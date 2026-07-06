from __future__ import annotations

import time
from typing import Any, Callable

from backend.app.agents.con_agent import run_con_agent
from backend.app.agents.input_parser import parse_input
from backend.app.agents.judge_agent import run_judge_agent
from backend.app.agents.pro_agent import run_pro_agent
from backend.app.schemas.decision import AgentStep, DebateResult, ToolResult, TraceItem
from backend.app.services.mcp_adapter import analyze_shopping_cost, create_cooling_reminder
from backend.app.services.mock_rag import search_mock_rag


def run_decision_flow(
    raw_input: str,
    user_id: str = "u001",
    case_id: str = "case_001",
    existing_collected_fields: dict[str, Any] | None = None,
) -> DebateResult:
    trace: list[TraceItem] = []
    steps: list[AgentStep] = []

    parser_result = _record_agent_trace(
        trace,
        "input_parser",
        raw_input,
        lambda: parse_input(raw_input, existing_collected_fields),
    )
    steps.append(parser_result.agent_step)

    if parser_result.is_high_risk:
        return DebateResult(
            success=False,
            message="HIGH_RISK_DECISION",
            case_id=case_id,
            case_status="rejected",
            steps=steps,
            rag_evidence=[],
            tool_results=[],
            report=None,
            trace=trace,
            reason=parser_result.reject_reason,
        )

    if parser_result.case_status != "ready_for_debate":
        return DebateResult(
            success=False,
            message="MISSING_FIELDS",
            case_id=case_id,
            case_status=parser_result.case_status,
            steps=steps,
            rag_evidence=[],
            tool_results=[],
            report=None,
            trace=trace,
            reason=parser_result.next_question,
        )

    fields = parser_result.merged_fields
    query = _build_rag_query(fields)
    rag_evidence = _record_trace(
        trace,
        trace_type="rag_search",
        name="rag_search",
        input_summary=query,
        func=lambda: search_mock_rag(user_id, case_id, "shopping", query, top_k=3),
        output_summary_builder=lambda result: f"返回 {len(result)} 条历史证据。",
        fallback=[],
    )

    tool_results = [
        _record_trace(
            trace,
            trace_type="tool_call",
            name="cost_analyzer",
            input_summary=f"price={fields.get('price')}, monthly_budget_left={fields.get('monthly_budget_left')}",
            # 编排层只调用 C 侧 adapter，避免 E 工具原始 dict 结构散落到流程里。
            func=lambda: analyze_shopping_cost(case_id, "shopping", fields),
            output_summary_builder=lambda result: result.summary,
            fallback=_failed_tool_result("cost_analyzer", "成本计算工具调用失败，主流程继续。", "TOOL_ERROR"),
        )
    ]

    pro_step = _record_agent_trace(
        trace,
        "pro_agent",
        fields.get("product_name", "shopping case"),
        lambda: run_pro_agent(case_id, fields, rag_evidence, tool_results),
    )
    steps.append(pro_step)

    con_step = _record_agent_trace(
        trace,
        "con_agent",
        fields.get("product_name", "shopping case"),
        lambda: run_con_agent(case_id, fields, rag_evidence, tool_results),
    )
    steps.append(con_step)

    if _should_create_reminder(tool_results, fields):
        reminder = _record_trace(
            trace,
            trace_type="tool_call",
            name="cooling_reminder",
            input_summary=f"case_id={case_id}, cooling_days=3",
            # reminder 必须在 judge 前进入 tool_results，法官才能综合工具结果。
            func=lambda: create_cooling_reminder(
                user_id=user_id,
                case_id=case_id,
                title=f"{fields.get('product_name', '商品')}冷静期复盘",
                cooling_days=3,
                reason=_cooling_reason(fields, tool_results),
                watch_items=["是否仍然需要", "是否已有低价替代品", "是否影响本月必要支出"],
            ),
            output_summary_builder=lambda result: result.summary,
            fallback=_failed_tool_result(
                "cooling_reminder",
                "冷静期提醒创建失败，建议用户手动设置复盘提醒。",
                "REMINDER_CREATE_FAILED",
            ),
        )
        tool_results.append(reminder)

    judge_step, report = _record_agent_trace(
        trace,
        "judge_agent",
        fields.get("product_name", "shopping case"),
        lambda: run_judge_agent(case_id, fields, pro_step, con_step, rag_evidence, tool_results),
        output_summary_builder=lambda result: f"final_decision={result[1].final_decision}, confidence={result[1].confidence}",
    )
    steps.append(judge_step)

    return DebateResult(
        success=True,
        message="debate completed",
        case_id=case_id,
        case_status="completed",
        steps=steps,
        rag_evidence=rag_evidence,
        tool_results=tool_results,
        report=report,
        trace=trace,
        reason=None,
    )


