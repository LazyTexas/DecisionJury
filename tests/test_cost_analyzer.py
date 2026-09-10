import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp_tools.cost_analyzer import analyze_shopping, analyze_time


def test_shopping_low_risk():
    """price <= 20% of remaining budget -> low"""
    result = analyze_shopping(price=300, monthly_budget_left=2000)
    assert result["risk_level"] == "low", f"expected low, got {result['risk_level']}"
    assert result["metrics"]["budget_ratio"] == 0.15
    assert result["metrics"]["budget_left_after_purchase"] == 1700


def test_shopping_medium_risk():
    """price ~60% of remaining budget -> medium"""
    result = analyze_shopping(price=1200, monthly_budget_left=2000)
    assert result["risk_level"] == "medium", f"expected medium, got {result['risk_level']}"
    assert result["metrics"]["budget_ratio"] == 0.6
    assert result["metrics"]["budget_left_after_purchase"] == 800


def test_shopping_high_risk():
    """price exceeds remaining budget -> high"""
    result = analyze_shopping(price=2600, monthly_budget_left=2000)
    assert result["risk_level"] == "high", f"expected high, got {result['risk_level']}"
    assert result["metrics"]["budget_ratio"] == 1.3
    assert result["metrics"]["budget_left_after_purchase"] == -600


def test_shopping_boundary_low_medium():
    """20% boundary -> low"""
    result = analyze_shopping(price=400, monthly_budget_left=2000)
    assert result["risk_level"] == "low"


def test_shopping_boundary_medium_high():
    """60% boundary -> medium"""
    result = analyze_shopping(price=1200, monthly_budget_left=2000)
    assert result["risk_level"] == "medium"


def test_shopping_zero_budget():
    """budget is 0 -> ratio clamped to 1.0 -> high"""
    result = analyze_shopping(price=100, monthly_budget_left=0)
    assert result["risk_level"] == "high"
    assert result["metrics"]["budget_ratio"] == 1.0


def test_time_low_risk():
    """time_ratio <= 30% -> low"""
    result = analyze_time(hours_required=4, free_hours_this_week=20, urgent_tasks=0)
    assert result["risk_level"] == "low", f"expected low, got {result['risk_level']}"
    assert result["metrics"]["time_ratio"] == 0.2
    assert result["metrics"]["urgent_tasks"] == 0


def test_time_medium_risk():
    """time_ratio ~50% -> medium"""
    result = analyze_time(hours_required=10, free_hours_this_week=20, urgent_tasks=1)
    assert result["risk_level"] == "medium"
    assert result["metrics"]["time_ratio"] == 0.5


def test_time_high_risk():
    """time_ratio > 70% and urgent tasks -> high"""
    result = analyze_time(hours_required=16, free_hours_this_week=20, urgent_tasks=2)
    assert result["risk_level"] == "high"
    assert result["metrics"]["time_ratio"] == 0.8


def test_time_boundary_low_medium():
    """30% boundary -> low"""
    result = analyze_time(hours_required=6, free_hours_this_week=20, urgent_tasks=0)
    assert result["risk_level"] == "low"


def test_time_boundary_medium_high():
    """70% boundary -> medium"""
    result = analyze_time(hours_required=14, free_hours_this_week=20, urgent_tasks=1)
    assert result["risk_level"] == "medium"


def test_time_zero_free_hours():
    """free hours is 0 -> ratio clamped to 1.0 -> high"""
    result = analyze_time(hours_required=5, free_hours_this_week=0, urgent_tasks=1)
    assert result["risk_level"] == "high"
    assert result["metrics"]["time_ratio"] == 1.0


def test_explanation_contains_chinese():
    """explanation should be in Chinese"""
    result = analyze_shopping(price=1299, monthly_budget_left=2000)
    assert "占剩余预算" in result["explanation"]

    result2 = analyze_time(hours_required=16, free_hours_this_week=20, urgent_tasks=2)
    assert "占用本周" in result2["explanation"]


def test_shopping_negative_price_raises():
    """negative price is invalid -> ValueError"""
    try:
        analyze_shopping(price=-10, monthly_budget_left=2000)
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_shopping_negative_budget_raises():
    """negative remaining budget is invalid -> ValueError"""
    try:
        analyze_shopping(price=100, monthly_budget_left=-1)
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_time_negative_hours_raises():
    """negative required hours is invalid -> ValueError"""
    try:
        analyze_time(hours_required=-4, free_hours_this_week=20, urgent_tasks=1)
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_time_negative_free_hours_raises():
    """negative free hours is invalid -> ValueError"""
    try:
        analyze_time(hours_required=4, free_hours_this_week=-5, urgent_tasks=1)
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_time_negative_urgent_tasks_raises():
    """negative urgent_tasks is invalid -> ValueError"""
    try:
        analyze_time(hours_required=4, free_hours_this_week=20, urgent_tasks=-1)
        assert False, "expected ValueError"
    except ValueError:
        pass


# ========== 预算金额来源（budget_source）分级 ==========
# 背景：用户说"攒了1000，购入不影响日常生活"时，1000 是攒下的存量资金，
# 而不是本月可支配预算。用月度阈值衡量存量，会把合理消费直接判成 high。


def test_savings_medium_not_high():
    """存款场景：799/1000 = 79.9% 只到 medium，不再是 high。"""
    result = analyze_shopping(price=799, monthly_budget_left=1000, budget_source="savings")
    assert result["risk_level"] == "medium", f"expected medium, got {result['risk_level']}"
    assert result["metrics"]["budget_source"] == "savings"
    assert result["metrics"]["budget_ratio"] == 0.8
    assert "攒下的可用资金" in result["explanation"]


def test_savings_boundaries():
    """存款场景边界：<=50% low，<=100% medium。"""
    assert analyze_shopping(price=500, monthly_budget_left=1000, budget_source="savings")["risk_level"] == "low"
    assert analyze_shopping(price=1000, monthly_budget_left=1000, budget_source="savings")["risk_level"] == "medium"


def test_savings_exceeding_funds_is_high():
    """存款本身也不够时仍判 high：1200/1000 = 120%。"""
    result = analyze_shopping(price=1200, monthly_budget_left=1000, budget_source="savings")
    assert result["risk_level"] == "high"


def test_monthly_budget_default_unchanged():
    """不传 budget_source 时行为与改动前一致：799/1000 仍为 high，1299/2000 仍为 high。"""
    default_result = analyze_shopping(price=799, monthly_budget_left=1000)
    explicit_result = analyze_shopping(price=799, monthly_budget_left=1000, budget_source="monthly_budget")
    assert default_result["risk_level"] == "high"
    assert explicit_result["risk_level"] == "high"
    assert default_result["metrics"]["budget_source"] == "monthly_budget"
    assert analyze_shopping(price=1299, monthly_budget_left=2000)["risk_level"] == "high"


def test_unknown_budget_source_raises():
    """未知来源直接报错，避免拼错时静默走默认分支。"""
    try:
        analyze_shopping(price=100, monthly_budget_left=1000, budget_source="deposit")
        assert False, "expected ValueError"
    except ValueError:
        pass
