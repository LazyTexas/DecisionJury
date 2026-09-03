import asyncio
import os
import sys

# 关闭实时后端联动，让单测/离线环境不依赖 B 后端服务和网络，保证快速、确定性。
# 联动逻辑本身由 tests/test_rag_data_loader.py 单独用 mock 覆盖。
os.environ.setdefault("RAG_LIVE_RECORDS", "0")

# 1. 把 rag 目录临时加入 Python 系统路径，确保能顺利找到 retriever 代码
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "rag")))

from retriever import RagRequest, rag_search  # noqa: E402


def call_rag_search(payload):
    """
    直接调用 FastAPI endpoint 函数，避免测试层为了 TestClient 引入额外 HTTP 客户端依赖。

    这里验证的重点是 D 模块检索逻辑和 /api/rag/search 的 JSON 契约；
    路由层本身由 FastAPI 管理，C-D adapter 联调时再通过真实 HTTP 服务覆盖。
    """
    return asyncio.run(rag_search(RagRequest(**payload)))


def results_for(payload):
    return call_rag_search(payload)["data"]["results"]


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


def test_rag_dataset_has_500_records():
    """
    新增验收：RAG 历史数据集应达到 500 条，购物/时间各 250，且字段齐全。
    """
    from data_loader import load_history_data
    records = load_history_data("u001")
    assert len(records) >= 500, f"数据集应不少于 500 条，当前 {len(records)}"
    shopping = sum(1 for r in records if r["case_type"] == "shopping")
    time_n = sum(1 for r in records if r["case_type"] == "time")
    assert shopping >= 250, f"购物记录应不少于 250 条，当前 {shopping}"
    assert time_n >= 250, f"时间记录应不少于 250 条，当前 {time_n}"

    required = {"id", "title", "content", "source", "case_type", "tags", "created_at"}
    for record in records:
        assert required.issubset(record.keys()), f"记录缺字段: {required - record.keys()}"
        assert isinstance(record.get("tags"), list), "tags 必须为列表"
        assert record.get("content"), "content 不能为空"


def test_rag_time_scenario_hit():
    """
    新增验收：时间决策场景（如“参加技术分享/社团活动”）应能正常召回且类型隔离正确。
    """
    for query in ["参加技术分享", "参加社团活动"]:
        payload = {
            "user_id": "u001",
            "case_id": "case_004",
            "case_type": "time",
            "query": query,
            "top_k": 3
        }
        results = results_for(payload)
        assert len(results) > 0, f"时间检索 '{query}' 未命中历史记录"
        assert all(r["case_type"] == "time" for r in results), "检索结果混入了非时间类型"
        for r in results:
            for key in ("id", "title", "content", "score", "source", "case_type", "tags"):
                assert key in r, f"检索结果缺少 RagEvidence 字段 {key}"
        print(f"\n✅ 时间检索 '{query}' 命中 {len(results)} 条")


def test_rag_results_only_rag_evidence_fields():
    """
    检索结果必须只暴露 RagEvidence 契约字段（docs/04_API.md §5.4），
    不允许泄漏 case_id/report_id/price/pros/cons 等内部字段。
    """
    payload = {
        "user_id": "u001",
        "case_id": "case_005",
        "case_type": "shopping",
        "query": "降噪耳机 学习",
        "top_k": 3,
    }
    results = results_for(payload)
    assert len(results) > 0, "应至少命中一条购物记录"

    expected = {"id", "title", "content", "score", "source", "case_type", "tags", "created_at"}
    for r in results:
        assert set(r.keys()) == expected, f"返回字段与 RagEvidence 契约不一致: {sorted(r.keys())}"
        assert isinstance(r["tags"], list), "tags 必须为列表"
        assert all(isinstance(t, str) for t in r["tags"]), "tags 必须全部为字符串"
        assert isinstance(r["score"], (int, float)), "score 必须为数值"
        assert r["created_at"] is None or isinstance(r["created_at"], str), "created_at 必须为字符串或 null"
