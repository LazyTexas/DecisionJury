# tests/test_chat_router.py
"""
测试 chat 路由（POST /api/cases/{case_id}/messages）
"""

import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.database import SessionLocal
from backend.models import Case, Message
from backend.schemas import CaseStatus

client = TestClient(app)


@pytest.fixture(scope="function")
def db_session():
    """提供数据库会话，测试结束后回滚"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()


def _create_test_case(
    db,
    case_id="case_chat_test",
    user_id="u001",
    case_type="shopping",
    title="买耳机",
    description="想买个降噪耳机",
    status=CaseStatus.COLLECTING,
    collected_fields=None,
    missing_fields=None,
):
    """辅助函数：直接插入测试案件"""
    case = Case(
        id=case_id,
        user_id=user_id,
        case_type=case_type,
        title=title,
        description=description,
        status=status,
        collected_fields=collected_fields or {"description": description},
        missing_fields=missing_fields or ["monthly_budget_left", "owned_alternatives"],
    )
    db.add(case)
    db.commit()
    db.refresh(case)
    return case


def test_messages_case_not_found(client):
    """不存在的 case_id 返回 CASE_NOT_FOUND"""
    response = client.post(
        "/api/cases/case_not_exist/messages",
        json={
            "user_id": "u001",
            "message": "预算还剩 1000 元",
        }
    )
    body = response.json()
    assert body["success"] is False
    assert body["message"] == "CASE_NOT_FOUND"


def test_messages_extracts_budget(client, db_session):
    """消息包含'预算'和数字时，正确提取 monthly_budget_left"""
    _create_test_case(db_session)

    response = client.post(
        "/api/cases/case_chat_test/messages",
        json={
            "user_id": "u001",
            "message": "我的预算还剩 2000 元",
        }
    )
    body = response.json()
    assert body["success"] is True
    assert body["data"]["collected_fields"]["monthly_budget_left"] == 2000
    assert "monthly_budget_left" not in body["data"]["missing_fields"]


def test_messages_extracts_alternatives(client, db_session):
    """消息包含'已有'时，正确提取 owned_alternatives"""
    _create_test_case(db_session)

    response = client.post(
        "/api/cases/case_chat_test/messages",
        json={
            "user_id": "u001",
            "message": "我已有旧耳机可以替代",
        }
    )
    body = response.json()
    assert body["success"] is True
    assert "owned_alternatives" in body["data"]["collected_fields"]
    assert "owned_alternatives" not in body["data"]["missing_fields"]


def test_messages_transitions_to_ready(client, db_session):
    """补全所有字段后，status 变为 ready_for_debate"""
    _create_test_case(
        db_session,
        collected_fields={"description": "想买个降噪耳机"},
        missing_fields=["monthly_budget_left", "owned_alternatives"],
    )

    # 第一次：补充预算
    response1 = client.post(
        "/api/cases/case_chat_test/messages",
        json={
            "user_id": "u001",
            "message": "预算还剩 1000 元",
        }
    )
    body1 = response1.json()
    assert body1["success"] is True
    assert body1["data"]["case_status"] == CaseStatus.COLLECTING

    # 第二次：补充替代品
    response2 = client.post(
        "/api/cases/case_chat_test/messages",
        json={
            "user_id": "u001",
            "message": "已有旧耳机替代",
        }
    )
    body2 = response2.json()
    assert body2["success"] is True
    assert body2["data"]["case_status"] == CaseStatus.READY_FOR_DEBATE


def test_messages_still_collecting(client, db_session):
    """未补全关键字段时，status 保持 collecting"""
    _create_test_case(db_session)

    response = client.post(
        "/api/cases/case_chat_test/messages",
        json={
            "user_id": "u001",
            "message": "我随便说说",
        }
    )
    body = response.json()
    assert body["success"] is True
    assert body["data"]["case_status"] == CaseStatus.COLLECTING


def test_messages_preserves_existing_price(client, db_session):
    """已有 price 字段不被 budget 覆盖"""
    # 创建案件时预置 price
    case = _create_test_case(
        db_session,
        collected_fields={"description": "想买降噪耳机", "price": 1299},
        missing_fields=["monthly_budget_left", "owned_alternatives"],
    )

    response = client.post(
        f"/api/cases/{case.id}/messages",
        json={
            "user_id": "u001",
            "message": "预算还剩 3000 元，已有普通耳机",
        }
    )
    body = response.json()
    # price 应该保持 1299，不被 3000 覆盖
    assert body["data"]["collected_fields"]["price"] == 1299
    assert body["data"]["collected_fields"].get("monthly_budget_left") == 3000


def test_messages_returns_reply_and_fields(client, db_session):
    """响应包含 reply、case_status、collected_fields、missing_fields"""
    _create_test_case(db_session)

    response = client.post(
        "/api/cases/case_chat_test/messages",
        json={
            "user_id": "u001",
            "message": "预算还剩 800 元",
        }
    )
    body = response.json()
    assert body["success"] is True
    assert isinstance(body["data"]["reply"], str)
    assert "case_status" in body["data"]
    assert "collected_fields" in body["data"]
    assert "missing_fields" in body["data"]


def test_messages_saves_user_and_assistant_messages(client, db_session):
    """用户消息和助手消息都被保存到数据库"""
    _create_test_case(db_session)

    client.post(
        "/api/cases/case_chat_test/messages",
        json={
            "user_id": "u001",
            "message": "预算还剩 500 元",
        }
    )

    # 查询数据库验证
    messages = db_session.query(Message).filter(
        Message.case_id == "case_chat_test"
    ).all()
    roles = [m.role for m in messages]
    assert "user" in roles
    assert "assistant" in roles


def test_messages_extracts_multiple_fields(client, db_session):
    """一条消息同时提取多个字段"""
    _create_test_case(db_session)

    response = client.post(
        "/api/cases/case_chat_test/messages",
        json={
            "user_id": "u001",
            "message": "预算还剩 2000 元，已有普通耳机，每天都会用",
        }
    )
    body = response.json()
    collected = body["data"]["collected_fields"]
    assert collected.get("monthly_budget_left") == 2000
    assert "owned_alternatives" in collected
    assert body["data"]["case_status"] == CaseStatus.READY_FOR_DEBATE


def test_messages_missing_user_id(client, db_session):
    """缺少 user_id 时返回验证错误"""
    _create_test_case(db_session)

    response = client.post(
        "/api/cases/case_chat_test/messages",
        json={
            "message": "测试消息"
        }
    )
    assert response.status_code == 422
    body = response.json()
    assert body["success"] is False
    assert body["message"] == "VALIDATION_ERROR"


def test_messages_empty_message(client, db_session):
    """空消息不报错，正常处理"""
    _create_test_case(db_session)

    response = client.post(
        "/api/cases/case_chat_test/messages",
        json={
            "user_id": "u001",
            "message": ""
        }
    )
    body = response.json()
    assert body["success"] is True
    assert body["data"]["case_status"] == CaseStatus.COLLECTING