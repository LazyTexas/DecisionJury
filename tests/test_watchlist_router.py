# tests/test_watchlist_router.py
"""
测试 watchlist 路由（GET /api/watchlist）
"""

from backend.models import Reminder
import datetime


def test_get_watchlist_success(client, db_session):
    """查询观察清单成功"""
    reminder = Reminder(
        id="reminder_001",
        user_id="u001",
        case_id="case_001",
        title="购买降噪耳机",
        reason="预算占比较高，建议冷静3天",
        due_at=datetime.datetime.now() + datetime.timedelta(days=3),
        status="waiting"
    )
    db_session.add(reminder)
    db_session.commit()

    response = client.get("/api/watchlist?user_id=u001")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert len(data["data"]["items"]) >= 1
    item = data["data"]["items"][0]
    assert item["case_id"] == "case_001"
    assert item["title"] == "购买降噪耳机"
    assert item["status"] == "waiting"


def test_get_watchlist_only_waiting(client, db_session):
    """只返回 waiting 状态的记录"""
    reminder1 = Reminder(
        id="reminder_waiting",
        user_id="u002",
        case_id="case_001",
        title="等待中",
        reason="冷静期",
        due_at=datetime.datetime.now() + datetime.timedelta(days=3),
        status="waiting"
    )
    reminder2 = Reminder(
        id="reminder_reviewed",
        user_id="u002",
        case_id="case_002",
        title="已复盘",
        reason="已复盘",
        due_at=datetime.datetime.now() - datetime.timedelta(days=1),
        status="reviewed"
    )
    reminder3 = Reminder(
        id="reminder_cancelled",
        user_id="u002",
        case_id="case_003",
        title="已取消",
        reason="已取消",
        due_at=datetime.datetime.now() + datetime.timedelta(days=1),
        status="cancelled"
    )
    db_session.add(reminder1)
    db_session.add(reminder2)
    db_session.add(reminder3)
    db_session.commit()

    response = client.get("/api/watchlist?user_id=u002")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert len(data["data"]["items"]) == 1
    assert data["data"]["items"][0]["case_id"] == "case_001"
    assert data["data"]["items"][0]["status"] == "waiting"


def test_get_watchlist_empty(client):
    """无数据返回空列表"""
    response = client.get("/api/watchlist?user_id=u_empty")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["items"] == []


def test_get_watchlist_sorted_by_due_at(client, db_session):
    """按 due_at 升序排列（即将到期的最先显示）"""
    reminder1 = Reminder(
        id="reminder_later",
        user_id="u003",
        case_id="case_001",
        title="晚到期",
        reason="晚",
        due_at=datetime.datetime.now() + datetime.timedelta(days=10),
        status="waiting"
    )
    reminder2 = Reminder(
        id="reminder_soon",
        user_id="u003",
        case_id="case_002",
        title="早到期",
        reason="早",
        due_at=datetime.datetime.now() + datetime.timedelta(days=1),
        status="waiting"
    )
    db_session.add(reminder1)
    db_session.add(reminder2)
    db_session.commit()

    response = client.get("/api/watchlist?user_id=u003")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    # 最近到期的应该排在最前面
    assert data["data"]["items"][0]["case_id"] == "case_002"
    assert data["data"]["items"][1]["case_id"] == "case_001"


def test_get_watchlist_missing_user_id(client):
    """缺少 user_id 返回验证错误"""
    response = client.get("/api/watchlist")

    assert response.status_code == 422
    data = response.json()
    assert data["success"] is False
    assert data["message"] == "VALIDATION_ERROR"