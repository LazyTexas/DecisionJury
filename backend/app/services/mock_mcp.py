from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from backend.app.schemas.decision import ToolResult


CHINA_TZ = timezone(timedelta(hours=8))


def cost_analyzer(case_id: str, case_type: str, fields: dict[str, Any]) -> ToolResult:
    _ = case_id
    try:
        if case_type != "shopping":
            return ToolResult(
                tool_name="cost_analyzer",
                status="failed",
                summary="当前 mock cost_analyzer 仅支持 shopping。",
                risk_level=None,
                metrics={},
                error="UNSUPPORTED_CASE_TYPE",
            )

        price = float(fields["price"])
        budget = float(fields["monthly_budget_left"])
        ratio = round(price / budget, 2) if budget else 1.0
        left_after = round(budget - price, 2)

        if ratio >= 0.8 or left_after < 0:
            risk_level = "high"
        elif ratio >= 0.4:
            risk_level = "medium"
        else:
            risk_level = "low"

        return ToolResult(
            tool_name="cost_analyzer",
            status="success",
            summary=f"该商品占剩余预算约 {int(ratio * 100)}%，预算风险为 {risk_level}。",
            risk_level=risk_level,
            metrics={
                "budget_ratio": ratio,
                "budget_left_after_purchase": left_after,
            },
            error=None,
        )
    except Exception as exc:
        return ToolResult(
            tool_name="cost_analyzer",
            status="failed",
            summary="成本计算工具调用失败，主流程继续。",
            risk_level=None,
            metrics={},
            error=f"TOOL_ERROR: {exc}",
        )


def cooling_reminder(
    user_id: str,
    case_id: str,
    title: str,
    cooling_days: int,
    reason: str,
    watch_items: list[str],
) -> ToolResult:
    try:
        days = cooling_days or 3
        due_at = (datetime.now(CHINA_TZ) + timedelta(days=days)).replace(microsecond=0).isoformat()
        return ToolResult(
            tool_name="cooling_reminder",
            status="success",
            summary=f"已创建 {days} 天冷静期提醒。",
            risk_level=None,
            metrics={
                "reminder_id": f"reminder_{case_id}",
                "user_id": user_id,
                "cooling_days": days,
                "due_at": due_at,
                "reason": reason,
                "watch_items": watch_items,
            },
            error=None,
        )
    except Exception as exc:
        return ToolResult(
            tool_name="cooling_reminder",
            status="failed",
            summary="冷静期提醒创建失败，建议用户手动设置复盘提醒。",
            risk_level=None,
            metrics={},
            error=f"REMINDER_CREATE_FAILED: {exc}",
        )
