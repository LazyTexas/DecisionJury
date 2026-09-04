"""decision_score — MCP tool for a transparent decision score.

给法官 Agent 一个可解释的量化依据：综合成本压力、历史证据风险、
使用价值和冲动触发 4 个维度，输出 0~100 的综合分与风险等级。

本工具是纯规则计算，不依赖 LLM，便于测试和答辩展示。
"""

from .logger import logger
import time


_COST_WEIGHT = {
    "low": 15,
    "medium": 0,
    "high": -20,
}


def _validate_unit(value: float, name: str) -> None:
    """校验 0~1 之间的浮点数。"""
    if value is None:
        raise ValueError(f"{name} 不能为空")
    if value < 0 or value > 1:
        raise ValueError(f"{name} 需在 0 到 1 之间，收到: {value}")


def score_decision(
    *,
    case_type: str,
    cost_risk_level: str = "medium",
    history_risk: float = 0.5,
    usage_value: float = 0.5,
    impulse_trigger: bool = False,
) -> dict:
    """计算决策综合分。

    Args:
        case_type: shopping 或 time。
        cost_risk_level: 来自 cost_analyzer 的 low / medium / high。
        history_risk: 0 表示历史记录支持，1 表示历史记录警示（如闲置/拖延）。
        usage_value: 0 表示使用价值低，1 表示使用价值高。
        impulse_trigger: 是否因促销/种草/情绪等冲动触发。

    Returns:
        dict with score, risk_level, suggestion, dimensions.
    """
    start = time.perf_counter()

    if case_type not in ("shopping", "time"):
        raise ValueError(f"case_type 只能是 shopping 或 time，收到: {case_type}")
    if cost_risk_level not in _COST_WEIGHT:
        raise ValueError(f"cost_risk_level 只能是 low / medium / high，收到: {cost_risk_level}")
    _validate_unit(history_risk, "history_risk")
    _validate_unit(usage_value, "usage_value")
    if not isinstance(impulse_trigger, bool):
        raise ValueError("impulse_trigger 必须是布尔值")

    cost_delta = _COST_WEIGHT[cost_risk_level]
    # history_risk 越高（历史越警示）分数扣得越多
    history_delta = round((0.5 - history_risk) * 30, 2)
    # usage_value 越高分数加得越多
    usage_delta = round((usage_value - 0.5) * 40, 2)
    impulse_delta = -10 if impulse_trigger else 0

    score = max(0, min(100, round(
        50 + cost_delta + history_delta + usage_delta + impulse_delta
    )))

    if score >= 70:
        risk_level = "low"
        suggestion = "综合评分较高，建议积极执行。"
    elif score >= 45:
        risk_level = "medium"
        suggestion = "综合评分中等，建议暂缓后再决定。"
    else:
        risk_level = "high"
        suggestion = "综合评分偏低，建议放弃或寻找替代方案。"

    result = {
        "score": score,
        "risk_level": risk_level,
        "suggestion": suggestion,
        "dimensions": {
            "cost": cost_delta,
            "history": history_delta,
            "usage_value": usage_delta,
            "impulse": impulse_delta,
        },
    }

    duration = (time.perf_counter() - start) * 1000
    logger.log_call(
        "decision_score",
        {
            "case_type": case_type,
            "cost_risk_level": cost_risk_level,
            "history_risk": history_risk,
            "usage_value": usage_value,
            "impulse_trigger": impulse_trigger,
        },
        result,
        duration,
    )
    return result
