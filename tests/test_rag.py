import asyncio
import os
import sys

# 1. 把 rag 目录临时加入 Python 系统路径，确保能顺利找到 retriever 代码
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "rag")))

from retriever import RagRequest, rag_search


def call_rag_search(payload):
    """
    直接调用 FastAPI endpoint 函数，避免测试层为了 TestClient 引入额外 HTTP 客户端依赖。

    这里验证的重点是 D 模块检索逻辑和 /api/rag/search 的 JSON 契约；
    路由层本身由 FastAPI 管理，C-D adapter 联调时再通过真实 HTTP 服务覆盖。
    """
    return asyncio.run(rag_search(RagRequest(**payload)))


def test_rag_search_hit():
    """
    用例一：正常检索命中测试（测试“降噪耳机”）
    预期：HTTP 状态码 200，返回成功，且 results 列表长度大于 0
    """
    payload = {
        "user_id": "u001",
        "case_id": "case_001",
        "case_type": "shopping",
        "query": "降噪耳机 学习",
        "top_k": 3
    }
    data = call_rag_search(payload)
    assert data["success"] is True, "返回 JSON 中 success 不为 True"
    assert len(data["data"]["results"]) > 0, "搜‘降噪耳机’居然没有召回任何数据！"
    print("\n✅ 用例一通过：正常检索命中测试成功！")


def test_rag_search_anti_hallucination():
    """
    用例二：防幻觉极限边界测试（测试奇葩关键词“挖掘机”）
    预期：HTTP 状态码 200，但是不应该捏造数据，results 列表长度必须严格等于 0
    """
    payload = {
        "user_id": "u001",
        "case_id": "case_002",
        "case_type": "shopping",
        "query": "挖掘机 航空母舰",
        "top_k": 3
    }
    data = call_rag_search(payload)
    assert data["success"] is True, "返回 JSON 中 success 不为 True"
    assert len(data["data"]["results"]) == 0, "防幻觉失败！搜‘挖掘机’居然召回了无关记录！"
    print("\n✅ 用例二通过：防幻觉极限边界测试成功！")


def test_rag_case_type_isolation():
    """
    用例三：数据隔离测试（测试用 time 场景搜购物数据）
    预期：搜“机械键盘”，但传的 case_type 是 time（时间决策），应该由于类型隔离返回空列表
    """
    payload = {
        "user_id": "u001",
        "case_id": "case_003",
        "case_type": "time",
        "query": "机械键盘 青轴 降噪耳机",
        "top_k": 3
    }
    data = call_rag_search(payload)
    assert len(data["data"]["results"]) == 0, "数据隔离失效！在 time 场景下召回了 shopping 的记录！"
    print("\n✅ 用例三通过：case_type 跨场景数据隔离测试成功！")
