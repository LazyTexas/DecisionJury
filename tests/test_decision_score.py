# tests/test_decision_score.py
"""decision_score 决策评分工具单元测试。"""

from mcp_tools.decision_score import score_decision


def test_score_high_value_low_risk_low():
    """成本低 + 历史支持 + 使用价值高 + 无冲动 -> 低风险高得分。"""
    result = score_decision(
        case_type="shopping",
        cost_risk_level="low",
        history_risk=0.2,
        usage_value=0.9,
        impulse_trigger=False,
    )
    assert result["risk_level"] == "low"
    assert result["score"] == 90


def test_score_low_value_high_risk_high():
    """成本高 + 历史警示 + 价值低 + 冲动触发 -> 高风险低得分（0 分兜底）。"""
    result = score_decision(
        case_type="time",
        cost_risk_level="high",
        history_risk=0.9,
        usage_value=0.1,
        impulse_trigger=True,
    )
    assert result["risk_level"] == "high"
    assert result["score"] == 0


def test_score_medium_default():
    """默认参数 -> 50 分中等。"""
    result = score_decision(case_type="shopping")
    assert result["risk_level"] == "medium"
    assert result["score"] == 50


def test_score_dimensions_present():
    """返回包含 4 个维度贡献。"""
    result = score_decision(
        case_type="shopping",
        cost_risk_level="medium",
        history_risk=0.5,
        usage_value=0.5,
        impulse_trigger=True,
    )
    dims = result["dimensions"]
    assert "cost" in dims
    assert "history" in dims
    assert "usage_value" in dims
    assert "impulse" in dims
    # 冲动触发会扣 10 分
    assert result["score"] == 40
    assert dims["impulse"] == -10


def test_invalid_case_type_raises():
    """非法 case_type 报错。"""
    try:
        score_decision(case_type="medical")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_invalid_cost_risk_level_raises():
    """非法 cost_risk_level 报错。"""
    try:
        score_decision(case_type="shopping", cost_risk_level="urgent")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_history_risk_out_of_range_raises():
    """history_risk 超出 0~1 报错。"""
    try:
        score_decision(case_type="shopping", history_risk=1.5)
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_impulse_trigger_must_be_bool():
    """score_decision 直接调用时，impulse_trigger 必须是布尔值，字符串应报错。"""
    try:
        score_decision(case_type="shopping", impulse_trigger="true")
        assert False, "expected ValueError"
    except ValueError:
        pass
