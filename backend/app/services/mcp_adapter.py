from __future__ import annotations

from typing import Any

from backend.app.schemas.decision import ToolResult
from mcp_tools.cost_analyzer import analyze_shopping, analyze_time
from mcp_tools.cooling_reminder import create_reminder


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

        raw_result = analyze_shopping(
            price=float(fields["price"]),
            monthly_budget_left=float(fields["monthly_budget_left"]),
        )
        return ToolResult(
            tool_name="cost_analyzer",
            status="success",
            summary=raw_result.get("explanation", "成本分析完成。"),
            risk_level=raw_result.get("risk_level"),
            metrics=raw_result.get("metrics", {}),
            error=None,
        )
    except Exception as exc:
        return _failed_tool_result(
            tool_name="cost_analyzer",
            summary="成本分析工具调用失败，主流程继续。",
            error=f"TOOL_ERROR: {exc}",
        )


def analyze_time_cost(hours_required: float, free_hours_this_week: float, urgent_tasks: int) -> ToolResult:
    # 暂不接入主流程，保留给后续 time case 编排复用。
    try:
        raw_result = analyze_time(
            hours_required=hours_required,
            free_hours_this_week=free_hours_this_week,
            urgent_tasks=urgent_tasks,
        )
        return ToolResult(
            tool_name="cost_analyzer",
            status="success",
            summary=raw_result.get("explanation", "时间成本分析完成。"),
            risk_level=raw_result.get("risk_level"),
            metrics=raw_result.get("metrics", {}),
            error=None,
        )
    except Exception as exc:
        return _failed_tool_result(
            tool_name="cost_analyzer",
            summary="时间成本分析工具调用失败，主流程继续。",
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
    try:
        raw_result = create_reminder(
            user_id=user_id,
            case_id=case_id,
            title=title,
            days=cooling_days,
            reason=reason,
        )

        # E 工具用 status=error 表达业务失败，C 侧统一转成 failed ToolResult。
        if raw_result.get("status") == "error":
            return _failed_tool_result(
                tool_name="cooling_reminder",
                summary="冷静期提醒创建失败，建议用户手动设置复盘提醒。",
                error=raw_result.get("error", "REMINDER_CREATE_FAILED"),
            )

        days = max(cooling_days or 3, 1)
        return ToolResult(
            tool_name="cooling_reminder",
            status="success",
            summary=f"已创建 {days} 天冷静期提醒。",
            risk_level=None,
            metrics={
                "reminder_id": raw_result.get("reminder_id"),
                "cooling_days": days,
                "due_at": raw_result.get("due_at"),
                "status": raw_result.get("status"),
                "watch_items": watch_items or [],
            },
            error=None,
        )
    except Exception as exc:
        return _failed_tool_result(
            tool_name="cooling_reminder",
            summary="冷静期提醒创建失败，建议用户手动设置复盘提醒。",
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
