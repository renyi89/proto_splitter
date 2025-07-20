# /**
#  * @注意 源文件不能出现带有 枚举cmdid 的 proto 被嵌套进另一个 proto， 否则生成的 cmdid 注释会混乱
#  * @注意 源 message 如果出现 oneof 类型 则下面的字段都会被丢弃 直到进入下一个 message
#  * @brief 将多个 .proto 文件中的 message enum 分解为独立的 .proto 文件。
#  **/

import os
import re
import chardet  # py -m pip install chardet
import shutil   # py -m pip install shutilwhich


''' CONFIG Start '''

# 输入文件夹路径
INPUT_FOLDER = './proto/v5.7.0/protocol/'
# INPUT_FOLDER = 'D:\\BaiduNetdiskDownload\\原神5.7-GC启动器\\server\\work\\output 57\\'


# 输出文件夹路径
OUTPUT_FOLDER = 'D:\\projects\\GC\\Grasscutter_KunCore\\src\\main\\proto'

# 定义文件头部内容
HEADER_CONTENT = '''syntax = "proto3";
option java_package = "emu.grasscutter.net.proto";
'''

# 生成输出文件前永远清理输出文件夹
CLEAR_OUTPUTFOLDER_FOREVER = True

# 允许未知 proto
ALLOWUNKNOWNPROTO = False

''' CONFIG END '''

print('start')

