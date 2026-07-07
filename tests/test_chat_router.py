# tests/test_chat_router.py
"""Chat 路由 HTTP 端点测试"""

from backend.main import app
from backend.database import get_db as _get_db
from backend.models import Case


def _insert_case(client, user_id="u001", status="collecting",
                 collected_fields=None, missing_fields=None):
    """辅助：通过 DB 直接插入一条案例，返回 case_id。"""
    db = next(app.dependency_overrides[_get_db]())
    case = Case(
        id="case_chat01",
        user_id=user_id,
        case_type="shopping",
        title="买耳机",
        description="想买个降噪耳机",
        status=status,
        collected_fields=collected_fields or {"description": "想买个降噪耳机"},
        missing_fields=missing_fields or ["monthly_budget_left", "owned_alternatives"],
    )
    db.add(case)
    db.commit()
    return case.id


def test_chat_case_not_found(client):
    """不存在的 case_id 返回 CASE_NOT_FOUND。"""
    resp = client.post("/api/chat", json={
        "user_id": "u001",
        "case_id": "case_notexist",
        "message": "预算还剩 1000 元",
    })
    body = resp.json()
    assert body["success"] is False
    assert body["message"] == "CASE_NOT_FOUND"


def test_chat_extracts_budget(client):
    """消息含"预算"和数字时更新 monthly_budget_left。"""
    _insert_case(client)

    resp = client.post("/api/chat", json={
        "user_id": "u001",
        "case_id": "case_chat01",
        "message": "我的预算还剩 2000 元",
    })
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["collected_fields"]["monthly_budget_left"] == 2000
    assert "monthly_budget_left" not in body["data"]["missing_fields"]


def test_chat_extracts_alternatives(client):
    """消息含"已有"时更新 owned_alternatives。"""
    _insert_case(client)

    resp = client.post("/api/chat", json={
        "user_id": "u001",
        "case_id": "case_chat01",
        "message": "我已有旧耳机",
    })
    body = resp.json()
    assert body["success"] is True
    assert "owned_alternatives" in body["data"]["collected_fields"]
    assert "owned_alternatives" not in body["data"]["missing_fields"]


def test_chat_transitions_to_ready(client):
    """补全所有字段后 status 变为 ready_for_debate。"""
    _insert_case(
        client,
        collected_fields={"description": "想买个降噪耳机"},
        missing_fields=["monthly_budget_left", "owned_alternatives"],
    )

    # 先补预算
    resp1 = client.post("/api/chat", json={
        "user_id": "u001",
        "case_id": "case_chat01",
        "message": "预算还剩 1000 元",
    })
    # 再补替代
    resp2 = client.post("/api/chat", json={
        "user_id": "u001",
        "case_id": "case_chat01",
        "message": "已有旧耳机替代",
    })
    body = resp2.json()
    assert body["success"] is True
    assert body["data"]["case_status"] == "ready_for_debate"


def test_chat_still_collecting(client):
    """未补全字段时 status 仍为 collecting。"""
    _insert_case(client)

    resp = client.post("/api/chat", json={
        "user_id": "u001",
        "case_id": "case_chat01",
        "message": "我随便说说",
    })
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["case_status"] == "collecting"


def test_chat_removes_description_from_collected(client):
    """聊天时 description 键从 collected_fields 中移除。"""
    _insert_case(client)

    resp = client.post("/api/chat", json={
        "user_id": "u001",
        "case_id": "case_chat01",
        "message": "随便聊聊",
    })
    body = resp.json()
    assert "description" not in body["data"]["collected_fields"]


def test_chat_returns_reply_and_fields(client):
    """返回包含 reply、case_status、collected_fields、missing_fields。"""
    _insert_case(client)

    resp = client.post("/api/chat", json={
        "user_id": "u001",
        "case_id": "case_chat01",
        "message": "预算还剩 800 元",
    })
    body = resp.json()
    assert body["success"] is True
    assert isinstance(body["data"]["reply"], str)
    assert "case_status" in body["data"]
    assert "collected_fields" in body["data"]
    assert "missing_fields" in body["data"]


def test_chat_saves_user_message(client):
    """用户消息被保存到数据库。"""
    _insert_case(client)

    client.post("/api/chat", json={
        "user_id": "u001",
        "case_id": "case_chat01",
        "message": "预算还剩 500 元",
    })

    # 通过 DB 查询验证消息已保存
    from backend.models import Message
    db = next(app.dependency_overrides[_get_db]())
    messages = db.query(Message).filter(Message.case_id == "case_chat01").all()
    # 应该有 1 条用户消息 + 1 条助手消息
    roles = [m.role for m in messages]
    assert "user" in roles, "用户消息未保存"
    assert "assistant" in roles, "助手消息未保存"
