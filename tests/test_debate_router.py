# tests/test_debate_router.py
"""Debate 路由 HTTP 端点测试"""

from typing import Any

from backend.main import app
from backend.database import get_db as _get_db
from backend.models import Case


def _insert_case(client, status="ready_for_debate", collected_fields=None):
    """辅助：通过 DB 直接插入一条案例，返回 case_id。"""
    db = next(app.dependency_overrides[_get_db]())
    case = Case(
        id="case_debate01",
        user_id="u001",
        case_type="shopping",
        title="买耳机",
        description="想买个降噪耳机",
        status=status,
        collected_fields=collected_fields or {"description": "想买个降噪耳机"},
        missing_fields=[] if status == "ready_for_debate" else ["monthly_budget_left"],
    )
    db.add(case)
    db.commit()
    return case.id


def _fake_flow_success(*args, **kwargs) -> dict[str, Any]:
    """mock：辩论成功。"""
    return {
        "success": True,
        "message": "debate completed",
        "case_status": "completed",
        "steps": [],
        "rag_evidence": [],
        "tool_results": [],
        "report": {
            "final_decision": "buy",
            "report_id": "report_debate01",
        },
    }


def _fake_flow_high_risk(*args, **kwargs) -> dict[str, Any]:
    """mock：高风险拒绝。"""
    return {
        "success": False,
        "message": "HIGH_RISK_DECISION",
        "case_status": "rejected",
    }


def _fake_flow_missing_fields(*args, **kwargs) -> dict[str, Any]:
    """mock：字段缺失。"""
    return {
        "success": False,
        "message": "MISSING_FIELDS",
        "case_status": "collecting",
        "reason": "缺少预算信息",
    }


def _fake_flow_generic_failure(*args, **kwargs) -> dict[str, Any]:
    """mock：通用失败。"""
    return {
        "success": False,
        "message": "INTERNAL_ERROR",
    }


def test_debate_case_not_found(client):
    """不存在的 case_id 返回 CASE_NOT_FOUND。"""
    resp = client.post("/api/cases/case_notexist/debate")
    body = resp.json()
    assert body["success"] is False
    assert body["message"] == "CASE_NOT_FOUND"


def test_debate_rejected_case(client, monkeypatch):
    """status=rejected 的案例返回 HIGH_RISK_DECISION。"""
    monkeypatch.setattr("backend.routers.debate.run_case_decision_flow", _fake_flow_success)
    _insert_case(client, status="rejected")

    resp = client.post("/api/cases/case_debate01/debate")
    body = resp.json()
    assert body["success"] is False
    assert body["message"] == "HIGH_RISK_DECISION"


def test_debate_not_ready(client, monkeypatch):
    """status=collecting 的案例返回 MISSING_FIELDS。"""
    monkeypatch.setattr("backend.routers.debate.run_case_decision_flow", _fake_flow_success)
    _insert_case(client, status="collecting")

    resp = client.post("/api/cases/case_debate01/debate")
    body = resp.json()
    assert body["success"] is False
    assert body["message"] == "MISSING_FIELDS"


def test_debate_success(client, monkeypatch):
    """mock 辩论成功，status 变为 completed。"""
    monkeypatch.setattr("backend.routers.debate.run_case_decision_flow", _fake_flow_success)
    _insert_case(client, status="ready_for_debate")

    resp = client.post("/api/cases/case_debate01/debate")
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["case_status"] == "completed"
    assert body["data"]["report"]["final_decision"] == "buy"
    assert body["data"]["report"]["report_id"] == "report_debate01"

    # 验证数据库中 case 状态已更新
    db = next(app.dependency_overrides[_get_db]())
    case = db.query(Case).filter(Case.id == "case_debate01").first()
    assert case.status == "completed"
    assert case.final_decision == "buy"
    assert case.report_id == "report_debate01"


def test_debate_high_risk_result(client, monkeypatch):
    """mock 返回 HIGH_RISK_DECISION，status 变为 rejected。"""
    monkeypatch.setattr("backend.routers.debate.run_case_decision_flow", _fake_flow_high_risk)
    _insert_case(client, status="ready_for_debate")

    resp = client.post("/api/cases/case_debate01/debate")
    body = resp.json()
    assert body["success"] is False
    assert body["message"] == "HIGH_RISK_DECISION"

    # 验证数据库中 case 状态已更新
    db = next(app.dependency_overrides[_get_db]())
    case = db.query(Case).filter(Case.id == "case_debate01").first()
    assert case.status == "rejected"


def test_debate_missing_fields_result(client, monkeypatch):
    """mock 返回 MISSING_FIELDS，status 回退为 collecting。"""
    monkeypatch.setattr("backend.routers.debate.run_case_decision_flow", _fake_flow_missing_fields)
    _insert_case(client, status="ready_for_debate")

    resp = client.post("/api/cases/case_debate01/debate")
    body = resp.json()
    assert body["success"] is False
    assert body["message"] == "MISSING_FIELDS"
    assert body["data"]["case_status"] == "collecting"

    # 验证数据库中 case 状态已回退
    db = next(app.dependency_overrides[_get_db]())
    case = db.query(Case).filter(Case.id == "case_debate01").first()
    assert case.status == "collecting"


def test_debate_generic_failure(client, monkeypatch):
    """mock 返回通用失败，返回 DEBATE_FAILED 或对应 message。"""
    monkeypatch.setattr("backend.routers.debate.run_case_decision_flow", _fake_flow_generic_failure)
    _insert_case(client, status="ready_for_debate")

    resp = client.post("/api/cases/case_debate01/debate")
    body = resp.json()
    assert body["success"] is False
    assert body["message"] in ("DEBATE_FAILED", "INTERNAL_ERROR")
