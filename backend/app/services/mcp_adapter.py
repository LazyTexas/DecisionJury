from __future__ import annotations

from typing import Any

from backend.app.agents.field_normalizer import (
    FREQ_UNKNOWN,
    canonical_frequency,
    canonical_trigger,
    is_high_frequency,
    is_impulse_trigger,
    split_evidence_by_relevance,
)
from backend.app.schemas.decision import ToolResult
from mcp_tools.mcp import call_tool


def analyze_shopping_cost(case_id: str, case_type: str, fields: dict[str, Any]) -> ToolResult:
    _ = case_id
    try:
        # C 模块对外只暴露 ToolResult；E 工具的原始 dict 在 adapter 内部完成翻译。
        if case_type != "shopping":
            return _failed_tool_result(
                tool_name="cost_analyzer",
                summary="当前 cost_analyzer adapter 仅支持 shopping。",
                error="UNSUPPORTED_CASE_TYPE",
            )

        # 单价 / 数量语义：'5元/斤' 的 5 是单价，不能直接当总价算占比。
        quantity = fields.get("quantity")
        price = float(fields["price"])
        price_basis = "total_price"
        if fields.get("price_is_unit"):
            if quantity not in (None, ""):
                try:
                    price = price * float(quantity)
                    price_basis = "unit_price_x_quantity"
                except (TypeError, ValueError):
                    price_basis = "unit_price"
            else:
                price_basis = "unit_price"

        raw_result = call_tool(
            "cost_analyzer",
            {
                "case_type": "shopping",
                "price": price,
                "monthly_budget_left": float(fields["monthly_budget_left"]),
                # 金额来源由 parser 标记；老案件没有该字段时回落到月度预算（原行为）。
                "budget_source": fields.get("budget_source") or "monthly_budget",
            },
        )
        tool_result = _to_tool_result(raw_result, "cost_analyzer")
        tool_result.metrics = {**(tool_result.metrics or {}), "basis": price_basis}
        if price_basis == "unit_price":
            tool_result.summary = f"{tool_result.summary}（按单价估算，未计数量）"
        return tool_result
    except Exception as exc:
        return _failed_tool_result(
            tool_name="cost_analyzer",
            summary="成本分析工具调用失败，主流程继续。",
            error=f"TOOL_ERROR: {exc}",
        )


def analyze_time_cost(hours_required: float, free_hours_this_week: float, urgent_tasks: int) -> ToolResult:
    # 暂不接入主流程，保留给后续 time case 编排复用。
    try:
        raw_result = call_tool(
            "cost_analyzer",
            {
                "case_type": "time",
                "hours_required": hours_required,
                "free_hours_this_week": free_hours_this_week,
                "urgent_tasks": urgent_tasks,
            },
        )
        return _to_tool_result(raw_result, "cost_analyzer")
    except Exception as exc:
        return _failed_tool_result(
            tool_name="cost_analyzer",
            summary="时间成本分析工具调用失败，主流程继续。",
            error=f"TOOL_ERROR: {exc}",
        )


