"""MCP tool contract layer for DecisionJury.

E 模块把 cost_analyzer / cooling_reminder 包装成“工具名称 + 参数字典”即可调用的
统一入口（ToolResult 兼容的结构），供：

- Agent 编排层按 (name, arguments) 直接调用；
- 前端/联调脚本验证工具调用链路；
- 未来封装为真正的 MCP Server 时复用同一份 tool schema。

本模块不引入第三方 MCP SDK，仅依赖项目已实现的工具函数与日志器。
"""

from __future__ import annotations

from typing import Any

from mcp_tools.cost_analyzer import analyze_shopping, analyze_time
from mcp_tools.cooling_reminder import create_reminder
from mcp_tools.decision_score import score_decision
from mcp_tools.logger import logger
import time


# MCP 工具定义（input_schema 风格），用于描述工具可被哪些参数调用。
TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "cost_analyzer",
        "description": "分析购物预算占比或时间占用压力，返回风险等级与指标。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "case_type": {"type": "string", "enum": ["shopping", "time"]},
                "price": {"type": "number"},
                "monthly_budget_left": {"type": "number"},
                "hours_required": {"type": "number"},
                "free_hours_this_week": {"type": "number"},
                "urgent_tasks": {"type": "integer"},
            },
            "required": ["case_type"],
        },
    },
    {
        "name": "cooling_reminder",
        "description": "创建冷静期提醒，返回提醒 ID、到期时间和状态。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "user_id": {"type": "string"},
                "case_id": {"type": "string"},
                "title": {"type": "string"},
                "cooling_days": {"type": "integer", "minimum": 1},
                "reason": {"type": "string"},
                "watch_items": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["user_id", "case_id", "title"],
        },
    },
    {
        "name": "decision_score",
        "description": "对购物或时间决策给出 0~100 的可解释综合分，辅助法官裁决。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "case_type": {"type": "string", "enum": ["shopping", "time"]},
                "cost_risk_level": {"type": "string", "enum": ["low", "medium", "high"]},
                "history_risk": {"type": "number", "minimum": 0, "maximum": 1},
                "usage_value": {"type": "number", "minimum": 0, "maximum": 1},
                "impulse_trigger": {"type": "boolean"},
            },
            "required": ["case_type"],
        },
    },
]


def get_tool_definitions() -> list[dict[str, Any]]:
    """返回工具定义副本，避免调用方直接修改内部状态。"""
    return [dict(item) for item in TOOL_DEFINITIONS]


