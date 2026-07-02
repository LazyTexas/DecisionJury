from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any


CHINA_TZ = timezone(timedelta(hours=8))


def now_iso() -> str:
    return datetime.now(CHINA_TZ).replace(microsecond=0).isoformat()


def to_dict(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        return asdict(value)
    if isinstance(value, list):
        return [to_dict(item) for item in value]
    if isinstance(value, dict):
        return {key: to_dict(item) for key, item in value.items()}
    return value


@dataclass
class AgentStep:
    agent: str
    status: str
    summary: str
    confidence: float
    arguments: list[str]
    used_rag_ids: list[str] = field(default_factory=list)
    used_tool_names: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass
class RagEvidence:
    id: str
    title: str
    content: str
    score: float
    source: str
    case_type: str
    tags: list[str]
    created_at: str | None


@dataclass
class ToolResult:
    tool_name: str
    status: str
    summary: str
    risk_level: str | None
    metrics: dict[str, Any]
    error: str | None = None


@dataclass
class DecisionReport:
    report_id: str
    case_id: str
    case_type: str
    final_decision: str
    confidence: float
    summary: str
    case_summary: str
    pro_points: list[str]
    con_points: list[str]
    rag_evidence: list[RagEvidence]
    tool_results: list[ToolResult]
    next_actions: list[str]
    created_at: str


@dataclass
class TraceItem:
    trace_id: str
    step: int
    type: str
    name: str
    input_summary: str
    output_summary: str
    duration_ms: int
    status: str
    error: str | None = None


@dataclass
class ParserResult:
    case_type: str | None
    is_supported: bool
    is_high_risk: bool
    reject_reason: str | None
    extracted_fields: dict[str, Any]
    merged_fields: dict[str, Any]
    missing_fields: list[str]
    next_question: str | None
    case_status: str
    agent_step: AgentStep


@dataclass
class DebateResult:
    success: bool
    message: str
    case_id: str
    case_status: str
    steps: list[AgentStep]
    rag_evidence: list[RagEvidence]
    tool_results: list[ToolResult]
    report: DecisionReport | None
    trace: list[TraceItem]
    reason: str | None = None
