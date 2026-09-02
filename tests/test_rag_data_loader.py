import os
import sys

# 把 rag 目录加入系统路径，以便直接 import data_loader
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "rag")))

import data_loader  # noqa: E402


def test_normalize_backend_item_maps_b_fields():
    """
    B 后端 GET /api/history 返回的是 history_id + summary；
    RAG 检索需要 id + content + source，必须做字段映射。
    """
    item = {
        "history_id": "history_new_01",
        "user_id": "local_user",
        "case_type": "shopping",
        "title": "新买的平板电脑",
        "summary": "用户新买平板电脑用于学习，使用率高，值得。",
        "result": "worth",
        "tags": ["数码", "学习"],
        "case_id": "case_x",
        "report_id": "rep_x",
        "created_at": "2026-08-01T00:00:00+08:00",
    }

    record = data_loader._normalize_backend_item(item)

    assert record is not None
    assert record["id"] == "history_new_01"
    assert record["content"] == item["summary"]
    assert record["source"] == "decision_history"
    assert record["case_type"] == "shopping"
    assert record["title"] == "新买的平板电脑"
    assert record["tags"] == ["数码", "学习"]


def test_normalize_backend_item_skips_empty_summary():
    item = {"history_id": "x", "summary": "   ", "case_type": "shopping"}
    assert data_loader._normalize_backend_item(item) is None


def test_load_history_data_merges_static_and_live(monkeypatch):
    """静态种子 + 后端实时记录合并，且以 id 去重、实时优先。"""
    static = data_loader._read_static_records()
    assert len(static) >= 500, "静态种子应不少于 500 条"

    live = [
        data_loader._normalize_backend_item({
            "history_id": "history_live_001",
            "user_id": "local_user",
            "case_type": "shopping",
            "title": "实时新增的显示器",
            "summary": "刚提交复盘：显示器用于学习，使用率高，值得。",
            "result": "worth",
            "tags": ["数码", "学习"],
            "created_at": "2026-08-02T00:00:00+08:00",
        }),
    ]

    monkeypatch.setattr(data_loader, "fetch_backend_history", lambda user_id="local_user": live)

    merged = data_loader.load_history_data("local_user")

    ids = {r["id"] for r in merged}
    assert "history_live_001" in ids
    assert len(merged) >= len(static), "合并后记录数应不小于静态种子数"


def test_load_history_data_returns_static_when_live_empty(monkeypatch):
    """后端无数据/不可用时，应回退到静态种子，且不编造历史。"""
    monkeypatch.setattr(data_loader, "fetch_backend_history", lambda user_id="local_user": [])
    merged = data_loader.load_history_data("local_user")
    assert len(merged) >= 500


def test_fetch_backend_history_can_be_disabled(monkeypatch):
    """通过 RAG_LIVE_RECORDS=0 可关闭实时联动，用于离线/单测。"""
    monkeypatch.setenv("RAG_LIVE_RECORDS", "0")
    assert data_loader.fetch_backend_history("local_user") == []


def test_fetch_backend_history_maps_response_items(monkeypatch):
    """
    模拟 B 后端返回 data.items，验证 fetch_backend_history 能正确解包并映射。
    """
    payload = {
        "success": True,
        "data": {
            "items": [
                {
                    "history_id": "history_a1",
                    "user_id": "local_user",
                    "case_type": "time",
                    "title": "参加技术分享",
                    "summary": "参加技术分享收获大，值得。",
                    "result": "worth",
                    "tags": ["技能"],
                    "created_at": "2026-08-03T00:00:00+08:00",
                }
            ],
            "total": 1,
            "page": 1,
            "page_size": 1000,
        },
        "message": "",
    }

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self):
            import json
            return json.dumps(payload, ensure_ascii=False).encode("utf-8")

    monkeypatch.setenv("RAG_LIVE_RECORDS", "1")
    monkeypatch.setattr(
        data_loader.urllib.request, "urlopen", lambda url, timeout: FakeResponse()
    )

    records = data_loader.fetch_backend_history("local_user")
    assert len(records) == 1
    assert records[0]["id"] == "history_a1"
    assert records[0]["content"] == "参加技术分享收获大，值得。"
    assert records[0]["source"] == "decision_history"
