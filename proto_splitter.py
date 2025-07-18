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

# 输出文件夹路径
OUTPUT_FOLDER = 'D:\\projects\\GC\\LunaGC_5.7.0\\src\\main\\proto'

# 定义文件头部内容
HEADER_CONTENT = '''syntax = "proto3";
option java_package = "emu.grasscutter.net.proto";
'''

# 生成输出文件前永远清理输出文件夹
CLEAR_OUTPUTFOLDER_FOREVER = True

# 允许未知 proto
ALLOWUNKNOWNPROTO = False

# 检查目标版本 不通过条件的不继续解析
CHECK_VERSION = False

# 目标版本 不要出现小数点
VERSION = 570

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

# 处理嵌套的 message enum
def parse_messages(content):
    messages = []
    stack = []
    current_message = ''
    in_message = False

    lines = content.splitlines()
    for line in lines:
        if 'message' in line or 'enum' in line:
            if in_message:
                stack.append(current_message)
            current_message = line
            in_message = True
        elif '}' in line and in_message:
            current_message += '\n' + line
            if stack:
                current_message = stack.pop() + '\n' + current_message
            else:
                messages.append(current_message)
                current_message = ''
                in_message = False
        elif in_message:
            current_message += '\n' + line

    return messages

# 处理嵌套的 message enum //fx 括号平衡
def parse_messages_fx(content):
    messages = []
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
            in_message = True
            current_message =  line
            if lines[index-1].startswith( '//' ):
                current_message = lines[index-1] + '\n' + current_message
            if lines[index-2].startswith( '//' ):
                current_message = lines[index-2] + '\n' + current_message
        elif in_message and value_left == 0:
            in_message = False
            current_message += '\n'+  line
            messages.append(current_message)
            current_message = ''
        elif in_message:
            current_message += '\n' + line

    return messages

# Proto 自带的数据类型
builtin_types = {
    'double', 'float', 'int32', 'int64', 'uint32', 'uint64', 'sint32', 'sint64',
    'fixed32', 'fixed64', 'sfixed32', 'sfixed64', 'bool', 'string', 'bytes',
    'option', 'optional', 'oneof', 'reserved', 'enum', 'message', 
    'repeated', ' repeated ',' repeated', 'repeated ',
}

# 检查 message 中是否存在 enum CmdId 并且包含 CMD_ID
def has_cmd_id_enum(message):
    cmd_id_pattern = re.compile(r'enum\s+CmdId\s*\{[^}]*\bCMD_ID\s*=\s*(\d+);', re.DOTALL)
    match = cmd_id_pattern.search(message)
    return match.group(1) if match else None

# 检查 message 中是否存在 enum Note 并且包含 VERSION
def has_version_in_cmd_id(message):
    version_pattern = re.compile(r'enum\s+Note\s*\{[^}]*\bVERSION\s*=\s*(\d+);', re.DOTALL)
    match = version_pattern.search(message)
    return int(match.group(1)) if match else None


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
for message in all_messages:
    bans = []
    is_enum = False

    # # 确保文件的结尾是 } 不然有 oneof 关键字出现时会少一个括号
    # if message.endswith('\n}') == False:
    #     message += '\n}'

    # 提取 message 名称
    message_name = re.search(r'(message|enum)\s+(\w+)', message).group(2)

    # 跳过全大写的未知 proto
    if message_name.isupper() and ALLOWUNKNOWNPROTO == False:
        # print("未知字段 " + message_name + " 被跳过")
        unknown_skip_count += 1
        continue

    # CHECK_VERSION 判断方法放在这里性能会有优化 但是生成的注释 version 会在 cmdid 下面
    # 对 cmdid 脚本不友好
    
    # 记录需要导入的未知类型
    imports = set()

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
                if key_type.isupper() and ALLOWUNKNOWNPROTO == False:
                    bans.append(key_type)
                else:
                    imports.add(f'import "{key_type}.proto";')
            if value_type not in builtin_types and value_type not in internal_typology:
                if value_type.isupper() and ALLOWUNKNOWNPROTO == False:
                    bans.append(value_type)
                else:
                    imports.add(f'import "{value_type}.proto";')
        elif 'repeated' in data_type:
            # 提取 repeated 类型
            repeated_type = data_type.split()[1]
            if repeated_type not in builtin_types and repeated_type not in internal_typology:
                if repeated_type.isupper() and ALLOWUNKNOWNPROTO == False:
                    bans.append(repeated_type)
                else:
                    imports.add(f'import "{repeated_type}.proto";')
        elif 'optional' in data_type:
            # 提取 optional 类型
            optional_type = data_type.split()[1]
            if optional_type not in builtin_types and optional_type not in internal_typology:
                if optional_type.isupper() and ALLOWUNKNOWNPROTO == False:
                    bans.append(optional_type)
                else:
                    imports.add(f'import "{optional_type}.proto";')
        else:
            data_type = data_type.split(".")[0]
            if data_type not in builtin_types and data_type not in internal_typology:
                if data_type.isupper() and ALLOWUNKNOWNPROTO == False:
                    bans.append(data_type)
                else:
                    imports.add(f'import "{data_type}.proto";')
    if ALLOWUNKNOWNPROTO == False:

        # 保留不包含任何关键词的行
        filtered_lines = [line for line in message.splitlines()
                  if not any(keyword in line for keyword in bans)]

        # 合并为新文本
        message = "\n".join(filtered_lines)
    
    # 检查 message 中是否存在 enum CmdId 并且包含 CMD_ID
    cmd_id_value = has_cmd_id_enum(message)
    if cmd_id_value:
        message = f'// CmdId: {cmd_id_value}\n{message}'

    # 检查是否枚举类型
    if re.search(r'(enum)\s+(Note)', message):
        is_enum = False
    elif re.search(r'(enum)\s+(\w+)', message):
        is_enum = True

    # 检查源文件 VERSION 是否符合要求 不对枚举起作用
    version_value = has_version_in_cmd_id(message)
    if CHECK_VERSION and is_enum == False:
        if version_value is not None:
            if version_value != VERSION:
                skip_count_old_version += 1
                continue
            else:
                message = f'// version: {version_value}\n{message}'
        else:   # 没有 version_value 的情况下
            skip_count_old_version += 1
            continue
    
    # 构建输出文件路径
    output_file_path = os.path.join(OUTPUT_FOLDER, f'{message_name}.proto')
    
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