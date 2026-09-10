"""cost_analyzer — MCP tool for budget and time cost analysis.

Shopping scenario:
    Calculates budget ratio and risk level based on price and remaining budget.

    同一个 monthly_budget_left 数值可能代表两种语义完全不同的钱：本月剩余可支配
    预算（流量），或用户为这次购物攒下的一次性资金（存量）。用同一套月度阈值去
    衡量存量，会把"用攒下的钱买，不影响日常生活"的合理消费误判成高风险，因此这里
    按 budget_source 分开分级。
Time scenario:
    Calculates time pressure based on required hours, free hours, and urgent tasks.
"""

from .logger import logger
import time


# 预算金额的两种来源：
# - monthly_budget: 本月剩余可支配预算（流量，默认值，保持既有行为不变）
# - savings: 用户为这次购物攒下的一次性资金（存量，不按月度重复消耗）
BUDGET_SOURCES = ("monthly_budget", "savings")

# (占比上界, 风险等级)；超过最后一个上界即为 high
_MONTHLY_BUDGET_GRADES = ((0.2, "low"), (0.6, "medium"))
# 存款是一次性资金池，阈值比月度预算宽松：只有超出这笔钱本身（占比 > 1.0）才算高风险
_SAVINGS_GRADES = ((0.5, "low"), (1.0, "medium"))


def _grade_risk(budget_ratio: float, grades: tuple[tuple[float, str], ...]) -> str:
    """按 (占比上界, 等级) 表返回风险等级，超出全部上界时为 high。"""
    for upper_bound, level in grades:
        if budget_ratio <= upper_bound:
            return level
    return "high"


def _validate_budget_source(value: str) -> None:
    """校验资金来源，避免拼错的来源静默走默认分支。"""
    if value not in BUDGET_SOURCES:
        raise ValueError(
            f"budget_source 只能是 monthly_budget 或 savings，收到: {value}"
        )


def _validate_non_negative(value: float, name: str) -> None:
    """确保数值不为空且不为负数。

    0 是合法的边界值（例如剩余预算为 0），负数或 None 属于错误输入，
    由调用方决定如何兜底（上层 adapter/dispatcher 会转成 failed ToolResult）。
    """
    if value is None:
        raise ValueError(f"{name} 不能为空")
    if value < 0:
        raise ValueError(f"{name} 不能为负数，收到: {value}")


def analyze_shopping(
    price: float,
    monthly_budget_left: float,
    budget_source: str = "monthly_budget",
) -> dict:
    """Analyze purchase cost against the money the user set aside for it.

    Args:
        price: Item price in yuan.
        monthly_budget_left: Remaining monthly budget, or the one-off savings
            the user set aside for this purchase.
        budget_source: "monthly_budget" (default, keeps existing behaviour) or
            "savings".

    Returns:
        dict with risk_level, metrics, and explanation.
    """
    start = time.perf_counter()

    _validate_non_negative(price, "price")
    _validate_non_negative(monthly_budget_left, "monthly_budget_left")
    _validate_budget_source(budget_source)
    budget_ratio = price / monthly_budget_left if monthly_budget_left > 0 else 1.0
    budget_left_after = monthly_budget_left - price

    if budget_source == "savings":
        risk_level = _grade_risk(budget_ratio, _SAVINGS_GRADES)
        explanation = (
            f"该商品占本次攒下的可用资金约 {round(budget_ratio * 100)}%，"
            f"风险等级为 {risk_level}。"
        )
    else:
        risk_level = _grade_risk(budget_ratio, _MONTHLY_BUDGET_GRADES)
        explanation = (
            f"该商品占剩余预算约 {round(budget_ratio * 100)}%，"
            f"风险等级为 {risk_level}。"
        )

    result = {
        "risk_level": risk_level,
        "metrics": {
            "budget_ratio": round(budget_ratio, 2),
            "budget_left_after_purchase": round(budget_left_after, 2),
            "budget_source": budget_source,
        },
        "explanation": explanation,
    }

    duration = (time.perf_counter() - start) * 1000
    logger.log_call(
        "cost_analyzer",
        {"price": price, "monthly_budget_left": monthly_budget_left, "budget_source": budget_source},
        result,
        duration,
    )
    return result


def analyze_time(hours_required: float, free_hours_this_week: float, urgent_tasks: int) -> dict:
    """Analyze time commitment against weekly availability.

    Args:
        hours_required: Hours the activity requires.
        free_hours_this_week: User's free hours this week.
        urgent_tasks: Number of urgent tasks the user has.

    Returns:
        dict with risk_level, metrics, and explanation.
    """
    start = time.perf_counter()

    _validate_non_negative(hours_required, "hours_required")
    _validate_non_negative(free_hours_this_week, "free_hours_this_week")
    if urgent_tasks is None or urgent_tasks < 0:
        raise ValueError(f"urgent_tasks 不能为负数或为空，收到: {urgent_tasks}")
    time_ratio = hours_required / free_hours_this_week if free_hours_this_week > 0 else 1.0

    if time_ratio <= 0.3:
        risk_level = "low"
    elif time_ratio <= 0.7:
        risk_level = "medium"
    else:
        risk_level = "high"

    result = {
        "risk_level": risk_level,
        "metrics": {
            "time_ratio": round(time_ratio, 2),
            "urgent_tasks": urgent_tasks,
        },
        "explanation": (
            f"该活动占用本周 {round(time_ratio * 100)}% 空闲时间，"
            f"风险等级为 {risk_level}。"
        ),
    }

    duration = (time.perf_counter() - start) * 1000
    logger.log_call(
        "cost_analyzer",
        {"hours_required": hours_required, "free_hours_this_week": free_hours_this_week, "urgent_tasks": urgent_tasks},
        result,
        duration,
    )
    return result
