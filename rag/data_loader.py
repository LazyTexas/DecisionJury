import json
import os


def load_history_data():
    # 找到 data 文件夹的相对路径
    # 假设当前运行在 rag 目录下，我们要去上一层的 data 目录找文件
    current_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(current_dir, "..", "data", "history_records.json")

    # 用最基础的文件读取语法打开 json
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            print(f"成功加载了 {len(data)} 条历史记录！")
            return data
    except Exception as e:
        print(f"读取数据失败: {e}")
        return []


# 当你直接运行这个文件时，会执行下面这行代码进行测试
if __name__ == "__main__":
    records = load_history_data()
    if records:
        print("第一条数据的标题是:", records[0]["title"])