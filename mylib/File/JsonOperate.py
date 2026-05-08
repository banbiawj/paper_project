import os
import json
from typing import Union,List, Dict, Any

def create_json_file(directory: str, filename: str, content=None) -> str:
    """
    在指定目录下创建一个 .json 文件
    如果文件已存在，则直接返回路径，不重新创建

    参数:
        directory (str): 目标目录路径
        filename (str): 文件名，可以带或不带 .json 后缀
        content (dict | list, 可选): 要写入的内容，默认空列表 []

    返回:
        str: JSON 文件完整路径
    """
    # 默认内容为空列表
    if content is None:
        content = []

    # 确保文件名以 .json 结尾
    if not filename.endswith('.json'):
        filename += '.json'

    # 如果目录不存在，则创建目录
    os.makedirs(directory, exist_ok=True)

    # 拼接完整路径
    file_path = os.path.join(directory, filename)

    # 如果文件已经存在，直接返回
    if os.path.exists(file_path):
        return file_path

    # 写入 JSON 文件
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(content, f, ensure_ascii=False, indent=4)

    return file_path


def append_json_to_file(directory: str, filename: str, new_data):
    """
    将一段 JSON 数据追加到指定目录下的指定 .json 文件中
    
    参数:
        directory (str): 文件所在目录
        filename (str): JSON 文件名（可以带或不带 .json 后缀）
        new_data (dict | list): 要追加的 JSON 数据
    """
    if not filename.endswith('.json'):
        filename += '.json'

    os.makedirs(directory, exist_ok=True)
    file_path = os.path.join(directory, filename)

    # 读取已有内容
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            try:
                existing_data = json.load(f)
            except json.JSONDecodeError:
                existing_data = {} if isinstance(new_data, dict) else []
    else:
        existing_data = {} if isinstance(new_data, dict) else []

    # 追加数据
    if isinstance(existing_data, list) and isinstance(new_data, list):
        existing_data.extend(new_data)
    elif isinstance(existing_data, dict) and isinstance(new_data, dict):
        existing_data.update(new_data)
    elif isinstance(existing_data, list) and isinstance(new_data, dict):
        existing_data.append(new_data)
    elif isinstance(existing_data, dict) and isinstance(new_data, list):
        raise ValueError("无法将列表追加到字典 JSON 文件中")
    else:
        raise ValueError("JSON 数据类型不匹配")

    # 写回文件
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(existing_data, f, ensure_ascii=False, indent=4)

    return file_path


def read_json_file(directory: str, filename: str, encoding="utf-8"):
    """
    读取指定目录下的指定 .json 文件内容
    
    参数:
        directory (str): 目录路径
        filename (str): 文件名，可以带 .json 后缀，也可以不带
        encoding (str): 文件编码（默认 utf-8）

    返回:
        dict | list: JSON 文件的内容
    """
    # 确保文件名有 .json 后缀
    if not filename.endswith(".json"):
        filename += ".json"
    
    file_path = os.path.join(directory, filename)

    # 检查文件是否存在
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"文件不存在: {file_path}")
    
    # 读取 JSON 文件
    with open(file_path, "r", encoding=encoding) as f:
        content = json.load(f)
    
    return content


def find_in_json(data, key: str, value):
    """
    在 JSON 数据中查找匹配的键值对
    
    参数:
        data (dict | list): JSON 数据
        key (str): 要匹配的键
        value (any): 要匹配的值
    
    返回:
        dict | None: 匹配到的字典数据，若未找到返回 None
    """
    if isinstance(data, dict):  # JSON 是字典
        if data.get(key) == value:
            return data
        # 递归查找嵌套的字典或列表
        for v in data.values():
            result = find_in_json(v, key, value)
            if result is not None:
                return result

    elif isinstance(data, list):  # JSON 是列表
        for item in data:
            result = find_in_json(item, key, value)
            if result is not None:
                return result
    
    return None

# 覆写保存操作慎用，用于修改数据和删除数据
def overwrite_json_file(directory: str, filename: str, data: Union[dict, list]) -> str:
    """
    在指定目录下对指定 .json 文件进行覆写保存操作

    参数:
        directory (str): 目标目录路径
        filename (str): 文件名，可以带或不带 .json 后缀
        data (dict | list): 要写入的 JSON 数据

    返回:
        str: JSON 文件的完整路径
    """
    # 确保目录存在
    os.makedirs(directory, exist_ok=True)

    # 确保文件名后缀为 .json
    if not filename.endswith(".json"):
        filename += ".json"

    # 拼接完整路径
    file_path = os.path.join(directory, filename)

    # 覆写保存 JSON 数据
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

    return file_path


# 删除
def remove_key_value(key: str, value: str, data: Union[dict, list]) -> Union[dict, list, None]:
    """
    删除 JSON 数据中，包含指定键值对的整段数据

    参数:
        key (str): 要删除的键
        value (str): 要匹配的值
        data (dict | list): JSON 数据，可以是字典或列表

    返回:
        dict | list | None: 处理后的 JSON 数据（如果整个字典被删除，返回 None）
    """

    if isinstance(data, dict):
        # 如果是字典，且包含该键值对 -> 删除整个字典（返回 None）
        if key in data and data[key] == value:
            return None
        # 否则递归处理字典中的值
        return {k: remove_key_value(key, value, v) for k, v in data.items() if remove_key_value(key, value, v) is not None}

    elif isinstance(data, list):
        # 如果是列表，逐个检查，过滤掉匹配的数据
        new_list = []
        for item in data:
            processed = remove_key_value(key, value, item)
            if processed is not None:  # 只保留没被删除的
                new_list.append(processed)
        return new_list

    else:
        return data

