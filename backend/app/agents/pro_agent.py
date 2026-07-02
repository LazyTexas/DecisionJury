from __future__ import annotations

from typing import Any

from backend.app.schemas.decision import AgentStep, RagEvidence, ToolResult
from backend.app.services.llm_client import get_llm_client


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
            "collected_fields": collected_fields,
            "rag_evidence": [item.id for item in rag_evidence],
            "tool_results": [item.tool_name for item in tool_results],
        },
    )
    useful_rag_ids = [item.id for item in rag_evidence if "useful" in item.tags or "study" in item.tags]
    arguments = list(response["arguments"])
    if useful_rag_ids:
        arguments.append(f"可参考正向历史证据：{', '.join(useful_rag_ids)}")
    return AgentStep(
        agent="pro_agent",
        status="completed",
        summary=response["summary"],
        confidence=float(response["confidence"]),
        arguments=arguments,
        used_rag_ids=useful_rag_ids,
        used_tool_names=[result.tool_name for result in tool_results if result.status == "success"],
        error=None,
    )
