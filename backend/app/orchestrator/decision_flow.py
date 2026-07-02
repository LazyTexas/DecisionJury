from __future__ import annotations

import time
from typing import Any, Callable

from backend.app.agents.con_agent import run_con_agent
from backend.app.agents.input_parser import parse_input
from backend.app.agents.judge_agent import run_judge_agent
from backend.app.agents.pro_agent import run_pro_agent
from backend.app.schemas.decision import AgentStep, DebateResult, TraceItem
from backend.app.services.mock_mcp import cooling_reminder, cost_analyzer
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
    )

    tool_results = [
        _record_trace(
            trace,
            trace_type="tool_call",
            name="cost_analyzer",
            input_summary=f"price={fields.get('price')}, monthly_budget_left={fields.get('monthly_budget_left')}",
            func=lambda: cost_analyzer(case_id, "shopping", fields),
            output_summary_builder=lambda result: result.summary,
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

    judge_step, report = _record_agent_trace(
        trace,
        "judge_agent",
        fields.get("product_name", "shopping case"),
        lambda: run_judge_agent(case_id, fields, pro_step, con_step, rag_evidence, tool_results),
        output_summary_builder=lambda result: f"final_decision={result[1].final_decision}, confidence={result[1].confidence}",
    )
    steps.append(judge_step)

    if _should_create_reminder(report.final_decision, tool_results, fields):
        reminder = _record_trace(
            trace,
            trace_type="tool_call",
            name="cooling_reminder",
            input_summary=f"case_id={case_id}, cooling_days=3",
            func=lambda: cooling_reminder(
                user_id=user_id,
                case_id=case_id,
                title=f"{fields.get('product_name', '商品')}冷静期复盘",
                cooling_days=3,
                reason=report.summary,
                watch_items=["是否仍然需要", "是否已有低价替代品", "是否影响本月必要支出"],
            ),
            output_summary_builder=lambda result: result.summary,
        )
        tool_results.append(reminder)
        report.tool_results = tool_results
        if reminder.status == "success":
            report.next_actions.append("冷静期提醒已创建，可按期复盘。")
        else:
            report.next_actions.append("提醒创建失败，建议手动设置 3 天后复盘。")
        judge_step.used_tool_names.append("cooling_reminder")

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


def _should_create_reminder(report_decision: str, tool_results: list[Any], fields: dict[str, Any]) -> bool:
    if report_decision in {"delay", "alternative"}:
        return True
    cost_result = next((item for item in tool_results if item.tool_name == "cost_analyzer"), None)
    trigger = fields.get("trigger_reason")
    return bool(cost_result and cost_result.risk_level in {"medium", "high"} or trigger in {"促销", "种草", "情绪"})


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
        raise


def _agent_output_summary(result: Any) -> str:
    if hasattr(result, "agent_step"):
        return result.agent_step.summary
    if isinstance(result, tuple) and result and hasattr(result[0], "summary"):
        return result[0].summary
    if hasattr(result, "summary"):
        return result.summary
    return str(result)
