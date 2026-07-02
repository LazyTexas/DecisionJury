import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp_tools.cooling_reminder import create_reminder
from datetime import datetime, timedelta


def test_create_reminder_basic():
    """Happy path: create a 3-day reminder"""
    result = create_reminder(
        user_id="u001",
        case_id="case_001",
        title="降噪耳机冷静期复盘",
        days=3,
        reason="预算占比较高",
    )

    assert result["status"] == "scheduled"
    assert result["reminder_id"].startswith("r_")


def test_reminder_id_format():
    """reminder_id should start with r_ prefix"""
    result = create_reminder(user_id="u001", case_id="c001", title="test", days=1)
    rid = result["reminder_id"]
    assert rid.startswith("r_"), f"expected r_ prefix, got {rid}"


def test_due_at_is_future():
    """due_at should be in the future"""
    result = create_reminder(user_id="u001", case_id="c001", title="test", days=1)
    due = datetime.strptime(result["due_at"], "%Y-%m-%dT%H:%M:%S+08:00")
    now = datetime.now()
    # Should be ~1 day in the future (allow small delta for test execution time)
    assert due > now, f"due_at {due} is not in the future"
    assert due < now + timedelta(days=2), f"due_at {due} is too far in the future"


def test_default_days():
    """When days is not provided, default to 3"""
    result = create_reminder(user_id="u001", case_id="c001", title="test")
    due = datetime.strptime(result["due_at"], "%Y-%m-%dT%H:%M:%S+08:00")
    now = datetime.now()
    assert due > now + timedelta(days=2), "default should be at least 3 days"


def test_days_less_than_one():
    """days < 1 should be clamped to 1"""
    result = create_reminder(user_id="u001", case_id="c001", title="test", days=0)
    due = datetime.strptime(result["due_at"], "%Y-%m-%dT%H:%M:%S+08:00")
    now = datetime.now()
    assert due < now + timedelta(hours=26), "0 days should be clamped to 1 day"


def test_days_negative():
    """negative days should be clamped to 1"""
    result = create_reminder(user_id="u001", case_id="c001", title="test", days=-5)
    due = datetime.strptime(result["due_at"], "%Y-%m-%dT%H:%M:%S+08:00")
    now = datetime.now()
    assert due < now + timedelta(hours=26), "negative days should be clamped to 1 day"


def test_missing_user_id():
    """missing user_id should return error"""
    result = create_reminder(user_id="", case_id="c001", title="test", days=3)
    assert result["status"] == "error"


def test_missing_case_id():
    """missing case_id should return error"""
    result = create_reminder(user_id="u001", case_id="", title="test", days=3)
    assert result["status"] == "error"


def test_create_and_validate_keys():
    """Ensure all expected keys are present"""
    result = create_reminder(user_id="u001", case_id="c001", title="冷静测试", days=2, reason="测试用")
    assert "reminder_id" in result
    assert "due_at" in result
    assert "status" in result
    assert result["status"] == "scheduled"
