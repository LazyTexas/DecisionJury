from __future__ import annotations

from typing import Any

from backend.app.schemas.decision import AgentStep, RagEvidence, ToolResult
from backend.app.services.llm_client import get_llm_client


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
            "collected_fields": collected_fields,
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
    arguments = list(response["arguments"])
    # 不再把工具 summary 直接塞进论点：模型已在 prompt 里拿到 tool_results，
    # 原文照搬会出现“该商品占剩余预算约 25%，风险等级为 medium。”这种注水论点。
    if cost_result and cost_result.status != "success":
        arguments.append("成本工具本次不可用，预算数据需人工核对。")
    if risk_rag_ids:
        arguments.append(f"历史复盘中有 {len(risk_rag_ids)} 条与闲置/后悔相关的记录，值得参考。")
    return AgentStep(
        agent="con_agent",
        status="completed",
        summary=response["summary"],
        confidence=float(response["confidence"]),
        arguments=arguments,
        used_rag_ids=risk_rag_ids,
        used_tool_names=[result.tool_name for result in tool_results if result.status == "success"],
        error=None,
    )
