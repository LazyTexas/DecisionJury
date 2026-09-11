from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any


CHINA_TZ = timezone(timedelta(hours=8))

# 工具标识 → 面向用户的中文名。
# 契约边界：`tool_name`/`used_tool_names` 是机器标识（docs/04_API.md §5.3/§5.5，
# 前端 frontend/src/constants.ts 自己也有映射），任何情况下都不改写；
# `tool_label`/`used_tool_labels` 是并行新增的展示名，方便非前端消费方直接渲染。
TOOL_LABELS: dict[str, str] = {
    "cost_analyzer": "成本分析",
    "decision_score": "决策评分",
    "cooling_reminder": "冷静期提醒",
}


def tool_label_for(tool_name: Any) -> str:
    """工具标识 → 中文展示名；未知工具原样返回，不吞掉信息。"""
    name = str(tool_name or "")
    return TOOL_LABELS.get(name, name)


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
    # 展示名与标识并行存在：标识给前端/调用方做逻辑，展示名给直接渲染的消费方
    used_tool_labels: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.used_tool_labels and self.used_tool_names:
            self.used_tool_labels = [tool_label_for(name) for name in self.used_tool_names]


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
    # 展示名；tool_name（契约标识）与 metrics（docs/04_API.md §5.5 契约字段）都保留
    tool_label: str = ""

    def __post_init__(self) -> None:
        if not self.tool_label:
            self.tool_label = tool_label_for(self.tool_name)


@dataclass
class DebateEvent:
    event_id: str
    order: int
    speaker: str
    phase: str
    content: str
    evidence: list[str] = field(default_factory=list)
    status: str = "completed"


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
    debate_events: list[DebateEvent] = field(default_factory=list)
    # 判决依据：命中的规则、说明与影响，供报告与页面展示“为什么这么判”。
    decision_basis: list[dict[str, str]] = field(default_factory=list)
    # 结论强度：命中硬约束/高频放行等确定性高的规则更高，兜底规则最低。
    decision_strength: float | None = None
    # 可复算信息：规则版本与当时的判定输入，便于事后复盘“当时为什么这么判”。
    rule_version: str | None = None
    input_snapshot: dict[str, Any] = field(default_factory=dict)


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
    correction_fields: dict[str, Any] = field(default_factory=dict)
    # C 模块扩展信息均为可选，保持旧调用方按原字段构造/读取时兼容。
    field_meta: dict[str, Any] = field(default_factory=dict)
    conflicts: list[dict[str, Any]] = field(default_factory=list)
    next_question_key: str | None = None
    is_complete: bool = False
    termination_reason: str | None = None
    parser_used: str | None = None
    # 收集阶段的回复计划：承接句、一个问题、快捷选项、是否可结束（见 reply_composer）。
    reply_plan: dict[str, Any] = field(default_factory=dict)
    # 模型给出的对话文案（ack/insight/question/chips/intent），由本地护栏裁剪后使用。
    dialogue: dict[str, Any] = field(default_factory=dict)


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
    debate_events: list[DebateEvent] = field(default_factory=list)
