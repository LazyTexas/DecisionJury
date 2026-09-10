# tests/test_chat_router.py
"""
测试 chat 路由
- POST /api/cases/{case_id}/messages（发送消息）
- GET  /api/cases/{case_id}/messages（消息列表）
"""

from datetime import datetime, timedelta

from backend.models import Case, Message
from backend.schemas import CaseStatus

# client / db_session 统一由 tests/conftest.py 提供（内存 SQLite + get_db 依赖覆盖）。
# 原先本文件自建的 db_session 用真实 SessionLocal，指向 data/decisionjury.db，
# 与 conftest 的 TestClient 用的内存库不是同一个数据库，用例必然失败。


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


def test_messages_marks_savings_budget_source(client, db_session):
    """回归：用户原话"我自己攒有1000块钱，不影响日常支出"要标成 savings。

    这是真实测试里出现过的一句话：当时关键词表只列了"攒了/攒下"等固定搭配，
    没有覆盖"攒有"，金额被当成月预算，899/1000 被判 high → reject。
    """
    _create_test_case(db_session)

    response = client.post(
        "/api/cases/case_chat_test/messages",
        json={
            "user_id": "u001",
            "message": "我自己攒有1000块钱，不影响日常支出",
        }
    )
    body = response.json()
    assert body["success"] is True
    collected = body["data"]["collected_fields"]
    assert collected["monthly_budget_left"] == 1000
    assert collected["budget_source"] == "savings"