if os.path.exists(OUTPUT_FOLDER):
    if CLEAR_OUTPUTFOLDER_FOREVER:
        response = "y"
    else:
        response = input(f"输出文件夹 {OUTPUT_FOLDER} 已存在，是否先清理其中的文件？ (y/n): ").strip().lower()

    if response == 'y':
        # 清理输出文件夹
        for filename in os.listdir(OUTPUT_FOLDER):
            file_path = os.path.join(OUTPUT_FOLDER, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception as e:
                print(f'删除文件 {file_path} 时出错: {e}')
        print(f"已清理输出文件夹 {OUTPUT_FOLDER}")
else:
    # 确保输出文件夹存在
    os.makedirs(OUTPUT_FOLDER)

# 读取输入文件夹中的所有 .proto 文件
input_files = [os.path.join(INPUT_FOLDER, f) for f in os.listdir(INPUT_FOLDER) if f.endswith('.proto')]
print(input_files)

def is_unknown(name):
    if name.isupper():
        return True
    if name.startswith("unk_") or name.startswith("Unk_"):
        return True
    return False

# 处理嵌套的 message enum //fx 括号平衡
def parse_messages_fx(content):
    is_enum = False
    pl_messages = []
    current_comment = ''
    current_message = ''
    in_message = False
    value_left = 0

    lines = content.splitlines()
    for index,line in enumerate(lines):
        if '{' in line:
            value_left += 1
        if '}' in line:
            value_left -= 1
        if not in_message and ( 'message ' in line or 'enum ' in line ):
            if 'message ' in line:
                is_enum = False
            if 'enum ' in line:
                is_enum = True
            in_message = True
            current_message =  line
            current_comment = ''
            if lines[index-1].startswith( '//' ):
                current_comment =  lines[index-1] + '\n' + current_comment
            if lines[index-2].startswith( '//' ):
                current_comment = lines[index-2] + '\n' + current_comment
        elif in_message and value_left == 0:
            cmd_id = -1
            name = re.search(r'(message|enum)\s+(\w+)', current_message.lstrip().rstrip()).group(2)
            cmd_id_pattern = re.compile(r'CmdId: (\d+)', re.MULTILINE)
            cmd_ids = cmd_id_pattern.findall(current_comment.lstrip().rstrip())
            if len(cmd_ids) == 1:
                cmd_id = cmd_ids[0]
            in_message = False
            current_message += '\n'+  line
            layer = -1
            if is_enum:
                layer = 0
            pl_message = {
                'is_enum': is_enum,
                'name': name,
                'cmd_id': cmd_id,
                'layer': layer,
                'base_widget': 0,
                'widget': -1,
                'type_widget': {},
                'count': 0,
                'wcount': 0,
                'imports': set(),
                'comment': current_comment.lstrip().rstrip(),
                'message': current_message.lstrip().rstrip()
            }
            pl_messages.append(pl_message)
            current_message = ''
        elif in_message:
            current_message += '\n' + line

    return pl_messages


# Proto 自带的数据类型
builtin_types = {
    'double', 'float', 'int32', 'int64', 'uint32', 'uint64', 'sint32', 'sint64',
    'fixed32', 'fixed64', 'sfixed32', 'sfixed64', 'bool', 'string', 'bytes',
    'option', 'optional', 'oneof', 'reserved', 'enum', 'message', 
    'repeated', ' repeated ',' repeated', 'repeated ',
}


# 处理所有输入文件
all_messages = []
for input_file in input_files:
    print("正在处理输入文件: " + input_file)
    with open(input_file, 'rb') as file:
        raw_content = file.read()
        detected_encoding = chardet.detect(raw_content)['encoding']
        content = raw_content.decode(detected_encoding)
    # content = re.sub(r'\{(?!\n)', '{\n', content)
    messages = parse_messages_fx(content)
    all_messages.extend(messages)

# 初始化计数
processed_count = 0
unknown_skip_count = 0
skip_count_old_version = 0
is_enum = False

# 将每个 message 保存到独立的文件中
for pl_message in all_messages:
    message = pl_message['message']
    message_name = pl_message['name']
    is_enum = pl_message['is_enum']

    bans = []
    

    # 跳过全大写的未知 proto
    if is_unknown(message_name) and ALLOWUNKNOWNPROTO == False:
        # print("未知字段 " + message_name + " 被跳过")
        unknown_skip_count += 1
        continue

    # 解析 message 中的数据类型
    # 这样写会导致 enum 类型生成的文件导入无关包 所以用下面的正则
    # type_pattern = re.compile(r'\b(\w+)\b\s+\w+\s*=', re.MULTILINE)   # 备份一下
    # type_pattern = re.compile(r'^\s*\w*\s*(\b\w+\b)\s+\w+\s*=', re.MULTILINE)
    # type_pattern = re.compile(r'^\s*(map<[\w, ]+>|[\w]+)\s+\w+\s*=', re.MULTILINE)
    type_pattern = re.compile(r'^\s*(map<[\w, ]+>|repeated+\s+[\w]+|optional+\s+[\w]+|[\w.]+)\s+\w+\s*=', re.MULTILINE)
    types = type_pattern.findall(message)

    # 记录内部定义的类型
    internal_typology = set()

    # 提取内部定义的 enum 类型
    enum_pattern = re.compile(r'enum\s+(\w+)\s*\{', re.MULTILINE)
    internal_typology.update(enum_pattern.findall(message))
    # 提取内部定义的 message 类型
    message_pattern = re.compile(r'message\s+(\w+)\s*\{', re.MULTILINE)
    internal_typology.update(message_pattern.findall(message))
    
    for data_type in types:
        if 'map<' in data_type:
            # 提取 map 中的键和值类型
            key_type, value_type = data_type[4:-1].split(',')
            key_type = key_type.strip()
            value_type = value_type.strip()
            # 处理 map 类型
            if key_type not in builtin_types and key_type not in internal_typology:
                if is_unknown(key_type) and ALLOWUNKNOWNPROTO == False:
                    bans.append(key_type)
                else:
                    pl_message['imports'].add(key_type)
            if value_type not in builtin_types and value_type not in internal_typology:
                if is_unknown(value_type) and ALLOWUNKNOWNPROTO == False:
                    bans.append(value_type)
                else:
                    pl_message['imports'].add(value_type)
        elif 'repeated' in data_type:
            # 提取 repeated 类型
            repeated_type = data_type.split()[1]
            if repeated_type not in builtin_types and repeated_type not in internal_typology:
                if is_unknown(repeated_type) and ALLOWUNKNOWNPROTO == False:
                    bans.append(repeated_type)
                else:
                    pl_message['imports'].add(repeated_type)
        elif 'optional' in data_type:
            # 提取 optional 类型
            optional_type = data_type.split()[1]
            if optional_type not in builtin_types and optional_type not in internal_typology:
                if is_unknown(optional_type) and ALLOWUNKNOWNPROTO == False:
                    bans.append(optional_type)
                else:
                    pl_message['imports'].add(optional_type)
        else:
            data_type = data_type.split(".")[0]
            if data_type not in builtin_types and data_type not in internal_typology:
                if is_unknown(data_type) and ALLOWUNKNOWNPROTO == False:
                    bans.append(data_type)
                else:
                    pl_message['imports'].add(data_type)


    if ALLOWUNKNOWNPROTO == False:

        # 保留不包含任何关键词的行
        filtered_lines = [line for line in message.splitlines()
                  if not any(keyword in line for keyword in bans)]

        # 合并为新文本
        message = "\n".join(filtered_lines)

        pl_message['message'] = message


def collect_names(pl_messages, allow_names):
    name_map = {item['name']: item for item in pl_messages}
    result = set(allow_names)

    def traverse(name):
        if name in name_map:
            for imp in name_map[name]['imports']:
                if imp not in result:
                    result.add(imp)
                    traverse(imp)

    for name in allow_names:
        traverse(name)

    return result

allow_names = [
    "AbilityChangeNotify",
    "AbilityInvocationsNotify",
    "AchievementAllDataNotify",
    "AchievementUpdateNotify",
    "ActivitySelectAvatarCardReq",
    "ActivitySelectAvatarCardRsp",
    "ActivityScheduleInfoNotify",
    "ActivityTakeWatcherRewardReq",
    "ActivityTakeWatcherRewardRsp",
    "ActivityUpdateWatcherNotify",
    "AddBackupAvatarTeamRsp",
    "AddNoGachaAvatarCardNotify",
    "AddQuestContentProgressReq",
    "AddQuestContentProgressRsp",
    "AllWidgetDataNotify",
    "AskAddFriendNotify",
    "AskAddFriendReq",
    "AskAddFriendRsp",
    "AvatarAddNotify",
    "AvatarChangeCostumeNotify",
    "AvatarChangeCostumeReq",
    "AvatarChangeCostumeRsp",
    "AvatarChangeElementTypeReq",
    "AvatarChangeElementTypeRsp",
    "AvatarChangeTraceEffectReq",
    "AvatarChangeTraceEffectRsp",
    "AvatarDataNotify",
    "AvatarDelNotify",
    "AvatarDieAnimationEndReq",
    "AvatarDieAnimationEndRsp",
    "AvatarEquipChangeNotify",
    "AvatarExpeditionAllDataRsp",
    "AvatarExpeditionCallBackReq",
    "AvatarExpeditionCallBackRsp",
    "AvatarExpeditionDataNotify",
    "AvatarExpeditionGetRewardReq",
    "AvatarExpeditionGetRewardRsp",
    "AvatarExpeditionStartReq",
    "AvatarExpeditionStartRsp",
    "AvatarFetterDataNotify",
    "AvatarFetterLevelRewardReq",
    "AvatarFetterLevelRewardRsp",
    "AvatarFightPropNotify",
    "AvatarFightPropUpdateNotify",
    "AvatarFlycloakChangeNotify",
    "AvatarGainCostumeNotify",
    "AvatarGainFlycloakNotify",
    "AvatarGainTraceEffectNotify",
    "AvatarLifeStateChangeNotify",
    "AvatarPromoteReq",
    "AvatarPromoteRsp",
    "AvatarPropNotify",
    "AvatarSatiationDataNotify",
    "AvatarSkillChangeNotify",
    "AvatarSkillDepotChangeNotify",
    "AvatarSkillInfoNotify",
    "AvatarSkillMaxChargeCountNotify",
    "AvatarSkillUpgradeReq",
    "AvatarSkillUpgradeRsp",
    "AvatarTeamAllDataNotify",
    "AvatarTeamUpdateNotify",
    "AvatarTraceEffectChangeNotify",
    "AvatarUnlockTalentNotify",
    "AvatarUpgradeReq",
    "AvatarUpgradeRsp",
    "AvatarWearFlycloakReq",
    "AvatarWearFlycloakRsp",
    "AvatarWearWeaponSkinReq",
    "AvatarWearWeaponSkinRsp",
    "AvatarWeaponSkinDataNotify",
    "AntiAddictNotify",
    "BackMyWorldRsp",
    "BargainOfferPriceReq",
    "BargainOfferPriceRsp",
    "BargainStartNotify",
    "BargainTerminateNotify",
    "BattlePassAllDataNotify",
    "BattlePassCurScheduleUpdateNotify",
    "BattlePassMissionUpdateNotify",
    "BlossomBriefInfoNotify",
    "BuyBattlePassLevelReq",
    "BuyBattlePassLevelRsp",
    "BuyGoodsReq",
    "BuyGoodsRsp",
    "BuyResinRsp",
    "CalcWeaponUpgradeReturnItemsReq",
    "CalcWeaponUpgradeReturnItemsRsp",
    "CancelCoopTaskReq",
    "CancelCoopTaskRsp",
    "CanUseSkillNotify",
    "CardProductRewardNotify",
    "ChallengeDataNotify",
    "ChangeAvatarReq",
    "ChangeAvatarRsp",
    "ChangeGameTimeReq",
    "ChangeGameTimeRsp",
    "ChangeMailStarNotify",
    "ChangeMpTeamAvatarReq",
    "ChangeMpTeamAvatarRsp",
    "ChangeTeamNameReq",
    "ChangeTeamNameRsp",
    "ChapterStateNotify",
    "CheckUgcStateRsp",
    "CheckUgcUpdateReq",
    "CheckUgcUpdateRsp",
    "ChooseCurAvatarTeamReq",
    "ChooseCurAvatarTeamRsp",
    "ClientAbilitiesInitFinishCombineNotify",
    "ClientAbilityChangeNotify",
    "ClientAbilityInitFinishNotify",
    "ClientLockGameTimeNotify",
    "ClientScriptEventNotify",
    "CodexDataFullNotify",
    "CodexDataUpdateNotify",
    "CombatInvocationsNotify",
    "CombineDataNotify",
    "CombineFormulaDataNotify",
    "CombineReq",
    "CombineRsp",
    "CompoundDataNotify",
    "CookDataNotify",
    "CookRecipeDataNotify",
    "CoopDataNotify",
    "CreateVehicleReq",
    "CreateVehicleRsp",
    "CutSceneBeginNotify",
    "DealAddFriendReq",
    "DealAddFriendRsp",
    "DelBackupAvatarTeamReq",
    "DelBackupAvatarTeamRsp",
    "DeleteFriendNotify",
    "DeleteFriendReq",
    "DeleteFriendRsp",
    "DelMailReq",
    "DelMailRsp",
    "DelTeamEntityNotify",
    "DestroyMaterialReq",
    "DestroyMaterialRsp",
    "DoGachaReq",
    "DoGachaRsp",
    "DropHintNotify",
    "DungeonChallengeBeginNotify",
    "DungeonChallengeFinishNotify",
    "DungeonDieOptionReq",
    "DungeonDieOptionRsp",
    "DungeonEntryInfoReq",
    "DungeonEntryInfoRsp",
    "DungeonEntryToBeExploreNotify",
    "DungeonPlayerDieNotify",
    "DungeonPlayerDieReq",
    "DungeonPlayerDieRsp",
    "DungeonRestartRsp",
    "DungeonSettleNotify",
    "DungeonShowReminderNotify",
    "DungeonSlipRevivePointActivateReq",
    "DungeonSlipRevivePointActivateRsp",
    "DungeonWayPointActivateReq",
    "DungeonWayPointActivateRsp",
    "DungeonWayPointNotify",
    "EnterSceneDoneReq",
    "EnterSceneDoneRsp",
    "EnterScenePeerNotify",
    "EnterSceneReadyReq",
    "EnterSceneReadyRsp",
    "EnterTransPointRegionNotify",
    "EnterTrialAvatarActivityDungeonReq",
    "EnterTrialAvatarActivityDungeonRsp",
    "EnterWorldAreaReq",
    "EnterWorldAreaRsp",
    "EntityAiKillSelfNotify",
    "EntityAiSyncNotify",
    "EntityAnimatorPairValueInfoNotify",
    "EntityFightPropChangeReasonNotify",
    "EntityFightPropUpdateNotify",
    "EvtAiSyncCombatThreatInfoNotify",
    "EvtAiSyncSkillCdNotify",
    "EvtAvatarEnterFocusNotify",
    "EvtAvatarExitFocusNotify",
    "EvtAvatarLockChairReq",
    "EvtAvatarLockChairRsp",
    "EvtAvatarSitDownNotify",
    "EvtAvatarStandUpNotify",
    "EvtAvatarUpdateFocusNotify",
    "EvtBulletDeactiveNotify",
    "EvtBulletHitNotify",
    "EvtBulletMoveNotify",
    "EvtCreateGadgetNotify",
    "EvtDestroyGadgetNotify",
    "EvtDoSkillSuccNotify",
    "EvtEntityRenderersChangedNotify",
    "ExecuteGadgetLuaReq",
    "ExecuteGadgetLuaRsp",
    "ExitTransPointRegionNotify",
    "FinishedParentQuestNotify",
    "FinishedParentQuestUpdateNotify",
    "FireworksLaunchDataNotify",
    "FireworksReformDataNotify",
    "ForgeDataNotify",
    "ForgeFormulaDataNotify",
    "ForgeGetQueueDataRsp",
    "ForgeQueueDataNotify",
    "ForgeQueueManipulateReq",
    "ForgeQueueManipulateRsp",
    "ForgeStartReq",
    "ForgeStartRsp",
    "FurnitureCurModuleArrangeCountNotify",
    "FurnitureMakeRsp",
    "FurnitureMakeStartReq",
    "FurnitureMakeStartRsp",
    "GachaWishReq",
    "GachaWishRsp",
    "GadgetAutoPickDropInfoNotify",
    "GadgetInteractReq",
    "GadgetInteractRsp",
    "GadgetStateNotify",
    "GetActivityInfoReq",
    "Uint32Pair",
    "ActivityPushTipsData",
    "ActivityWatcherInfo",
    "TrialAvatarActivityDetailInfo",
    "TowerChallengeDetailInfo",
    "GetActivityShopSheetInfoReq",
    "GetActivityShopSheetInfoRsp",
    "GetAllActivatedBargainDataRsp",
    "GetAllMailNotify",
    "GetAllMailResultNotify",
    "GetAllUnlockNameCardRsp",
    "GetAuthkeyReq",
    "GetAuthkeyRsp",
    "GetBargainDataReq",
    "GetBargainDataRsp",
    "GetCompoundDataRsp",
    "GetChatEmojiCollectionRsp",
    "GetDailyDungeonEntryInfoReq",
    "GetDailyDungeonEntryInfoRsp",
    "GetDungeonEntryExploreConditionReq",
    "GetDungeonEntryExploreConditionRsp",
    "GetFriendShowAvatarInfoReq",
    "GetFriendShowAvatarInfoRsp",
    "GetFriendShowNameCardInfoReq",
    "GetFriendShowNameCardInfoRsp",
    "GetGachaInfoRsp",
    "GetGameplayRecommendationReq",
    "GetGameplayRecommendationRsp",
    "GetHomeLevelUpRewardReq",
    "GetHomeLevelUpRewardRsp",
    "GetInvestigationMonsterReq",
    "GetInvestigationMonsterRsp",
    "GetMailItemReq",
    "GetMailItemRsp",
    "GetOnlinePlayerListRsp",
    "GetPlayerAskFriendListRsp",
    "GetPlayerBlacklistRsp",
    "GetPlayerFriendListRsp",
    "GetPlayerSocialDetailReq",
    "GetPlayerSocialDetailRsp",
    "GetPlayerTokenReq",
    "GetPlayerTokenRsp",
    "GetProfilePictureDataRsp",
    "GetQuickswapWidgetsRsp",
    "GetSceneAreaReq",
    "GetSceneAreaRsp",
    "GetScenePointReq",
    "GetScenePointRsp",
    "GetShopmallDataRsp",
    "GetShopReq",
    "GetShopRsp",
    "GetUgcBriefInfoReq",
    "GetUgcBriefInfoRsp",
    "GetUgcReq",
    "GetUgcRsp",
    "GetWidgetSlotRsp",
    "GetWorldMpInfoRsp",
    "GivingRecordNotify",
    "GmTalkReq",
    "GmTalkRsp",
    "GroupSuiteNotify",
    "GroupUnloadNotify",
    "H5ActivityIdsNotify",
    "HitTreeNotify",
    "HomeAllUnlockedBgmIdListNotify",
    "HomeAvatarAllFinishRewardNotify",
    "HomeAvatarCostumeChangeNotify",
    "HomeAvatarRewardEventGetReq",
    "HomeAvatarRewardEventGetRsp",
    "HomeAvatarRewardEventNotify",
    "HomeAvatarSummonAllEventNotify",
    "HomeAvatarSummonEventReq",
    "HomeAvatarSummonEventRsp",
    "HomeAvatarSummonFinishReq",
    "HomeAvatarSummonFinishRsp",
    "HomeAvatarTalkFinishInfoNotify",
    "HomeAvatarTalkReq",
    "HomeAvatarTalkRsp",
    "HomeBasicInfoNotify",
    "HomeChangeBgmNotify",
    "HomeChangeBgmReq",
    "HomeChangeBgmRsp",
    "HomeChangeEditModeReq",
    "HomeChangeEditModeRsp",
    "HomeChangeModuleReq",
    "HomeChangeModuleRsp",
    "HomeChooseModuleReq",
    "HomeChooseModuleRsp",
    "HomeComfortInfoNotify",
    "HomeEnterEditModeFinishRsp",
    "HomeGetArrangementInfoReq",
    "HomeGetArrangementInfoRsp",
    "HomeGetOnlineStatusRsp",
    "HomeKickPlayerReq",
    "HomeKickPlayerRsp",
    "HomeMarkPointNotify",
    "HomeModuleSeenReq",
    "HomeModuleSeenRsp",
    "HomeModuleUnlockNotify",
    "HomeNewUnlockedBgmIdListNotify",
    "HomePreChangeEditModeNotify",
    "HomeResourceNotify",
    "HomeResourceTakeFetterExpRsp",
    "HomeResourceTakeHomeCoinRsp",
    "HomeSaveArrangementNoChangeReq",
    "HomeSaveArrangementNoChangeRsp",
    "HomeSceneInitFinishRsp",
    "HomeSceneJumpReq",
    "HomeSceneJumpRsp",
    "HomeTransferReq",
    "HomeUpdateArrangementInfoReq",
    "HomeUpdateArrangementInfoRsp",
    "HostPlayerNotify",
    "ItemAddHintNotify",
    "ItemGivingReq",
    "ItemGivingRsp",
    "LaunchFireworksReq",
    "LevelupCityReq",
    "LevelupCityRsp",
    "LifeStateChangeNotify",
    "MailChangeNotify",
    "MarkMapReq",
    "MarkMapRsp",
    "MarkNewNotify",
    "MassiveEntityElementOpBatchNotify",
    "McoinExchangeHcoinReq",
    "McoinExchangeHcoinRsp",
    "MonsterAIConfigHashNotify",
    "MonsterAlertChangeNotify",
    "MonsterForceAlertNotify",
    "MonsterSummonTagNotify",
    "MusicGameSettleReq",
    "MusicGameSettleRsp",
    "MusicGameStartReq",
    "MusicGameStartRsp",
    "NpcTalkReq",
    "NpcTalkRsp",
    "ObstacleModifyNotify",
    "OpenStateChangeNotify",
    "OpenStateUpdateNotify",
    "OtherPlayerEnterHomeNotify",
    "PathfindingEnterSceneReq",
    "PathfindingEnterSceneRsp",
    "PersonalLineAllDataRsp",
    "PersonalSceneJumpReq",
    "PersonalSceneJumpRsp",
    "PingReq",
    "PingRsp",
    "PlatformChangeRouteNotify",
    "PlatformStartRouteNotify",
    "PlatformStopRouteNotify",
    "PlayerApplyEnterHomeNotify",
    "PlayerApplyEnterHomeResultNotify",
    "PlayerApplyEnterHomeResultReq",
    "PlayerApplyEnterHomeResultRsp",
    "PlayerApplyEnterMpNotify",
    "PlayerApplyEnterMpReq",
    "PlayerApplyEnterMpResultNotify",
    "PlayerApplyEnterMpResultReq",
    "PlayerApplyEnterMpResultRsp",
    "PlayerApplyEnterMpRsp",
    "PlayerChatNotify",
    "PlayerChatReq",
    "PlayerChatRsp",
    "PlayerCompoundMaterialReq",
    "PlayerCompoundMaterialRsp",
    "PlayerCookArgsReq",
    "PlayerCookArgsRsp",
    "PlayerCookReq",
    "PlayerCookRsp",
    "PlayerDataNotify",
    "PlayerEnterDungeonReq",
    "PlayerEnterDungeonRsp",
    "PlayerEnterSceneInfoNotify",
    "PlayerEnterSceneNotify",
    "PlayerForceExitRsp",
    "PlayerGameTimeNotify",
    "PlayerGetForceQuitBanInfoRsp",
    "PlayerHomeCompInfoNotify",
    "PlayerLevelRewardUpdateNotify",
    "PlayerLoginReq",
    "PlayerLoginRsp",
    "PlayerPreEnterMpNotify",
    "PlayerPropChangeNotify",
    "PlayerPropChangeReasonNotify",
    "PlayerPropNotify",
    "PlayerQuitDungeonReq",
    "PlayerQuitDungeonRsp",
    "PlayerQuitFromHomeNotify",
    "PlayerSetPauseReq",
    "PlayerSetPauseRsp",
    "PlayerStoreNotify",
    "PlayerTimeNotify",
    "PlayerWorldSceneInfoListNotify",
    "PostEnterSceneReq",
    "PostEnterSceneRsp",
    "PrivateChatNotify",
    "PrivateChatReq",
    "ProudSkillChangeNotify",
    "ProudSkillExtraLevelNotify",
    "PullPrivateChatReq",
    "PullPrivateChatRsp",
    "PullRecentChatReq",
    "PullRecentChatRsp",
    "QueryCodexMonsterBeKilledNumReq",
    "QueryCodexMonsterBeKilledNumRsp",
    "QueryPathReq",
    "QueryPathRsp",
    "QuestCreateEntityReq",
    "QuestCreateEntityRsp",
    "QuestDelNotify",
    "QuestDestroyEntityReq",
    "QuestDestroyEntityRsp",
    "QuestDestroyNpcReq",
    "QuestDestroyNpcRsp",
    "QuestGlobalVarNotify",
    "QuestListNotify",
    "QuestListUpdateNotify",
    "QuestProgressUpdateNotify",
    "QuestTransmitReq",
    "QuestTransmitRsp",
    "QuestUpdateQuestVarNotify",
    "QuestUpdateQuestVarReq",
    "QuestUpdateQuestVarRsp",
    "QuickUseWidgetReq",
    "QuickUseWidgetRsp",
    "ReadMailNotify",
    "ReceivedTrialAvatarActivityRewardReq",
    "ReceivedTrialAvatarActivityRewardRsp",
    "ReformFireworksReq",
    "ReformFireworksRsp",
    "ReliquaryDecomposeReq",
    "ReliquaryDecomposeRsp",
    "ReliquaryUpgradeReq",
    "ReliquaryUpgradeRsp",
    "ResinChangeNotify",
    "SceneAreaUnlockNotify",
    "SceneAreaWeatherNotify",
    "SceneAudioNotify",
    "SceneEntityAppearNotify",
    "SceneEntityDisappearNotify",
    "SceneEntityDrownReq",
    "SceneEntityDrownRsp",
    "SceneEntityMoveNotify",
    "SceneEntityUpdateNotify",
    "SceneForceLockNotify",
    "SceneForceUnlockNotify",
    "SceneInitFinishReq",
    "SceneInitFinishRsp",
    "SceneKickPlayerReq",
    "SceneKickPlayerRsp",
    "ScenePlayerInfoNotify",
    "ScenePlayerLocationNotify",
    "ScenePlayerSoundNotify",
    "ScenePointUnlockNotify",
    "SceneTeamUpdateNotify",
    "SceneTimeNotify",
    "SceneTransToPointReq",
    "SceneTransToPointRsp",
    "SelectWorktopOptionReq",
    "SelectWorktopOptionRsp",
    "ServerAnnounceNotify",
    "ServerAnnounceRevokeNotify",
    "ServerBuffChangeNotify",
    "ServerCondMeetQuestListUpdateNotify",
    "ServerDisconnectClientNotify",
    "ServerGlobalValueChangeNotify",
    "ServerTimeNotify",
    "SetBattlePassViewedReq",
    "SetBattlePassViewedRsp",
    "SetCoopChapterViewedRsp",
    "SetChatEmojiCollectionReq",
    "SetEntityClientDataNotify",
    "SetEquipLockStateReq",
    "SetEquipLockStateRsp",
    "SetFriendEnterHomeOptionReq",
    "SetNameCardReq",
    "SetNameCardRsp",
    "SetOpenStateReq",
    "SetOpenStateRsp",
    "SetPlayerBirthdayReq",
    "SetPlayerBirthdayRsp",
    "SetPlayerBornDataReq",
    "SetPlayerBornDataRsp",
    "SetPlayerHeadImageReq",
    "SetPlayerHeadImageRsp",
    "SetPlayerNameReq",
    "SetPlayerNameRsp",
    "SetPlayerPropReq",
    "SetPlayerPropRsp",
    "SetPlayerSignatureReq",
    "SetPlayerSignatureRsp",
    "SetReliquaryFavouriteReq",
    "SetReliquaryFavouriteRsp",
    "SetUpAvatarTeamReq",
    "SetUpAvatarTeamRsp",
    "SetUpLunchBoxWidgetReq",
    "SetUpLunchBoxWidgetRsp",
    "SetWidgetSlotReq",
    "SetWidgetSlotRsp",
    "ShowClientGuideNotify",
    "ShowCommonTipsNotify",
    "SkipPlayerGameTimeReq",
    "SkipPlayerGameTimeRsp",
    "StartCoopPointReq",
    "StartCoopPointRsp",
    "StoreItemChangeNotify",
    "StoreItemDelNotify",
    "StoreWeightLimitNotify",
    "SyncScenePlayTeamEntityNotify",
    "SyncTeamEntityNotify",
    "TakeAchievementGoalRewardReq",
    "TakeAchievementGoalRewardRsp",
    "TakeAchievementRewardReq",
    "TakeAchievementRewardRsp",
    "TakeBattlePassMissionPointReq",
    "TakeBattlePassMissionPointRsp",
    "TakeBattlePassRewardReq",
    "TakeBattlePassRewardRsp",
    "TakeCompoundOutputReq",
    "TakeCompoundOutputRsp",
    "TakeFurnitureMakeReq",
    "TakeFurnitureMakeRsp",
    "TakeoffEquipReq",
    "TakeoffEquipRsp",
    "TakePlayerLevelRewardReq",
    "TakePlayerLevelRewardRsp",
    "TowerAllDataReq",
    "TowerAllDataRsp",
    "TowerCurLevelRecordChangeNotify",
    "TowerEnterLevelReq",
    "TowerEnterLevelRsp",
    "TowerFloorRecordChangeNotify",
    "TowerLevelStarCondNotify",
    "TowerTeamSelectReq",
    "TowerTeamSelectRsp",
    "TryEnterHomeReq",
    "TryEnterHomeRsp",
    "UnfreezeGroupLimitNotify",
    "UnionCmdNotify",
    "UnlockAvatarTalentReq",
    "UnlockAvatarTalentRsp",
    "UnlockedFurnitureFormulaDataNotify",
    "UnlockedFurnitureSuiteDataNotify",
    "UnlockNameCardNotify",
    "UnlockPersonalLineReq",
    "UnlockPersonalLineRsp",
    "UnlockTransPointReq",
    "UnlockTransPointRsp",
    "UpdateAbilityCreatedMovingPlatformNotify",
    "UpdatePlayerShowAvatarListReq",
    "UpdatePlayerShowAvatarListRsp",
    "UpdatePlayerShowNameCardListReq",
    "UpdatePlayerShowNameCardListRsp",
    "UseItemReq",
    "UseItemRsp",
    "VehicleInteractReq",
    "VehicleInteractRsp",
    "VehiclePhlogistonPointsNotify",
    "VehicleStaminaNotify",
    "WeaponAwakenReq",
    "WeaponAwakenRsp",
    "WeaponPromoteReq",
    "WeaponPromoteRsp",
    "WeaponUpgradeReq",
    "WeaponUpgradeRsp",
    "WearEquipReq",
    "WearEquipRsp",
    "WidgetCoolDownNotify",
    "WidgetDoBagReq",
    "WidgetDoBagRsp",
    "WidgetGadgetAllDataNotify",
    "WidgetGadgetDataNotify",
    "WidgetSlotChangeNotify",
    "WindSeedType1Notify",
    "WorktopOptionNotify",
    "WorldChestOpenNotify",
    "WorldDataNotify",
    "WorldPlayerDieNotify",
    "WorldPlayerInfoNotify",
    "WorldPlayerLocationNotify",
    "WorldPlayerReviveRsp",
    "WorldPlayerRTTNotify",

    "AttackResult",
    "AbilityActionCreateGadget",
    "AbilityActionGenerateElemBall",
    "AbilityActionSummon",
    "AbilityActionSetRandomOverrideMapValue",
    "AbilityMetaModifierChange",
    "AbilityMetaSpecialEnergy",
    "AbilityMixinChangePhlogiston",
    "AbilityMetaAddAbility",
    "AbilityMetaReInitOverrideMap",
    "AbilityMetaSetKilledState",
    "AbilityIdentifier",
    "EntityMoveInfo",
    "EvtAnimatorParameterInfo",
    "EvtBeingHitInfo",
    "ModifierAction",

    

    "QueryCurrRegionHttpRsp",
    "QueryRegionListHttpRsp",
    "Retcode",
]

# allow_names = [
#     "QuestCreateEntityRsp",
#     "QuestTransmitReq",
#     "FinishedParentQuestNotify",
#     "QuestGlobalVarNotify",
#     "QuestUpdateQuestVarReq",
#     "QuestUpdateQuestVarRsp",
#     "QuestDestroyNpcReq",
#     "QuestCreateEntityReq",
#     "QuestListNotify",
#     "QuestDestroyNpcRsp",
#     "QuestTransmitRsp",
#     "QuestDestroyEntityRsp",
#     "QuestUpdateQuestVarNotify",
#     "QuestListUpdateNotify",
#     "QuestProgressUpdateNotify",
#     "AddQuestContentProgressReq",
#     "AddQuestContentProgressRsp",
#     "FinishedParentQuestUpdateNotify",
#     "QuestDestroyEntityReq",
#     "SceneGadgetInfo"
# ]

allow_set = collect_names(all_messages, allow_names)

# 将每个 message 保存到独立的文件中
for pl_message in all_messages:
    
    message_name = pl_message['name']

    if message_name not in allow_set:
        continue

    # 跳过全大写的未知 proto
    if is_unknown(message_name) and ALLOWUNKNOWNPROTO == False:
        # print("未知字段 " + message_name + " 被跳过")
        continue

    message = pl_message['message']
    is_enum = pl_message['is_enum']

    imports = []
    for import_name in pl_message['imports']:
        imports.append(f'import "{import_name}.proto";')
    
    # 构建输出文件路径
    output_file_path = os.path.join(OUTPUT_FOLDER, f'{message_name}.proto')

    if pl_message['comment'] != '':
        message =  pl_message['comment'] + '\n' + message
    
    # 构建最终的文件内容
    final_content = HEADER_CONTENT + '\n'.join(imports) + '\n\n' + message
    
    # 写入文件
    with open(output_file_path, 'w', encoding='utf-8') as output_file:
        output_file.write(final_content)
    processed_count += 1

print(f'\n共找到 {len(all_messages)} 条 message|enum')
if unknown_skip_count > 0:
    print(f'有 {unknown_skip_count} 条不会被保存为文件 因为它们是未知字段')
if skip_count_old_version > 0:
    print(f'有 {skip_count_old_version} 条不会被保存为文件 因为它们并非目标版本')
print(f'成功将其中 {processed_count} 条 分割并保存到 {OUTPUT_FOLDER}')