def score_decision(
    case_id: str,
    case_type: str,
    fields: dict[str, Any],
    rag_evidence: list[Any],
    cost_result: ToolResult,
) -> ToolResult:
    """调用 E 的 decision_score，并把 C 的案件上下文转换为工具契约。"""
    _ = case_id
    try:
        if case_type != "shopping":
            return _failed_tool_result(
                tool_name="decision_score",
                summary="当前 decision_score adapter 仅支持 shopping。",
                error="UNSUPPORTED_CASE_TYPE",
            )

        # 证据先做相关性过滤：无关历史不能影响评分（BM25 是词面检索，可能召回不相干记录）。
        related_evidence, _unrelated = split_evidence_by_relevance(rag_evidence, fields)
        risk_tags = {"idle", "regret", "budget", "cooling"}
        history_risk = (
            sum(1 for item in related_evidence if risk_tags.intersection(item.tags)) / len(related_evidence)
            if related_evidence
            else 0.5
        )
        # 频率与触发原因统一走归一化：'每天使用'/'日常使用' 都算高频，'朋友推荐' 也算冲动触发。
        frequency = canonical_frequency(fields)
        purpose = str(fields.get("purpose", "") or "")
        if is_high_frequency(frequency):
            usage_value = 0.9
        elif frequency != FREQ_UNKNOWN or purpose:
            usage_value = 0.65
        else:
            # 用途和频率都没填 = 信息未知，不是“使用价值低”。给中性 0.5，
            # 避免“没回答字段”被公式当成负分（旧实现给 0.3 -> 扣 8 分）。
            usage_value = 0.5

        raw_result = call_tool(
            "decision_score",
            {
                "case_type": "shopping",
                "cost_risk_level": cost_result.risk_level or "medium",
                "history_risk": max(0.0, min(history_risk, 1.0)),
                "usage_value": usage_value,
                "impulse_trigger": is_impulse_trigger(canonical_trigger(fields)),
            },
        )
        return _to_tool_result(raw_result, "decision_score")
    except Exception as exc:
        return _failed_tool_result(
            tool_name="decision_score",
            summary="决策评分工具调用失败，主流程继续。",
            error=f"TOOL_ERROR: {exc}",
        )


def create_cooling_reminder(
    user_id: str,
    case_id: str,
    title: str,
    cooling_days: int = 3,
    reason: str = "",
    watch_items: list[str] | None = None,
) -> ToolResult:
    failure_summary = "冷静期提醒创建失败，建议用户手动设置复盘提醒。"
    try:
        raw_result = call_tool(
            "cooling_reminder",
            {
                "user_id": user_id,
                "case_id": case_id,
                "title": title,
                "cooling_days": cooling_days,
                "reason": reason,
                "watch_items": watch_items or [],
            },
        )
        tool_result = _to_tool_result(raw_result, "cooling_reminder")
        if tool_result.status == "success":
            tool_result.metrics = {**tool_result.metrics, "title": title, "reason": reason}
        if tool_result.status == "failed":
            tool_result.summary = "冷静期提醒创建失败，建议用户手动设置复盘提醒。"
        return tool_result
    except Exception as exc:
        return _failed_tool_result(
            tool_name="cooling_reminder",
            summary=failure_summary,
            error=f"REMINDER_CREATE_FAILED: {exc}",
        )


def _failed_tool_result(tool_name: str, summary: str, error: str) -> ToolResult:
    return ToolResult(
        tool_name=tool_name,
        status="failed",
        summary=summary,
        risk_level=None,
        metrics={},
        error=error,
    )


def _to_tool_result(raw_result: dict[str, Any], fallback_tool_name: str) -> ToolResult:
    """将 E 统一入口的 dict 转为 C 编排层使用的 ToolResult。"""
    return ToolResult(
        tool_name=raw_result.get("tool_name", fallback_tool_name),
        status=raw_result.get("status", "failed"),
        summary=raw_result.get("summary", "工具调用失败，主流程继续。"),
        risk_level=raw_result.get("risk_level"),
        metrics=raw_result.get("metrics", {}),
        error=raw_result.get("error"),
    )


# 评分工具的原始文案是"建议积极执行"，与最终判决并存时会让读者困惑；
# 这里统一加限定语：评分只作参考，结论以规则判决为准。
_ORIGINAL_TO_TOOL_RESULT = _to_tool_result


def _to_tool_result(raw_result, tool_name, *args, **kwargs):  # type: ignore[no-redef]
    result = _ORIGINAL_TO_TOOL_RESULT(raw_result, tool_name, *args, **kwargs)
    if tool_name == "decision_score" and "仅供参考" not in result.summary:
        result.summary = result.summary.rstrip("。") + "（该评分仅供参考，最终以判决结论为准）。"
    return result