def test_messages_marks_monthly_budget_source(client, db_session):
    """对照：明确的月预算表达仍标成 monthly_budget。"""
    _create_test_case(db_session)

    response = client.post(
        "/api/cases/case_chat_test/messages",
        json={
            "user_id": "u001",
            "message": "本月预算还剩1000元",
        }
    )
    body = response.json()
    assert body["success"] is True
    collected = body["data"]["collected_fields"]
    assert collected["monthly_budget_left"] == 1000
    assert collected["budget_source"] == "monthly_budget"


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
    """补齐最小决策字段（商品/价格/预算）后，status 变为 ready_for_debate"""
    _create_test_case(
        db_session,
        collected_fields={"description": "想买个降噪耳机"},
        missing_fields=["price", "monthly_budget_left"],
    )

    # 第一次：补充商品与价格 -> 仍缺预算
    response1 = client.post(
        "/api/cases/case_chat_test/messages",
        json={
            "user_id": "u001",
            "message": "想买降噪耳机，价格 800 元",
        }
    )
    body1 = response1.json()
    assert body1["success"] is True
    assert body1["data"]["case_status"] == CaseStatus.COLLECTING

    # 第二次：补充预算 -> 达到最小决策字段
    response2 = client.post(
        "/api/cases/case_chat_test/messages",
        json={
            "user_id": "u001",
            "message": "预算还剩 1000 元",
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
    """一条消息同时提取多个字段，并达到最小决策字段"""
    _create_test_case(db_session)

    response = client.post(
        "/api/cases/case_chat_test/messages",
        json={
            "user_id": "u001",
            "message": "想买降噪耳机，预算还剩 2000 元，价格 800 元，已有普通耳机，每天都会用",
        }
    )
    body = response.json()
    collected = body["data"]["collected_fields"]
    assert collected.get("product_name")
    assert collected.get("price") == 800
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

def test_messages_price_correction(client, db_session):
    """测试价格纠正"""
    case = Case(
        id="case_correction",
        user_id="u001",
        case_type="shopping",
        title="买耳机",
        description="想买降噪耳机，1299元",
        status=CaseStatus.COLLECTING,
        collected_fields={"price": 1299, "product_name": "降噪耳机"},
        missing_fields=["monthly_budget_left", "owned_alternatives"]
    )
    db_session.add(case)
    db_session.commit()

    response = client.post(
        f"/api/cases/case_correction/messages",
        json={
            "user_id": "u001",
            "message": "刚才价格说错了，不是1299，是999。"
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert data["data"]["collected_fields"]["price"] == 999


def test_messages_budget_correction(client, db_session):
    """测试预算纠正"""
    case = Case(
        id="case_budget_correction",
        user_id="u001",
        case_type="shopping",
        title="买耳机",
        description="想买降噪耳机，1299元",
        status=CaseStatus.COLLECTING,
        collected_fields={"price": 1299, "monthly_budget_left": 3000},
        missing_fields=["owned_alternatives"]
    )
    db_session.add(case)
    db_session.commit()

    response = client.post(
        f"/api/cases/case_budget_correction/messages",
        json={
            "user_id": "u001",
            "message": "预算不是3000，是2500。"
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert data["data"]["collected_fields"]["monthly_budget_left"] == 2500
    # 确保 price 没有被错误覆盖
    assert data["data"]["collected_fields"]["price"] == 1299


# ============================================================
# GET /api/cases/{case_id}/messages —— 消息列表
# 契约：Query 参数 user_id（必填）、page（>=1）、page_size（1~100）；
# 返回 data.items[{id, session_id, role, type, content, created_at}]、total、page、page_size
# ============================================================

def _add_message(db, message_id, content, role="user", case_id="case_chat_test",
                 offset_seconds=0, message_type="text"):
    """辅助：插入一条带确定时间戳的消息，保证排序断言稳定。"""
    message = Message(
        id=message_id,
        case_id=case_id,
        role=role,
        content=content,
        message_type=message_type,
        created_at=datetime(2026, 1, 1, 12, 0, 0) + timedelta(seconds=offset_seconds),
    )
    db.add(message)
    db.commit()
    return message


def test_get_messages_success(client, db_session):
    """按创建时间升序返回消息列表，字段与契约一致"""
    _create_test_case(db_session)
    _add_message(db_session, "msg_001", "想买降噪耳机", role="user", offset_seconds=0)
    _add_message(db_session, "msg_002", "请补充预算", role="assistant", offset_seconds=1)

    response = client.get("/api/cases/case_chat_test/messages", params={"user_id": "u001"})

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    data = body["data"]
    assert data["total"] == 2
    assert data["page"] == 1
    assert data["page_size"] == 20
    assert [m["id"] for m in data["items"]] == ["msg_001", "msg_002"]
    first = data["items"][0]
    assert first["session_id"] == "case_chat_test"
    assert first["role"] == "user"
    assert first["type"] == "text"
    assert first["content"] == "想买降噪耳机"
    assert first["created_at"]


def test_get_messages_empty(client, db_session):
    """没有消息时返回空列表而不是报错"""
    _create_test_case(db_session)

    response = client.get("/api/cases/case_chat_test/messages", params={"user_id": "u001"})

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["items"] == []
    assert data["total"] == 0


def test_get_messages_pagination(client, db_session):
    """分页参数生效，且 total 为全量条数"""
    _create_test_case(db_session)
    for index in range(3):
        _add_message(db_session, f"msg_{index}", f"消息{index}", offset_seconds=index)

    page1 = client.get(
        "/api/cases/case_chat_test/messages",
        params={"user_id": "u001", "page": 1, "page_size": 2},
    ).json()["data"]
    assert page1["total"] == 3
    assert page1["page"] == 1
    assert page1["page_size"] == 2
    assert [m["id"] for m in page1["items"]] == ["msg_0", "msg_1"]

    page2 = client.get(
        "/api/cases/case_chat_test/messages",
        params={"user_id": "u001", "page": 2, "page_size": 2},
    ).json()["data"]
    assert page2["total"] == 3
    assert [m["id"] for m in page2["items"]] == ["msg_2"]


def test_get_messages_case_not_found(client):
    """案件不存在返回 CASE_NOT_FOUND"""
    response = client.get("/api/cases/case_not_exist/messages", params={"user_id": "u001"})

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is False
    assert body["message"] == "CASE_NOT_FOUND"


def test_get_messages_forbidden_for_other_user(client, db_session):
    """非本人案件返回 FORBIDDEN，不泄漏消息内容"""
    _create_test_case(db_session)
    _add_message(db_session, "msg_001", "想买降噪耳机")

    response = client.get("/api/cases/case_chat_test/messages", params={"user_id": "u002"})

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is False
    assert body["message"] == "FORBIDDEN"


def test_get_messages_missing_user_id(client, db_session):
    """缺少 user_id 且无 Token 时返回 MISSING_USER_ID（HTTP 200 + 业务错误码）"""
    _create_test_case(db_session)

    response = client.get("/api/cases/case_chat_test/messages")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is False
    assert body["message"] == "MISSING_USER_ID"


def test_get_messages_invalid_page_params(client, db_session):
    """page / page_size 越界时返回验证错误"""
    _create_test_case(db_session)

    for params in ({"page": 0}, {"page_size": 0}, {"page_size": 101}):
        response = client.get(
            "/api/cases/case_chat_test/messages",
            params={"user_id": "u001", **params},
        )
        assert response.status_code == 422, params