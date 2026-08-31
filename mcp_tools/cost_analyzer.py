"""cost_analyzer — MCP tool for budget and time cost analysis.

Shopping scenario:
    Calculates budget ratio and risk level based on price and remaining budget.
Time scenario:
    Calculates time pressure based on required hours, free hours, and urgent tasks.
"""

from .logger import logger
import time


def _validate_non_negative(value: float, name: str) -> None:
    """确保数值不为空且不为负数。

    0 是合法的边界值（例如剩余预算为 0），负数或 None 属于错误输入，
    由调用方决定如何兜底（上层 adapter/dispatcher 会转成 failed ToolResult）。
    """
    if value is None:
        raise ValueError(f"{name} 不能为空")
    if value < 0:
        raise ValueError(f"{name} 不能为负数，收到: {value}")


def analyze_shopping(price: float, monthly_budget_left: float) -> dict:
    """Analyze purchase cost against remaining monthly budget.

    Args:
        price: Item price in yuan.
        monthly_budget_left: User's remaining monthly budget.

    Returns:
        dict with risk_level, metrics, and explanation.
    """
    start = time.perf_counter()

    _validate_non_negative(price, "price")
    _validate_non_negative(monthly_budget_left, "monthly_budget_left")
    budget_ratio = price / monthly_budget_left if monthly_budget_left > 0 else 1.0
    budget_left_after = monthly_budget_left - price

    if budget_ratio <= 0.2:
        risk_level = "low"
    elif budget_ratio <= 0.6:
        risk_level = "medium"
    else:
        risk_level = "high"

    result = {
        "risk_level": risk_level,
        "metrics": {
            "budget_ratio": round(budget_ratio, 2),
            "budget_left_after_purchase": round(budget_left_after, 2),
        },
        "explanation": (
            f"该商品占剩余预算约 {round(budget_ratio * 100)}%，"
            f"风险等级为 {risk_level}。"
        ),
    }

    duration = (time.perf_counter() - start) * 1000
    logger.log_call("cost_analyzer", {"price": price, "monthly_budget_left": monthly_budget_left}, result, duration)
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
