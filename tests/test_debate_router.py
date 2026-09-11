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


def test_debate_response_contains_steps(client, db_session):
    """debate 响应按契约返回 steps / rag_evidence / tool_results（完整轨迹另由 GET /trace 提供）"""
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

    # 契约依据 docs/04_API.md：/debate 响应含 steps / rag_evidence / tool_results，
    # 不含 trace 字段（完整执行轨迹由 GET /api/cases/{case_id}/trace 单独提供）。
    # 原断言 trace 与文档不一致，属于用例过期。
    payload = data["data"]
    assert {"steps", "rag_evidence", "tool_results"} <= set(payload)

    step_agents = [step["agent"] for step in payload["steps"]]
    assert "input_parser" in step_agents
    assert "pro_agent" in step_agents
    assert "con_agent" in step_agents
    assert "judge_agent" in step_agents

    tool_names = [tool["tool_name"] for tool in payload["tool_results"]]
    assert "cost_analyzer" in tool_names
    assert "cooling_reminder" in tool_names


# ========== 预算金额来源的端到端回归对 ==========
# 场景来源：用户补充"我攒了1000，购入不影响日常生活"，系统却把它当成本月预算，
# 799/1000 被判 high，最终 reject 且置信度 0.85。下面两条用例锁住修复后的行为。

def _seed_budget_case(case_id, price, budget, budget_source=None):
    """播种一个可进入庭审的购物案件；description 不含预算/存量词，避免庭审重解析改标签。"""
    fields = {
        "product_name": "降噪耳机",
        "price": price,
        "purpose": "学习",
        "monthly_budget_left": budget,
        "owned_alternatives": "普通耳机",
        "expected_usage_frequency": "每天",
        "trigger_reason": "刚需",
    }
    if budget_source:
        fields["budget_source"] = budget_source
    return Case(
        id=case_id,
        user_id="u001",
        case_type="shopping",
        title="买耳机",
        description="想买降噪耳机，已有普通耳机",
        status=CaseStatus.READY_FOR_DEBATE,
        collected_fields=fields,
        missing_fields=[],
    )


def _cost_result(payload):
    return next(item for item in payload["tool_results"] if item["tool_name"] == "cost_analyzer")


def test_debate_savings_budget_avoids_reject(client, db_session):
    """攒下的钱买 799 元耳机：成本风险降为 medium，判决不再是 reject。"""
    db_session.add(_seed_budget_case("case_savings_budget", price=799, budget=1000, budget_source="savings"))
    db_session.commit()

    response = client.post("/api/cases/case_savings_budget/debate", json={"user_id": "u001"})

    assert response.status_code == 200
    payload = response.json()["data"]
    cost = _cost_result(payload)
    assert cost["risk_level"] == "medium"
    assert cost["metrics"]["budget_source"] == "savings"
    assert payload["report"]["final_decision"] == "delay"


def test_debate_monthly_budget_still_rejects(client, db_session):
    """本月预算口径的金额不得被 savings 分级放过：成本风险必须仍是 high。

    口径说明（融合时按本地规则表 v2 调整）：
    - 本用例原本断言 final_decision == "reject"（dev 侧旧口径：high → reject）。
    - 本地规则表 v2 对"高风险但属于刚需/高频且评分达标"的支出走 E6（提示冷静期）
      再由 R3 放行 → buy；真正超预算（占比 >100%）才由 H1 直接 reject。
    - 因此保留"风险等级 high + 来源 monthly_budget"这两个核心保护断言，并改为按本地
      口径断言 buy + 冷静期提醒仍在，避免"真·超预算被放过"的回归无人把守。
    """
    db_session.add(_seed_budget_case("case_monthly_budget", price=799, budget=1000))
    db_session.commit()

    response = client.post("/api/cases/case_monthly_budget/debate", json={"user_id": "u001"})

    assert response.status_code == 200
    payload = response.json()["data"]
    cost = _cost_result(payload)
    assert cost["risk_level"] == "high"
    assert cost["metrics"]["budget_source"] == "monthly_budget"
    assert payload["report"]["final_decision"] == "buy"
    tools = {t.get("tool_name") for t in payload["report"].get("tool_results") or []}
    assert "cooling_reminder" in tools, "高风险放行必须仍然创建冷静期提醒"