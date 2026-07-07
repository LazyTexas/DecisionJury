# tests/test_cases_router.py
"""Cases 路由 HTTP 端点测试"""

import re

from backend.main import app
from backend.database import get_db as _get_db


def test_create_case_success(client):
    """正常创建案例，返回 case_id，status 为 collecting。"""
    resp = client.post("/api/cases", json={
        "user_id": "u001",
        "case_type": "shopping",
        "title": "买耳机",
        "description": "想买个降噪耳机",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["case_id"].startswith("case_")
    assert body["data"]["case_status"] == "collecting"
    assert "description" in body["data"]["collected_fields"]


def test_create_case_ready_for_debate(client):
    """description 含 budget 和替代时，status 直接为 ready_for_debate。"""
    resp = client.post("/api/cases", json={
        "user_id": "u001",
        "case_type": "shopping",
        "title": "买耳机",
        "description": "想买降噪耳机，budget 还够，已有替代的旧耳机",
    })
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["case_status"] == "ready_for_debate"
    assert body["data"]["missing_fields"] == []


def test_create_case_missing_budget(client):
    """缺预算信息时 next_question 提示补充预算。"""
    resp = client.post("/api/cases", json={
        "user_id": "u001",
        "case_type": "shopping",
        "title": "买耳机",
        "description": "想买个降噪耳机",
    })
    body = resp.json()
    assert body["success"] is True
    assert "monthly_budget_left" in body["data"]["missing_fields"]
    assert body["data"]["next_question"] is not None


def test_create_case_generates_case_id(client):
    """case_id 格式为 case_{8位hex}。"""
    resp = client.post("/api/cases", json={
        "user_id": "u001",
        "case_type": "shopping",
        "title": "买耳机",
        "description": "想买个降噪耳机",
    })
    case_id = resp.json()["data"]["case_id"]
    assert re.match(r"^case_[0-9a-f]{8}$", case_id), f"case_id 格式不正确: {case_id}"


def test_get_case_found(client):
    """创建后能通过 GET 查到，字段完整。"""
    create_resp = client.post("/api/cases", json={
        "user_id": "u001",
        "case_type": "shopping",
        "title": "买耳机",
        "description": "想买个降噪耳机",
    })
    case_id = create_resp.json()["data"]["case_id"]

    resp = client.get(f"/api/cases/{case_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    data = body["data"]
    assert data["case_id"] == case_id
    assert data["user_id"] == "u001"
    assert data["case_type"] == "shopping"
    assert data["title"] == "买耳机"
    assert "case_status" in data
    assert "collected_fields" in data
    assert "missing_fields" in data


def test_get_case_not_found(client):
    """查询不存在的 case_id 返回 CASE_NOT_FOUND。"""
    resp = client.get("/api/cases/case_notexist")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is False
    assert body["message"] == "CASE_NOT_FOUND"


def test_list_cases(client):
    """创建案例后列表能查到，包含分页数据。"""
    client.post("/api/cases", json={
        "user_id": "u001",
        "case_type": "shopping",
        "title": "买耳机",
        "description": "想买个降噪耳机",
    })

    resp = client.get("/api/cases", params={"user_id": "u001"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["total"] >= 1
    assert len(body["data"]["items"]) >= 1
    item = body["data"]["items"][0]
    assert "case_id" in item
    assert "title" in item
    assert "status" in item
    assert "message_count" in item
    assert "has_report" in item


def test_list_cases_pagination(client):
    """分页参数正确生效。"""
    # 创建 3 个案例
    for i in range(3):
        client.post("/api/cases", json={
            "user_id": "u002",
            "case_type": "shopping",
            "title": f"买物品{i}",
            "description": f"想买物品{i}",
        })

    # 每页 2 条
    resp = client.get("/api/cases", params={"user_id": "u002", "page": 1, "page_size": 2})
    body = resp.json()
    assert body["data"]["page"] == 1
    assert body["data"]["page_size"] == 2
    assert len(body["data"]["items"]) == 2
    assert body["data"]["total"] == 3


def test_list_cases_empty(client):
    """无数据的用户返回空列表。"""
    resp = client.get("/api/cases", params={"user_id": "u_empty"})
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["total"] == 0
    assert body["data"]["items"] == []


def test_get_report_case_not_found(client):
    """不存在的 case 查报告返回 CASE_NOT_FOUND。"""
    resp = client.get("/api/cases/case_notexist/report")
    body = resp.json()
    assert body["success"] is False
    assert body["message"] == "CASE_NOT_FOUND"


def test_get_report_not_found(client):
    """无 report_id 的案例查报告返回 REPORT_NOT_FOUND。"""
    create_resp = client.post("/api/cases", json={
        "user_id": "u001",
        "case_type": "shopping",
        "title": "买耳机",
        "description": "想买个降噪耳机",
    })
    case_id = create_resp.json()["data"]["case_id"]

    resp = client.get(f"/api/cases/{case_id}/report")
    body = resp.json()
    assert body["success"] is False
    assert body["message"] == "REPORT_NOT_FOUND"


def test_get_report_success(client):
    """有 report_id 的案例查报告返回完整报告，confidence 为 MVP 固定值 0.75。"""
    # 直接通过 DB 插入一个有 report_id 的案例
    from backend.models import Case

    # 用 override 的 get_db 获取 session
    db = next(app.dependency_overrides[_get_db]())

    case = Case(
        id="case_report01",
        user_id="u001",
        case_type="shopping",
        title="买耳机",
        description="想买个降噪耳机",
        status="completed",
        collected_fields={},
        missing_fields=[],
        final_decision="buy",
        report_id="report_test01",
    )
    db.add(case)
    db.commit()

    resp = client.get("/api/cases/case_report01/report")
    body = resp.json()
    assert body["success"] is True
    data = body["data"]
    assert data["report_id"] == "report_test01"
    assert data["final_decision"] == "buy"
    assert data["confidence"] == 0.75
    assert "summary" in data
    assert isinstance(data["pro_points"], list)
    assert isinstance(data["con_points"], list)
