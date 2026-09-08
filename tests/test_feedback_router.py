# tests/test_feedback_router.py
"""
测试 feedback 路由（POST /api/cases/{case_id}/feedback）
"""

from backend.models import Case, History, Reminder
from backend.schemas import CaseStatus
import datetime


def test_feedback_success(client, db_session):
    """提交反馈成功"""
    case = Case(
        id="case_feedback",
        user_id="u001",
        case_type="shopping",
        title="买耳机",
        description="想买降噪耳机",
        status=CaseStatus.COMPLETED,
        final_decision="delay",
        report_id="report_001",
        collected_fields={},
        missing_fields=[]
    )
    db_session.add(case)
    db_session.commit()

    response = client.post(
        "/api/cases/case_feedback/feedback",
        json={
            "user_id": "u001",
            "actual_action": "bought",
            "satisfaction": 4,
            "review": "冷静三天后发现确实需要，使用体验很好。"
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["saved_to_history"] is True
    assert "history_id" in data["data"]

    # 验证历史记录已创建
    history = db_session.query(History).filter(History.id == data["data"]["history_id"]).first()
    assert history is not None
    assert history.user_id == "u001"
    assert history.result == "worth"  # 4分 → worth


def test_feedback_case_not_found(client):
    """案件不存在返回 CASE_NOT_FOUND"""
    response = client.post(
        "/api/cases/case_not_exist/feedback",
        json={
            "user_id": "u001",
            "actual_action": "bought",
            "satisfaction": 4
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert data["message"] == "CASE_NOT_FOUND"


def test_feedback_not_completed(client, db_session):
    """案件未完成返回 CASE_NOT_COMPLETED"""
    case = Case(
        id="case_not_completed",
        user_id="u001",
        case_type="shopping",
        title="买耳机",
        description="想买降噪耳机",
        status=CaseStatus.COLLECTING,
        collected_fields={},
        missing_fields=[]
    )
    db_session.add(case)
    db_session.commit()

    response = client.post(
        "/api/cases/case_not_completed/feedback",
        json={
            "user_id": "u001",
            "actual_action": "bought",
            "satisfaction": 4
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert data["message"] == "CASE_NOT_COMPLETED"


def test_feedback_satisfaction_5_to_worth(client, db_session):
    """满意度 5 分映射为 worth"""
    case = Case(
        id="case_sat5",
        user_id="u001",
        case_type="shopping",
        title="买耳机",
        description="想买降噪耳机",
        status=CaseStatus.COMPLETED,
        final_decision="buy",
        report_id="report_001",
        collected_fields={},
        missing_fields=[]
    )
    db_session.add(case)
    db_session.commit()

    response = client.post(
        "/api/cases/case_sat5/feedback",
        json={
            "user_id": "u001",
            "actual_action": "bought",
            "satisfaction": 5,
            "review": "非常满意"
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    history_id = data["data"]["history_id"]
    history = db_session.query(History).filter(History.id == history_id).first()
    assert history.result == "worth"


def test_feedback_satisfaction_3_to_neutral(client, db_session):
    """满意度 3 分映射为 neutral"""
    case = Case(
        id="case_sat3",
        user_id="u001",
        case_type="shopping",
        title="买耳机",
        description="想买降噪耳机",
        status=CaseStatus.COMPLETED,
        final_decision="buy",
        report_id="report_001",
        collected_fields={},
        missing_fields=[]
    )
    db_session.add(case)
    db_session.commit()

    response = client.post(
        "/api/cases/case_sat3/feedback",
        json={
            "user_id": "u001",
            "actual_action": "bought",
            "satisfaction": 3
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    history_id = data["data"]["history_id"]
    history = db_session.query(History).filter(History.id == history_id).first()
    assert history.result == "neutral"


def test_feedback_satisfaction_2_to_regret(client, db_session):
    """满意度 2 分映射为 regret"""
    case = Case(
        id="case_sat2",
        user_id="u001",
        case_type="shopping",
        title="买耳机",
        description="想买降噪耳机",
        status=CaseStatus.COMPLETED,
        final_decision="buy",
        report_id="report_001",
        collected_fields={},
        missing_fields=[]
    )
    db_session.add(case)
    db_session.commit()

    response = client.post(
        "/api/cases/case_sat2/feedback",
        json={
            "user_id": "u001",
            "actual_action": "bought",
            "satisfaction": 2
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    history_id = data["data"]["history_id"]
    history = db_session.query(History).filter(History.id == history_id).first()
    assert history.result == "regret"


def test_feedback_updates_reminder_status(client, db_session):
    """提交反馈后观察清单状态更新为 reviewed"""
    case = Case(
        id="case_with_reminder",
        user_id="u001",
        case_type="shopping",
        title="买耳机",
        description="想买降噪耳机",
        status=CaseStatus.COMPLETED,
        final_decision="delay",
        report_id="report_001",
        collected_fields={},
        missing_fields=[]
    )
    db_session.add(case)

    reminder = Reminder(
        id="reminder_test",
        user_id="u001",
        case_id="case_with_reminder",
        title="降噪耳机冷静期",
        reason="冷静期",
        due_at=datetime.datetime.now() + datetime.timedelta(days=3),
        status="waiting"
    )
    db_session.add(reminder)
    db_session.commit()

    response = client.post(
        "/api/cases/case_with_reminder/feedback",
        json={
            "user_id": "u001",
            "actual_action": "not_bought",
            "satisfaction": 5,
            "review": "冷静后决定不买"
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True

    # 验证观察清单状态已更新
    updated_reminder = db_session.query(Reminder).filter(Reminder.id == "reminder_test").first()
    assert updated_reminder.status == "reviewed"


def test_feedback_review_optional(client, db_session):
    """review 字段选填，不填也能提交"""
    case = Case(
        id="case_no_review",
        user_id="u001",
        case_type="shopping",
        title="买耳机",
        description="想买降噪耳机",
        status=CaseStatus.COMPLETED,
        final_decision="delay",
        report_id="report_001",
        collected_fields={},
        missing_fields=[]
    )
    db_session.add(case)
    db_session.commit()

    response = client.post(
        "/api/cases/case_no_review/feedback",
        json={
            "user_id": "u001",
            "actual_action": "bought",
            "satisfaction": 4
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["saved_to_history"] is True


def test_feedback_missing_user_id(client, db_session):
    """缺少 user_id 返回验证错误"""
    case = Case(
        id="case_test",
        user_id="u001",
        case_type="shopping",
        title="买耳机",
        description="想买降噪耳机",
        status=CaseStatus.COMPLETED,
        collected_fields={},
        missing_fields=[]
    )
    db_session.add(case)
    db_session.commit()

    response = client.post(
        "/api/cases/case_test/feedback",
        json={
            "actual_action": "bought",
            "satisfaction": 4
        }
    )

    assert response.status_code == 422
    data = response.json()
    assert data["success"] is False
    assert data["message"] == "VALIDATION_ERROR"