# 修改
def replace_json_segment(key: str, value: Any, new_segment: Dict[str, Any], data_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    在 JSON 数据列表中，用新的 JSON 数据段替换掉匹配到的旧数据段

    参数:
        key (str): 用于匹配的键
        value (Any): 用于匹配的值
        new_segment (dict): 新的 JSON 数据段
        data_list (list[dict]): JSON 数据列表

    返回:
        list[dict]: 替换后的 JSON 数据列表
    """
    updated_list = []
    for item in data_list:
        if isinstance(item, dict) and item.get(key) == value:
            updated_list.append(new_segment)  # 替换
        else:
            updated_list.append(item)
    return updated_list


def remove_save_json(directory: str, filename: str,remove_data):
    try:
        favorite_datalist =  read_json_file(directory,filename)
        query_datalist = read_json_file(directory,"query")

        f_remove_end_data = remove_key_value("word",remove_data['word'],favorite_datalist)
        # q_remove_end_data = remove_key_value("word",remove_data['word'],query_datalist)

        overwrite_json_file(directory,filename,f_remove_end_data)
        # overwrite_json_file(directory,"query",q_remove_end_data)
        return False
    except Exception as e:
        return e

def replace_save_json(directory: str, filename: str,replace_data):
    try:
        favorite_datalist =  read_json_file(directory,filename)
        query_datalist = read_json_file(directory,"query")

        f_replace_end_data = replace_json_segment("word",replace_data['word'],replace_data,favorite_datalist)
        q_replace_end_data = replace_json_segment("word",replace_data['word'],replace_data,query_datalist)

        overwrite_json_file(directory,filename,f_replace_end_data)
        overwrite_json_file(directory,"query",q_replace_end_data)
        return False
    except Exception as e:
        return e

# 读取指定目录下的文件名列表
def list_files_in_directory(directory: str) -> list:
    """
    获取指定目录下的文件名列表

    参数:
        directory (str): 目标目录路径

    返回:
        list: 文件名列表（不包含路径）
    """
    try:
        # os.listdir 会列出目录下的所有文件和文件夹
        # 使用 os.path.isfile 过滤掉文件夹，只保留文件
        files = [f for f in os.listdir(directory) if os.path.isfile(os.path.join(directory, f))]
        return files
    except FileNotFoundError:
        print(f"错误：目录 '{directory}' 不存在。")
        return []
    except PermissionError:
        print(f"错误：没有权限访问目录 '{directory}'。")
        return []

# 获取指定目录下所有文件夹的名称
def get_folder_names(directory_path):
    """
    获取指定目录下所有文件夹的名称
    
    参数:
    directory_path (str): 要扫描的目录路径
    
    返回:
    list: 包含所有文件夹名称的字符串列表
    """
    try:
        # 检查路径是否存在
        if not os.path.exists(directory_path):
            print(f"错误：路径 '{directory_path}' 不存在")
            return []
        
        # 检查是否为目录
        if not os.path.isdir(directory_path):
            print(f"错误：'{directory_path}' 不是目录")
            return []
        
        # 获取目录下所有条目
        entries = os.listdir(directory_path)
        
        # 筛选出文件夹（排除文件）
        folders = []
        for entry in entries:
            full_path = os.path.join(directory_path, entry)
            if os.path.isdir(full_path):
                folders.append(entry)
        
        return folders
    
    except PermissionError:
        print(f"错误：没有权限访问目录 '{directory_path}'")
        return []
    except Exception as e:
        print(f"读取目录时发生错误：{str(e)}")
        return []


# 在指定目录下创建文件夹，并返回该目录下所有文件夹名
def create_folder_and_list(directory_path, folder_name):
    """
    在指定目录下创建文件夹，并返回该目录下所有文件夹名
    
    参数:
    directory_path (str): 指定目录路径
    folder_name (str): 要创建的文件夹名称
    
    返回:
    list: 包含指定目录下所有文件夹名称的字符串数组
    """
    try:
        # 检查目录路径是否存在
        if not os.path.exists(directory_path):
            print(f"错误：目录路径 '{directory_path}' 不存在")
            return []
        
        # 检查是否为目录
        if not os.path.isdir(directory_path):
            print(f"错误：'{directory_path}' 不是目录")
            return []
        
        # 构建新文件夹的完整路径
        new_folder_path = os.path.join(directory_path, folder_name)
        
        # 检查文件夹是否已存在
        if os.path.exists(new_folder_path):
            print(f"提示：文件夹 '{folder_name}' 已存在于 '{directory_path}' 中")
        else:
            # 创建新文件夹
            os.makedirs(new_folder_path, exist_ok=True)
            print(f"成功：在 '{directory_path}' 中创建了文件夹 '{folder_name}'")
        
        # 获取目录下所有文件夹名称
        all_items = os.listdir(directory_path)
        folders = []
        
        for item in all_items:
            item_path = os.path.join(directory_path, item)
            if os.path.isdir(item_path):
                folders.append(item)
        
        # 按字母顺序排序（可选）
        folders.sort()
        
        return folders
    
    except PermissionError:
        print(f"错误：没有权限在 '{directory_path}' 中创建文件夹或读取目录")
        return []
    except Exception as e:
        print(f"操作时发生错误：{str(e)}")
        return []






# if __name__ == "__main__":
#     directory_path = "E:\project-VScode-web\ds-memory\static\data\idiom"
#     file_list = create_folder_and_list(directory_path,"尝试")
#     print(file_list)
