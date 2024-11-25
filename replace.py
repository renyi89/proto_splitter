import csv

def read_tsv(file_path):
    """读取TSV文件, 返回混淆字段和解混淆字段的字典"""
    mapping = {}
    with open(file_path, 'r', encoding='utf-8') as tsvfile:
        reader = csv.reader(tsvfile, delimiter='\t')
        next(reader)  # 跳过表头
        for row in reader:
            if len(row) == 2:
                mapping[row[0]] = row[1]
    return mapping

def replace_content(file_path, mapping):
    """读取文件内容并进行替换"""
    with open(file_path, 'r', encoding='utf-8') as file:
        content = file.read()
    
    for key, value in mapping.items():
        content = content.replace(key, value)
    
    return content

def write_content(file_path, content):
    """将替换后的内容写回文件"""
    with open(file_path, 'w', encoding='utf-8') as file:
        file.write(content)

def main(tsv_file, target_file):
    # 读取TSV文件
    mapping = read_tsv(tsv_file)
    
    # 替换目标文件内容
    new_content = replace_content(target_file, mapping)
    
    # 写回目标文件
    write_content(target_file, new_content)

if __name__ == "__main__":
    tsv_file = 'mapping.tsv'  # TSV文件路径
    target_file = 'all-in-one.proto'  # 目标文件路径
    main(tsv_file, target_file)