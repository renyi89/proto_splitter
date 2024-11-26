# /**
#  * @作者 亡灵奶龙大帝
#  * @注意 源文件不能出现带有 枚举cmdid 的 proto 被嵌套进另一个 proto， 否则生成的 cmdid 注释会混乱
#  * @brief 将多个 .proto 文件中的 message enum oneof 分解为独立的 .proto 文件。
#  **/

import os
import re
import chardet  # py -m pip install chardet
import shutil   # py -m pip install shutilwhich


''' CONFIG Start '''

# 输入文件夹路径
INPUT_FOLDER = 'cmd'

# 输出文件夹路径
OUTPUT_FOLDER = 'protocol'

# 定义文件头部内容
HEADER_CONTENT = '''syntax = "proto3";
package proto;
'''

# 生成输出文件前永远清理输出文件夹
CLEAR_OUTPUTFOLDER_FOREVER = True

# 允许未知 proto
ALLOWUNKNOWNPROTO = False

''' CONFIG END '''


if os.path.exists(OUTPUT_FOLDER):
    if CLEAR_OUTPUTFOLDER_FOREVER:
        response = "y"
    else:
        # 询问用户是否清理输出文件夹
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

# Proto 自带的数据类型
builtin_types = {
    'double', 'float', 'int32', 'int64', 'uint32', 'uint64', 'sint32', 'sint64',
    'fixed32', 'fixed64', 'sfixed32', 'sfixed64', 'bool', 'string', 'bytes',
    'option', 'oneof'
}

# 检查 message 中是否存在 enum CmdId 并且包含 CMD_ID
def has_cmd_id_enum(message):
    cmd_id_pattern = re.compile(r'enum\s+CmdId\s*\{[^}]*\bCMD_ID\s*=\s*(\d+);', re.DOTALL)
    match = cmd_id_pattern.search(message)
    return match.group(1) if match else None

# 处理所有输入文件
all_messages = []
for input_file in input_files:
    print("正在处理输入文件: " + input_file)
    with open(input_file, 'rb') as file:
        raw_content = file.read()
        detected_encoding = chardet.detect(raw_content)['encoding']
        content = raw_content.decode(detected_encoding)
    messages = parse_messages(content)
    all_messages.extend(messages)

processed_count = 0
skip_count = 0
# 将每个 message 保存到独立的文件中
for message in all_messages:
    # 提取 message 名称
    message_name = re.search(r'(message|enum)\s+(\w+)', message).group(2)
    # 跳过全大写的未知 proto
    if message_name.isupper() and ALLOWUNKNOWNPROTO == False:
        skip_count += 1
        continue
    
    # 记录需要导入的未知类型
    imports = set()

    # 解析 message 中的数据类型
    # 这样写会导致 enum 类型生成的文件导入无关包 所以用下面的正则
    # type_pattern = re.compile(r'\b(\w+)\b\s+\w+\s*=', re.MULTILINE)
    type_pattern = re.compile(r'^\s*\w*\s*(\b\w+\b)\s+\w+\s*=', re.MULTILINE)
    types = type_pattern.findall(message)
    
    for data_type in types:
        if data_type not in builtin_types:
            imports.add(f'import "{data_type}.proto";')
    
    # 检查 message 中是否存在 enum CmdId 并且包含 CMD_ID
    cmd_id_value = has_cmd_id_enum(message)
    if cmd_id_value:
        message = f'// CmdId: {cmd_id_value}\n{message}'
    
    # 构建输出文件路径
    output_file_path = os.path.join(OUTPUT_FOLDER, f'{message_name}.proto')
    
    # 构建最终的文件内容
    final_content = HEADER_CONTENT + '\n'.join(imports) + '\n\n' + message
    
    # 写入文件
    with open(output_file_path, 'w', encoding='utf-8') as output_file:
        output_file.write(final_content)
    processed_count += 1

print(f'共找到 {len(all_messages)} 条 message|enum')

if skip_count > 0:
    print(f'有 {skip_count} 条不会被保存为文件 因为它们是未知字段')

print(f'成功将其中 {processed_count} 条 分割并保存到 {OUTPUT_FOLDER}')
