# tests/test_tools_router.py
"""E 模块 MCP 工具 HTTP 接口联调测试。

覆盖 docs/04_API.md §11 的 MCP 工具接口：
- POST /api/tools/cost-analyzer
- POST /api/tools/cooling-reminder
"""

from backend.models import Reminder


def test_cost_analyzer_shopping_success(client):
    """购物成本分析接口成功返回 ToolResult。"""
    resp = client.post(
        "/api/tools/cost-analyzer",
        json={
            "case_type": "shopping",
            "price": 1200,
            "monthly_budget_left": 2000,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    data = body["data"]
    assert data["tool_name"] == "cost_analyzer"
    assert data["status"] == "success"
    assert data["risk_level"] == "medium"
    assert data["metrics"]["budget_ratio"] == 0.6
    assert data["metrics"]["budget_left_after_purchase"] == 800
    assert data["error"] is None


def test_cost_analyzer_shopping_missing_args(client):
    """shopping 缺参数时返回 success=False 的提示信息。"""
    resp = client.post(
        "/api/tools/cost-analyzer",
        json={"case_type": "shopping", "price": 100},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is False
    assert "price" in body["message"] and "monthly_budget_left" in body["message"]


def test_cost_analyzer_time_success(client):
    """时间成本分析接口成功，返回高风险。"""
    resp = client.post(
        "/api/tools/cost-analyzer",
        json={
            "case_type": "time",
            "hours_required": 16,
            "free_hours_this_week": 20,
            "urgent_tasks": 2,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["tool_name"] == "cost_analyzer"
    assert body["data"]["status"] == "success"
    assert body["data"]["risk_level"] == "high"
    assert body["data"]["metrics"]["time_ratio"] == 0.8


def test_cost_analyzer_unsupported_case_type(client):
    """非法 case_type 返回 UNSUPPORTED_CASE_TYPE。"""
    resp = client.post(
        "/api/tools/cost-analyzer",
        json={"case_type": "medical", "price": 100, "monthly_budget_left": 2000},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is False
    assert body["message"] == "UNSUPPORTED_CASE_TYPE"


def test_cooling_reminder_success_persists_to_db(client, db_session):
    """创建冷静期提醒成功，并写入 reminders 表（观察清单可查到）。"""
    # 先创建案件，满足 reminders.case_id 外键约束
    create_resp = client.post(
        "/api/cases",
        json={
            "user_id": "u001",
            "case_type": "shopping",
            "title": "买降噪耳机",
            "description": "想买一副 1299 元降噪耳机",
        },
    )
    assert create_resp.status_code == 200
    case_id = create_resp.json()["data"]["case_id"]

    resp = client.post(
        "/api/tools/cooling-reminder",
        json={
            "user_id": "u001",
            "case_id": case_id,
            "title": "降噪耳机冷静期复盘",
            "cooling_days": 3,
            "reason": "预算占比较高",
            "watch_items": ["是否仍然需要", "是否已有替代品"],
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    data = body["data"]
    assert data["tool_name"] == "cooling_reminder"
    assert data["status"] == "success"
    assert data["metrics"]["reminder_id"].startswith("r_")
    assert data["metrics"]["watch_items"] == ["是否仍然需要", "是否已有替代品"]

    # 验证写入数据库
    reminders = db_session.query(Reminder).filter(Reminder.case_id == case_id).all()
    assert len(reminders) == 1
    assert reminders[0].status == "waiting"
    assert reminders[0].title == "降噪耳机冷静期复盘"


def test_cooling_reminder_missing_user_id(client):
    """缺少 user_id 时返回 failed ToolResult。"""
    resp = client.post(
        "/api/tools/cooling-reminder",
        json={
            "user_id": "",
            "case_id": "case_001",
            "title": "测试",
            "cooling_days": 3,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    data = body["data"]
    assert data["tool_name"] == "cooling_reminder"
    assert data["status"] == "failed"
    # 按 docs/04_API.md §11 约定，失败时 error 统一为错误码，具体原因在 summary。
    assert data["error"] == "REMINDER_CREATE_FAILED"
    assert "user_id" in data["summary"]