def call_tool(name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    """按工具名分发到具体函数，并统一返回 ToolResult 兼容结构。

    成功路径由各工具函数写一条调用日志；失败路径由本分发器补一条失败的调用日志，
    因此使用统一入口调用时只保留一条调用记录。
    """
    args = dict(arguments or {})
    start = time.perf_counter()
    try:
        if name == "cost_analyzer":
            result = _call_cost_analyzer(args)
        elif name == "cooling_reminder":
            result = _call_cooling_reminder(args)
        elif name == "decision_score":
            result = _call_decision_score(args)
        else:
            result = _failed_tool(
                name, f"未知工具: {name}", "UNKNOWN_TOOL"
            )
    except Exception as exc:
        result = _failed_tool(
            name, "工具调用失败，主流程继续。", f"TOOL_ERROR: {exc}"
        )

    # 成功时工具函数已记日志；这里只在失败时补记，避免重复。
    if result.get("status") == "failed":
        duration_ms = (time.perf_counter() - start) * 1000
        logger.log_call(name, args, result, duration_ms)
    return result


def _call_cost_analyzer(args: dict[str, Any]) -> dict[str, Any]:
    case_type = args.get("case_type")
    if case_type == "shopping":
        price = args.get("price")
        budget = args.get("monthly_budget_left")
        if price is None or budget is None:
            return _failed_tool(
                "cost_analyzer",
                "shopping 场景需要 price 和 monthly_budget_left",
                "MISSING_ARGS",
            )
        raw = analyze_shopping(price=float(price), monthly_budget_left=float(budget))
        return _success_tool(
            "cost_analyzer",
            summary=raw.get("explanation", "成本分析完成。"),
            risk_level=raw.get("risk_level"),
            metrics=raw.get("metrics", {}),
        )

    if case_type == "time":
        hours = args.get("hours_required")
        free = args.get("free_hours_this_week")
        urgent = args.get("urgent_tasks")
        if hours is None or free is None or urgent is None:
            return _failed_tool(
                "cost_analyzer",
                "time 场景需要 hours_required、free_hours_this_week 和 urgent_tasks",
                "MISSING_ARGS",
            )
        raw = analyze_time(
            hours_required=float(hours),
            free_hours_this_week=float(free),
            urgent_tasks=int(urgent),
        )
        return _success_tool(
            "cost_analyzer",
            summary=raw.get("explanation", "时间成本分析完成。"),
            risk_level=raw.get("risk_level"),
            metrics=raw.get("metrics", {}),
        )

    return _failed_tool(
        "cost_analyzer",
        "case_type 只能是 shopping 或 time",
        "UNSUPPORTED_CASE_TYPE",
    )


def _call_cooling_reminder(args: dict[str, Any]) -> dict[str, Any]:
    user_id = args.get("user_id")
    case_id = args.get("case_id")
    title = args.get("title")
    if not user_id or not case_id or not title:
        return _failed_tool(
            "cooling_reminder",
            "user_id、case_id 和 title 都是必填项",
            "MISSING_ARGS",
        )

    raw = create_reminder(
        user_id=user_id,
        case_id=case_id,
        title=title,
        cooling_days=args.get("cooling_days", 3),
        reason=args.get("reason", ""),
    )
    if raw.get("status") == "error":
        return _failed_tool(
            "cooling_reminder",
            raw.get("error", "冷静期提醒创建失败。"),
            "REMINDER_CREATE_FAILED",
        )

    days = max(int(args.get("cooling_days") or 3), 1)
    return _success_tool(
        "cooling_reminder",
        summary=f"已创建 {days} 天冷静期提醒。",
        risk_level=None,
        metrics={
            "reminder_id": raw.get("reminder_id"),
            "cooling_days": days,
            "due_at": raw.get("due_at"),
            "status": raw.get("status"),
            "watch_items": args.get("watch_items") or [],
        },
    )


def _parse_bool(value: Any, default: bool = False) -> bool:
    """把参数解析成布尔值，无法解析时抛 ValueError。

    避免 bool("false") == True 这类误判，也避免把任意字符串强制成 True。
    """
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        text = value.strip().lower()
        if text in ("true", "1", "yes", "y"):
            return True
        if text in ("false", "0", "no", "n"):
            return False
        raise ValueError(f"impulse_trigger 无法解析的布尔值: {value!r}")
    if isinstance(value, int):
        if value in (0, 1):
            return bool(value)
    raise ValueError(f"impulse_trigger 必须是布尔值或可解析字符串，收到: {value!r}")


def _call_decision_score(args: dict[str, Any]) -> dict[str, Any]:
    case_type = args.get("case_type")
    if case_type not in ("shopping", "time"):
        return _failed_tool(
            "decision_score",
            "case_type 只能是 shopping 或 time",
            "UNSUPPORTED_CASE_TYPE",
        )

    try:
        impulse_trigger = _parse_bool(args.get("impulse_trigger"), default=False)
    except ValueError as exc:
        return _failed_tool(
            "decision_score",
            str(exc),
            "INVALID_ARGS",
        )

    raw = score_decision(
        case_type=case_type,
        cost_risk_level=args.get("cost_risk_level", "medium"),
        history_risk=args.get("history_risk", 0.5),
        usage_value=args.get("usage_value", 0.5),
        impulse_trigger=impulse_trigger,
    )

    return _success_tool(
        "decision_score",
        summary=raw.get("suggestion", "决策评分完成。"),
        risk_level=raw.get("risk_level"),
        metrics={
            "score": raw.get("score"),
            "risk_level": raw.get("risk_level"),
            "dimensions": raw.get("dimensions", {}),
        },
    )


def _success_tool(
    tool_name: str,
    summary: str,
    risk_level: str | None,
    metrics: dict[str, Any],
) -> dict[str, Any]:
    return {
        "tool_name": tool_name,
        "status": "success",
        "summary": summary,
        "risk_level": risk_level,
        "metrics": metrics,
        "error": None,
    }


def _failed_tool(
    tool_name: str,
    summary: str,
    error: str,
) -> dict[str, Any]:
    return {
        "tool_name": tool_name,
        "status": "failed",
        "summary": summary,
        "risk_level": None,
        "metrics": {},
        "error": error,
    }
