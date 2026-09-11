from __future__ import annotations

from typing import Any

from backend.app.schemas.decision import AgentStep, RagEvidence, ToolResult
from backend.app.agents.user_facing import (
    PROMPT_ECHO_MARKERS as ECHO_MARKERS,
    sanitize_arguments,
    sanitize_user_text,
)

from backend.app.services.llm_client import DEGRADED_REASON_KEY, debate_context_fields, get_llm_client


def run_pro_agent(
    case_id: str,
    collected_fields: dict[str, Any],
    rag_evidence: list[RagEvidence],
    tool_results: list[ToolResult],
) -> AgentStep:
    _ = case_id
    llm = get_llm_client()
    response = llm.complete_json(
        "pro_agent",
        {
            "collected_fields": debate_context_fields(collected_fields),
            # 真实 LLM 需要看到证据内容和工具状态；对外 AgentStep 字段仍只记录 id/name。
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
    useful_rag_ids = [item.id for item in rag_evidence if "useful" in item.tags or "study" in item.tags]
    degraded = response.pop(DEGRADED_REASON_KEY, None)
    if degraded:
        # 真实模型没回答：如实标注，绝不用 mock 模板冒充正方论点。
        return AgentStep(
            agent="pro_agent",
            status="failed",
            summary="模型调用失败，本轮未能生成正方观点。",
            confidence=0.0,
            arguments=[],
            used_rag_ids=useful_rag_ids,
            used_tool_names=[result.tool_name for result in tool_results if result.status == "success"],
            error=f"llm_degraded:{degraded}",
        )
    arguments = list(response["arguments"])
    if useful_rag_ids:
        arguments.append(f"可参考正向历史证据：{', '.join(useful_rag_ids)}")
    _filtered = [a for a in sanitize_arguments(arguments) if not any(mm in a for mm in ECHO_MARKERS)]
    fallback_used = not _filtered
    arguments = _filtered or ["本轮正方未生成有效论点，主要风险与依据见判决说明。"]
    return AgentStep(
        agent="pro_agent",
        status="completed",
        summary=sanitize_user_text(response["summary"], force=True),
        confidence=float(response["confidence"]),
        arguments=arguments,
        used_rag_ids=useful_rag_ids,
        used_tool_names=[result.tool_name for result in tool_results if result.status == "success"],
        error=("argument_fallback:model_gave_no_argument" if fallback_used else None),
    )
