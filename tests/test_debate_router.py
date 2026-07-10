# tests/test_debate_router.py
"""
测试 debate 路由（POST /api/cases/{case_id}/debate）
"""

from backend.models import Case
from backend.schemas import CaseStatus


def test_debate_success(client, db_session):
    """正常启动辩论，返回完整结果"""
    case = Case(
        id="case_debate_test",
        user_id="u001",
        case_type="shopping",
        title="买耳机",
        description="想买降噪耳机，预算充足，已有替代品",
        status=CaseStatus.READY_FOR_DEBATE,
        collected_fields={
            "product_name": "降噪耳机",
            "price": 1299,
            "purpose": "学习",
            "monthly_budget_left": 3000,
            "owned_alternatives": "普通耳机",
            "expected_usage_frequency": "每天",
            "trigger_reason": "刚需"
        },
        missing_fields=[]
    )
    db_session.add(case)
    db_session.commit()

    response = client.post(
        "/api/cases/case_debate_test/debate",
        json={"user_id": "u001"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["case_status"] == CaseStatus.COMPLETED
    assert "steps" in data["data"]
    assert "rag_evidence" in data["data"]
    assert "tool_results" in data["data"]
    assert "report" in data["data"]


def test_debate_case_not_found(client):
    """案件不存在返回 CASE_NOT_FOUND"""
    response = client.post(
        "/api/cases/case_not_exist/debate",
        json={"user_id": "u001"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert data["message"] == "CASE_NOT_FOUND"


def test_debate_not_ready_returns_missing_fields(client, db_session):
    """案件信息不完整时返回 MISSING_FIELDS，并包含 missing_fields 和 next_question"""
    case = Case(
        id="case_not_ready",
        user_id="u001",
        case_type="shopping",
        title="买耳机",
        description="想买降噪耳机",
        status=CaseStatus.COLLECTING,
        collected_fields={"description": "想买降噪耳机"},
        missing_fields=["monthly_budget_left", "owned_alternatives"]
    )
    db_session.add(case)
    db_session.commit()

    response = client.post(
        "/api/cases/case_not_ready/debate",
        json={"user_id": "u001"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert data["message"] == "MISSING_FIELDS"
    # P1-1 修复验证：返回 data 包含 missing_fields
    assert data["data"] is not None
    assert "missing_fields" in data["data"]
    assert "case_status" in data["data"]
    assert data["data"]["case_status"] == CaseStatus.COLLECTING
    assert "monthly_budget_left" in data["data"]["missing_fields"]
    assert "next_question" in data["data"]


def test_debate_high_risk_returns_rejected(client, db_session):
    """高风险决策返回 HIGH_RISK_DECISION"""
    case = Case(
        id="case_high_risk",
        user_id="u001",
        case_type="shopping",
        title="投资决策",
        description="想投资股票",
        status=CaseStatus.REJECTED,
        collected_fields={},
        missing_fields=[]
    )
    db_session.add(case)
    db_session.commit()

    response = client.post(
        "/api/cases/case_high_risk/debate",
        json={"user_id": "u001"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert data["message"] == "HIGH_RISK_DECISION"


def test_debate_missing_user_id(client, db_session):
    """缺少 user_id 返回验证错误"""
    case = Case(
        id="case_test",
        user_id="u001",
        case_type="shopping",
        title="买耳机",
        description="想买降噪耳机",
        status=CaseStatus.READY_FOR_DEBATE,
        collected_fields={},
        missing_fields=[]
    )
    db_session.add(case)
    db_session.commit()

    response = client.post(
        "/api/cases/case_test/debate",
        json={}
    )

    assert response.status_code == 422
    data = response.json()
    assert data["success"] is False
    assert data["message"] == "VALIDATION_ERROR"


def test_debate_response_contains_trace(client, db_session):
    """debate 响应中包含 trace 字段"""
    case = Case(
        id="case_trace_test",
        user_id="u001",
        case_type="shopping",
        title="买耳机",
        description="想买降噪耳机，预算充足，已有替代品",
        status=CaseStatus.READY_FOR_DEBATE,
        collected_fields={
            "product_name": "降噪耳机",
            "price": 1299,
            "purpose": "学习",
            "monthly_budget_left": 3000,
            "owned_alternatives": "普通耳机",
            "expected_usage_frequency": "每天",
            "trigger_reason": "刚需"
        },
        missing_fields=[]
    )
    db_session.add(case)
    db_session.commit()

    response = client.post(
        "/api/cases/case_trace_test/debate",
        json={"user_id": "u001"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "trace" in data["data"]
    assert len(data["data"]["trace"]) >= 7  # 至少 7 步
    trace_steps = [t["name"] for t in data["data"]["trace"]]
    assert "input_parser" in trace_steps
    assert "rag_search" in trace_steps
    assert "pro_agent" in trace_steps
    assert "con_agent" in trace_steps
    assert "judge_agent" in trace_steps
    assert "cost_analyzer" in trace_steps
    assert "cooling_reminder" in trace_steps