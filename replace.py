import os
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

def process_files_in_directory(directory, mapping):
    """处理指定目录下的所有文件"""
    for root, _, files in os.walk(directory):
        for file_name in files:
            file_path = os.path.join(root, file_name)
            new_content = replace_content(file_path, mapping)
            write_content(file_path, new_content)

def main(tsv_file, target_directory):
    # 读取TSV文件
    mapping = read_tsv(tsv_file)
    
    # 处理目标文件夹内的所有文件
    process_files_in_directory(target_directory, mapping)

if __name__ == "__main__":
    tsv_file = 'mapping.tsv'  # TSV文件路径
    target_directory = 'output'  # 目标文件夹路径
    main(tsv_file, target_directory)