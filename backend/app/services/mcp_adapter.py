from __future__ import annotations

from typing import Any

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

        raw_result = call_tool(
            "cost_analyzer",
            {
                "case_type": "shopping",
                "price": float(fields["price"]),
                "monthly_budget_left": float(fields["monthly_budget_left"]),
            },
        )
        return _to_tool_result(raw_result, "cost_analyzer")
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

        risk_tags = {"idle", "regret", "budget", "cooling"}
        history_risk = (
            sum(1 for item in rag_evidence if risk_tags.intersection(item.tags)) / len(rag_evidence)
            if rag_evidence
            else 0.5
        )
        frequency = str(fields.get("expected_usage_frequency", ""))
        purpose = str(fields.get("purpose", ""))
        if frequency in {"每天", "每日", "经常", "高频"}:
            usage_value = 0.9
        elif purpose:
            usage_value = 0.65
        else:
            usage_value = 0.3

        raw_result = call_tool(
            "decision_score",
            {
                "case_type": "shopping",
                "cost_risk_level": cost_result.risk_level or "medium",
                "history_risk": max(0.0, min(history_risk, 1.0)),
                "usage_value": usage_value,
                "impulse_trigger": fields.get("trigger_reason") in {"促销", "种草", "情绪"},
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