def _build_rag_query(fields: dict[str, Any]) -> str:
    product = str(fields.get("product_name", ""))
    purpose = str(fields.get("purpose", ""))
    inferred_tags: list[str] = []
    if any(keyword in product for keyword in ["耳机", "键盘", "电脑", "手机", "数码"]):
        inferred_tags.extend(["电子", "数码", "预算"])
    if any(keyword in purpose for keyword in ["学习", "备考", "效率", "安静", "降噪"]):
        inferred_tags.append("学习")

    parts = [
        product,
        purpose,
        str(fields.get("trigger_reason", "")),
        str(fields.get("owned_alternatives", "")),
        " ".join(inferred_tags),
    ]
    return " ".join(part for part in parts if part.strip())


def _should_create_reminder(tool_results: list[Any], fields: dict[str, Any]) -> bool:
    cost_result = next((item for item in tool_results if item.tool_name == "cost_analyzer"), None)
    trigger = fields.get("trigger_reason")
    return bool(cost_result and cost_result.risk_level in {"medium", "high"} or trigger in {"促销", "种草", "情绪"})


def _cooling_reason(fields: dict[str, Any], tool_results: list[Any]) -> str:
    cost_result = next((item for item in tool_results if item.tool_name == "cost_analyzer"), None)
    if cost_result and cost_result.status == "success":
        return cost_result.summary
    return f"{fields.get('product_name', '该商品')}存在冲动购买或预算不确定性，建议冷静 3 天后复盘。"


def _failed_tool_result(tool_name: str, summary: str, error: str) -> ToolResult:
    return ToolResult(
        tool_name=tool_name,
        status="failed",
        summary=summary,
        risk_level=None,
        metrics={},
        error=error,
    )


def _record_agent_trace(
    trace: list[TraceItem],
    name: str,
    input_summary: str,
    func: Callable[[], Any],
    output_summary_builder: Callable[[Any], str] | None = None,
) -> Any:
    return _record_trace(
        trace,
        trace_type="agent",
        name=name,
        input_summary=input_summary,
        func=func,
        output_summary_builder=output_summary_builder or _agent_output_summary,
    )


def _record_trace(
    trace: list[TraceItem],
    trace_type: str,
    name: str,
    input_summary: str,
    func: Callable[[], Any],
    output_summary_builder: Callable[[Any], str],
    fallback: Any = None,
) -> Any:
    start = time.perf_counter()
    try:
        result = func()
        duration_ms = int((time.perf_counter() - start) * 1000)
        trace.append(
            TraceItem(
                trace_id=f"trace_{len(trace) + 1:03d}",
                step=len(trace) + 1,
                type=trace_type,
                name=name,
                input_summary=str(input_summary)[:160],
                output_summary=output_summary_builder(result)[:200],
                duration_ms=duration_ms,
                status="completed",
                error=None,
            )
        )
        return result
    except Exception as exc:
        duration_ms = int((time.perf_counter() - start) * 1000)
        trace.append(
            TraceItem(
                trace_id=f"trace_{len(trace) + 1:03d}",
                step=len(trace) + 1,
                type=trace_type,
                name=name,
                input_summary=str(input_summary)[:160],
                output_summary="执行失败",
                duration_ms=duration_ms,
                status="failed",
                error=str(exc),
            )
        )
        if fallback is not None:
            return fallback
        raise


def _agent_output_summary(result: Any) -> str:
    if hasattr(result, "agent_step"):
        return result.agent_step.summary
    if isinstance(result, tuple) and result and hasattr(result[0], "summary"):
        return result[0].summary
    if hasattr(result, "summary"):
        return result.summary
    return str(result)
