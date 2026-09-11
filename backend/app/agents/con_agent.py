from __future__ import annotations

from typing import Any

from backend.app.schemas.decision import AgentStep, RagEvidence, ToolResult
from backend.app.agents.user_facing import (
    PROMPT_ECHO_MARKERS as ECHO_MARKERS,
    sanitize_arguments,
    sanitize_user_text,
)

from backend.app.services.llm_client import DEGRADED_REASON_KEY, debate_context_fields, get_llm_client


def run_con_agent(
    case_id: str,
    collected_fields: dict[str, Any],
    rag_evidence: list[RagEvidence],
    tool_results: list[ToolResult],
) -> AgentStep:
    _ = case_id
    llm = get_llm_client()
    response = llm.complete_json(
        "con_agent",
        {
            "collected_fields": debate_context_fields(collected_fields),
            # 传给真实 LLM 的上下文保留失败状态，便于模型说明工具结果的不确定性。
            "rag_evidence": [
                {
                    "id": item.id,
                    "title": item.title,
                    "content": item.content,
                    "tags": item.tags,
                }
                for item in rag_evidence
            ],
            "tool_results": [
                {
                    "tool_name": item.tool_name,
                    "status": item.status,
                    "summary": item.summary,
                    "risk_level": item.risk_level,
                    "metrics": item.metrics,
                    "error": item.error,
                }
                for item in tool_results
            ],
        },
    )
    risk_rag_ids = [
        item.id
        for item in rag_evidence
        if any(tag in item.tags for tag in ["idle", "regret", "budget", "cooling"])
    ]
    cost_result = next((item for item in tool_results if item.tool_name == "cost_analyzer"), None)
    degraded = response.pop(DEGRADED_REASON_KEY, None)
    if degraded:
        # 真实模型没回答：如实标注，绝不用 mock 模板冒充反方论点。
        return AgentStep(
            agent="con_agent",
            status="failed",
            summary="模型调用失败，本轮未能生成反方观点。",
            confidence=0.0,
            arguments=[],
            used_rag_ids=risk_rag_ids,
            used_tool_names=[result.tool_name for result in tool_results if result.status == "success"],
            error=f"llm_degraded:{degraded}",
        )
    arguments = list(response["arguments"])
    # 不再把工具 summary 直接塞进论点：模型已在 prompt 里拿到 tool_results，
    # 原文照搬会出现“该商品占剩余预算约 25%，风险等级为 medium。”这种注水论点。
    if cost_result and cost_result.status != "success":
        arguments.append("成本工具本次不可用，预算数据需人工核对。")
    if risk_rag_ids:
        arguments.append(f"历史复盘中有 {len(risk_rag_ids)} 条与闲置/后悔相关的记录，值得参考。")
    _filtered = [a for a in sanitize_arguments(arguments) if not any(mm in a for mm in ECHO_MARKERS)]
    fallback_used = not _filtered
    arguments = _filtered or ["本轮反方未生成有效论点，主要风险与依据见判决说明。"]
    return AgentStep(
        agent="con_agent",
        status="completed",
        summary=sanitize_user_text(response["summary"], force=True),
        confidence=float(response["confidence"]),
        arguments=arguments,
        used_rag_ids=risk_rag_ids,
        used_tool_names=[result.tool_name for result in tool_results if result.status == "success"],
        error=("argument_fallback:model_gave_no_argument" if fallback_used else None),
    )
