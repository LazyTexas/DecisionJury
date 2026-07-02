from __future__ import annotations

from typing import Any

from backend.app.schemas.decision import AgentStep, DecisionReport, RagEvidence, ToolResult, now_iso


def run_judge_agent(
    case_id: str,
    collected_fields: dict[str, Any],
    pro_step: AgentStep,
    con_step: AgentStep,
    rag_evidence: list[RagEvidence],
    tool_results: list[ToolResult],
) -> tuple[AgentStep, DecisionReport]:
    cost_result = next((item for item in tool_results if item.tool_name == "cost_analyzer"), None)
    final_decision = _decide(collected_fields, rag_evidence, cost_result)
    confidence = _confidence(rag_evidence, cost_result)
    product = collected_fields.get("product_name", "该商品")
    price = collected_fields.get("price", "未知价格")
    purpose = collected_fields.get("purpose", "未说明用途")

    summary = _summary(final_decision, product, rag_evidence)
    next_actions = _next_actions(final_decision, rag_evidence, cost_result)
    report = DecisionReport(
        report_id=f"report_{case_id}",
        case_id=case_id,
        case_type="shopping",
        final_decision=final_decision,
        confidence=confidence,
        summary=summary,
        case_summary=f"用户想购买 {price} 元的{product}，主要用途是{purpose}。",
        pro_points=pro_step.arguments,
        con_points=con_step.arguments,
        rag_evidence=rag_evidence,
        tool_results=tool_results,
        next_actions=next_actions,
        created_at=now_iso(),
    )
    judge_step = AgentStep(
        agent="judge_agent",
        status="completed",
        summary=f"综合正反方、RAG 与工具结果，建议：{final_decision}。",
        confidence=confidence,
        arguments=_judge_arguments(final_decision, rag_evidence, cost_result),
        used_rag_ids=[item.id for item in rag_evidence],
        used_tool_names=[item.tool_name for item in tool_results],
        error=None,
    )
    return judge_step, report


def _decide(fields: dict[str, Any], rag_evidence: list[RagEvidence], cost_result: ToolResult | None) -> str:
    risk_level = cost_result.risk_level if cost_result and cost_result.status == "success" else None
    alternatives = str(fields.get("owned_alternatives", ""))
    frequency = str(fields.get("expected_usage_frequency", ""))
    trigger = str(fields.get("trigger_reason", ""))
    has_risk_history = any(any(tag in item.tags for tag in ["idle", "regret", "budget"]) for item in rag_evidence)

    if risk_level == "high":
        return "reject"
    if risk_level == "medium" or trigger in {"促销", "种草", "情绪"} or has_risk_history:
        return "delay"
    if alternatives not in {"无", "没有"} and alternatives:
        return "alternative"
    if frequency in {"每天", "每日", "经常", "高频"}:
        return "buy"
    return "delay"


def _confidence(rag_evidence: list[RagEvidence], cost_result: ToolResult | None) -> float:
    confidence = 0.72
    if rag_evidence:
        confidence += 0.08
    else:
        confidence -= 0.12
    if cost_result and cost_result.status == "success":
        confidence += 0.05
    elif cost_result:
        confidence -= 0.1
    return round(max(0.3, min(confidence, 0.9)), 2)


def _summary(final_decision: str, product: str, rag_evidence: list[RagEvidence]) -> str:
    labels = {
        "buy": "可以考虑购买",
        "delay": "建议暂缓购买 3 天后复盘",
        "reject": "当前不建议购买",
        "alternative": "建议先寻找替代方案",
    }
    suffix = "" if rag_evidence else " 未找到相关历史证据，本次判断主要基于当前输入和工具结果。"
    return f"本案对{product}的辅助建议是：{labels[final_decision]}。{suffix}"


def _next_actions(final_decision: str, rag_evidence: list[RagEvidence], cost_result: ToolResult | None) -> list[str]:
    actions: list[str] = []
    if final_decision in {"delay", "alternative"}:
        actions.append("加入观察清单，3 天后复盘真实需求。")
        actions.append("比较已有替代品或低价替代方案能否满足核心用途。")
    if final_decision == "buy":
        actions.append("购买前再次确认不会影响本月必要支出。")
    if final_decision == "reject":
        actions.append("记录本次放弃原因，避免被同类促销反复触发。")
    if not rag_evidence:
        actions.append("未找到相关历史证据，建议后续补充购买复盘记录。")
    if cost_result and cost_result.status == "failed":
        actions.append("预算工具不可用，建议手动核对本月剩余预算。")
    return actions


def _judge_arguments(
    final_decision: str,
    rag_evidence: list[RagEvidence],
    cost_result: ToolResult | None,
) -> list[str]:
    arguments = [f"最终建议为 {final_decision}。"]
    if cost_result:
        arguments.append(cost_result.summary)
    if rag_evidence:
        arguments.append(f"引用 {len(rag_evidence)} 条真实返回的 RAG 历史证据。")
    else:
        arguments.append("未找到相关历史证据，没有编造历史记录。")
    return arguments
