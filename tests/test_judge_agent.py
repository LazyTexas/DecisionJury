# tests/test_judge_agent.py
"""Judge Agent 单元测试 —— 纯逻辑，无 LLM 依赖"""

from backend.app.agents.judge_agent import (
    run_judge_agent,
    _decide,
    _confidence,
    _next_actions,
)
from backend.app.schemas.decision import AgentStep, DecisionReport, RagEvidence, ToolResult


# ========== 辅助函数 ==========

def _make_fields(**overrides):
    """构建默认 collected_fields，可按需覆盖。"""
    defaults = {
        "product_name": "耳机",
        "price": 299,
        "purpose": "学习",
        "monthly_budget_left": 1000,
        "owned_alternatives": "",
        "expected_usage_frequency": "偶尔",
        "trigger_reason": "刚需",
    }
    defaults.update(overrides)
    return defaults


def _make_cost_result(risk_level="low", status="success", summary="预算风险低"):
    """构建 cost_analyzer ToolResult。"""
    return ToolResult(
        tool_name="cost_analyzer",
        status=status,
        summary=summary,
        risk_level=risk_level,
        metrics={},
        error=None,
    )


def _make_cooling_result(status="success"):
    """构建 cooling_reminder ToolResult。"""
    return ToolResult(
        tool_name="cooling_reminder",
        status=status,
        summary="冷静期提醒已创建",
        risk_level=None,
        metrics={"cooling_days": 3},
        error=None if status == "success" else "创建失败",
    )


def _make_rag(tags=None):
    """构建 RAG 证据列表。"""
    return [
        RagEvidence(
            id="rag_001",
            title="测试记录",
            content="测试内容",
            score=0.8,
            source="history",
            case_type="shopping",
            tags=tags or ["electronics"],
            created_at="2025-01-01T00:00:00",
        )
    ]


def _make_pro_step():
    return AgentStep(
        agent="pro_agent",
        status="completed",
        summary="支持购买",
        confidence=0.7,
        arguments=["用途明确", "使用频率高"],
    )


def _make_con_step():
    return AgentStep(
        agent="con_agent",
        status="completed",
        summary="反对购买",
        confidence=0.78,
        arguments=["预算压力大", "可能闲置"],
    )


# ========== _decide 决策逻辑 ==========

def test_decide_high_risk_reject():
    """cost risk_level="high" → final_decision="reject"。"""
    cost = _make_cost_result(risk_level="high")
    assert _decide(_make_fields(), [], cost) == "reject"


def test_decide_medium_risk_delay():
    """risk_level="medium" → "delay"。"""
    cost = _make_cost_result(risk_level="medium")
    assert _decide(_make_fields(), [], cost) == "delay"


def test_decide_impulse_trigger_delay():
    """trigger="促销" → "delay"。"""
    cost = _make_cost_result(risk_level="low")
    assert _decide(_make_fields(trigger_reason="促销"), [], cost) == "delay"


def test_decide_risk_history_delay():
    """RAG 有 idle 标签 → "delay"。"""
    cost = _make_cost_result(risk_level="low")
    rag = _make_rag(tags=["idle", "regret"])
    assert _decide(_make_fields(), rag, cost) == "delay"


def test_decide_has_alternatives():
    """alternatives 非空非"无" → "alternative"。"""
    cost = _make_cost_result(risk_level="low")
    assert _decide(_make_fields(owned_alternatives="旧耳机"), [], cost) == "alternative"


def test_decide_high_frequency_buy():
    """frequency="每天" → "buy"。"""
    cost = _make_cost_result(risk_level="low")
    assert _decide(_make_fields(expected_usage_frequency="每天"), [], cost) == "buy"


def test_decide_default_delay():
    """无特殊条件 → 默认 "delay"。"""
    cost = _make_cost_result(risk_level="low")
    assert _decide(_make_fields(), [], cost) == "delay"


# ========== _confidence 置信度 ==========

def test_confidence_with_rag_and_cost():
    """有 RAG + cost 成功 → confidence 较高。"""
    rag = _make_rag()
    cost = _make_cost_result(status="success")
    c = _confidence(rag, cost)
    # 0.72 + 0.08 + 0.05 = 0.85
    assert c == 0.85


def test_confidence_without_rag():
    """无 RAG → confidence 较低。"""
    cost = _make_cost_result(status="success")
    c = _confidence([], cost)
    # 0.72 - 0.12 + 0.05 = 0.65
    assert c == 0.65


def test_confidence_clamped():
    """confidence 钳制在 [0.3, 0.9]。"""
    # 无 RAG + cost 失败 = 0.72 - 0.12 - 0.1 = 0.5
    cost = _make_cost_result(status="failed")
    c = _confidence([], cost)
    assert c >= 0.3
    assert c <= 0.9


# ========== _next_actions ==========

def test_next_actions_delay():
    """delay 时包含"观察清单"和"替代方案"。"""
    actions = _next_actions("delay", [], None, None)
    assert any("观察清单" in a for a in actions)
    assert any("替代方案" in a for a in actions)


def test_next_actions_buy():
    """buy 时包含"确认不影响必要支出"。"""
    actions = _next_actions("buy", [], None, None)
    assert any("必要支出" in a for a in actions)


def test_next_actions_reject():
    """reject 时包含"记录放弃原因"。"""
    actions = _next_actions("reject", [], None, None)
    assert any("放弃原因" in a for a in actions)


def test_next_actions_no_rag_hint():
    """无 RAG 时提示补充复盘记录。"""
    actions = _next_actions("buy", [], None, None)
    assert any("历史证据" in a or "复盘记录" in a for a in actions)


def test_next_actions_cooling_success():
    """冷静期提醒成功时提示"按期复盘"。"""
    cooling = _make_cooling_result(status="success")
    actions = _next_actions("delay", [], None, cooling)
    assert any("按期复盘" in a for a in actions)


def test_next_actions_cooling_failed():
    """冷静期提醒失败时提示手动设置。"""
    cooling = _make_cooling_result(status="failed")
    actions = _next_actions("delay", [], None, cooling)
    assert any("手动" in a for a in actions)


# ========== run_judge_agent 完整流程 ==========

def test_run_judge_agent_returns_tuple():
    """run_judge_agent 返回 (AgentStep, DecisionReport) 元组。"""
    step, report = run_judge_agent(
        case_id="case_001",
        collected_fields=_make_fields(),
        pro_step=_make_pro_step(),
        con_step=_make_con_step(),
        rag_evidence=[],
        tool_results=[_make_cost_result()],
    )
    assert isinstance(step, AgentStep)
    assert isinstance(report, DecisionReport)
    assert step.agent == "judge_agent"
    assert step.status == "completed"


def test_report_structure():
    """DecisionReport 各字段完整。"""
    step, report = run_judge_agent(
        case_id="case_001",
        collected_fields=_make_fields(),
        pro_step=_make_pro_step(),
        con_step=_make_con_step(),
        rag_evidence=_make_rag(),
        tool_results=[_make_cost_result()],
    )
    assert report.report_id.startswith("report_")
    assert report.case_id == "case_001"
    assert report.case_type == "shopping"
    assert report.final_decision in ("buy", "delay", "reject", "alternative")
    assert 0.3 <= report.confidence <= 0.9
    assert isinstance(report.summary, str)
    assert isinstance(report.pro_points, list)
    assert isinstance(report.con_points, list)
    assert isinstance(report.next_actions, list)
    assert isinstance(report.rag_evidence, list)
    assert isinstance(report.tool_results, list)
    assert report.created_at is not None
