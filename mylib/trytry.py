import os

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


# 使用示例
if __name__ == "__main__":
    # 测试1：使用当前目录
    print("当前目录下的文件夹：")
    folders = get_folder_names(".")
    for folder in folders:
        print(f"  - {folder}")
    
    # 测试2：指定其他路径
    # folders = get_folder_names("C:/Users/YourName/Documents")
    
    # 测试3：获取文件夹数量
    if folders:
        print(f"\n共找到 {len(folders)} 个文件夹")
    else:
        print("没有找到任何文件夹")