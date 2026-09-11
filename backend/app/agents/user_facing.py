"""面向用户的文案清洗：把内部字段名/工具名换成自然说法。

判决书、论点、摘要都是给普通用户看的，出现 `alternative_covers_need`、`cost_analyzer`、
`MCP` 这类工程词汇会让人读不懂。清洗放在本地（确定性），而不是只靠提示词约束模型。
"""

from __future__ import annotations

import re
from typing import Any

from backend.app.schemas.decision import TOOL_LABELS, tool_label_for

# 内部标识 → 自然说法（长串在前，避免被短串抢先替换）
TERM_REPLACEMENTS: list[tuple[str, str]] = [
    ("alternative_covers_need", "已有物品能否满足需求"),
    ("expected_usage_frequency", "使用频率"),
    ("frequency_canonical", "使用频率"),
    ("trigger_canonical", "购买动机"),
    ("trigger_reason", "购买动机"),
    ("monthly_budget_left", "本月剩余预算"),
    ("owned_alternatives", "已有物品"),
    ("price_basis", "计价方式"),
    ("price_is_unit", "按单价计价"),
    ("product_name", "商品"),
    ("decision_score", "决策评分"),
    ("cost_analyzer", "成本分析"),
    ("decision_basis", "判决依据"),
    ("input_snapshot", "判定输入"),
    ("rule_version", "规则版本"),
    ("field_meta", "字段信息"),
    ("_field_conflicts", "字段冲突"),
    ("_abstained", "无依据字段"),
    ("_evidence_spans", "原文出处"),
    ("MCP 工具", "工具"),
    ("MCP工具", "工具"),
    ("MCP", "工具"),
    ("pro_agent", "正方"),
    ("con_agent", "反方"),
    ("judge_agent", "法官"),
    ("rag_evidence", "历史证据"),
    # 模型习惯写大写缩写的 RAG（真实复验："RAG证据为空"），一并去术语
    ("RAG 证据", "历史证据"),
    ("RAG证据", "历史证据"),
    ("RAG 检索", "历史检索"),
    ("RAG检索", "历史检索"),
    ("RAG", "历史检索"),
]

# 这些词出现在句子里就已经很"工程化"，整句丢弃比替换更安全
DROP_SENTENCE_MARKERS = ("_field_conflicts", "_abstained", "_evidence_spans", "field_meta")

_FIELD_LABEL_PATTERN = re.compile(
    r"\b(?:alternative_covers_need|expected_usage_frequency|frequency_canonical|trigger_canonical|"
    r"trigger_reason|monthly_budget_left|owned_alternatives|price_basis|price_is_unit|product_name|"
    r"decision_score|cost_analyzer|decision_basis|input_snapshot|rule_version)\b"
)


# 工具/评分原始模板句：模型经常把它们抄进论点，直接整句丢弃
TOOL_SENTENCE_PATTERNS = (
    r"该商品占剩余预算约",
    r"占剩余预算约\s*\d+%",
    r"风险等级为\s*(low|medium|high)",
    r"综合评分(较高|中等|较低)",
    r"建议(积极执行|暂缓后再决定|暂缓)",
    r"cost_analyzer|decision_score",
    r"两项工具均(执行)?成功",
)


PURE_TEMPLATE_PATTERNS = (
    r"^该商品占剩余预算约\s*\d+%[，,]?\s*风险等级为.*[。.]?$",
    r"^综合评分(较高|中等|较低)[，,]?\s*建议(积极执行|暂缓后再决定|暂缓)[。.]?$",
    r"^(已创建\s*\d+\s*天冷静期提醒|该商品占剩余预算约.*高风险.*)[。.]?$",
)


def _is_pure_template(sentence: str) -> bool:
    """只有"纯模板句"才整句丢弃；其余（含分析内容）保留并做术语替换。"""
    stripped = sentence.strip()
    return any(re.match(pattern, stripped, flags=re.I) for pattern in PURE_TEMPLATE_PATTERNS)


def _is_tool_sentence(sentence: str) -> bool:
    return any(re.search(pattern, sentence, flags=re.I) for pattern in TOOL_SENTENCE_PATTERNS)


def sanitize_user_text(text: Any, *, force: bool = False) -> str:
    """替换内部术语；含"纯内部标记"的句子直接丢弃。

    契约边界（T07）：`daily` / `pro_agent` / `decision_score` / `monthly_budget_left`
    这类**整体就是一个标识符或受控取值**的字符串是 API 契约，不是文案，一律原样返回。
    前端有自己的映射表（frontend/src/constants.ts），服务端改写会让前端逻辑和断言同时失效。
    `force=True` 用于明确是"给人读的话"的字段（summary/arguments/content…），
    此时即使是纯 ASCII 也照常清洗，避免 `cost_analyzer` 单独成句漏给用户。
    """
    if not isinstance(text, str) or not text.strip():
        return ""
    if not force and is_identifier_value(text):
        return text.strip()
    sentences = re.split(r"(?<=[。！？；])", text)
    kept: list[str] = []
    for sentence in sentences:
        if not sentence.strip():
            continue
        if any(marker in sentence for marker in DROP_SENTENCE_MARKERS):
            continue
        if _is_pure_template(sentence):
            continue
        cleaned = sentence
        for term, natural in TERM_REPLACEMENTS:
            cleaned = cleaned.replace(term, natural)
        kept.append(cleaned)
    result = "".join(kept).strip()
    # 替换后可能留下空括号或重复标点，做一次轻量清理
    result = re.sub(r"（\s*）|\(\s*\)", "", result)
    result = re.sub(r"[，、]{2,}", "，", result)
    result = _CONTROLLED_PATTERN.sub(lambda m: CONTROLLED_VALUE_LABELS.get(m.group(1), m.group(1)), result)
    result = _FLOAT_PATTERN.sub(r"\1", result)
    # 内部英文词（评分维度名/工具状态词）：中文文案里出现 "返回success"、"history 维度" 同样是工程腔
    result = _INTERNAL_EN_PATTERN.sub(lambda m: INTERNAL_EN_WORDS[m.group(1)], result)
    # 内部主键（含括号形式一起去掉，避免留下空括号）
    result = _INTERNAL_ID_WRAPPER_PATTERN.sub("", result)
    result = _INTERNAL_ID_PATTERN.sub("", result)
    result = re.sub(r"[ \t]{2,}", " ", result)
    # 中文之间不留空格（"成本分析 提示" → "成本分析提示"），英文与数字之间的空格保留
    result = _CJK_SPACE_PATTERN.sub("", result)
    # FINAL_SWEEP：收尾再无条件扫一遍内部词，任何调用路径都绕不过
    for term, natural in TERM_REPLACEMENTS:
        result = result.replace(term, natural)
    return _never_empty(result, text)


INTERNAL_DUMP_PATTERN = re.compile(
    r"已收集字段|_asked_fields|_evidence_spans|_parser_used|_last_question|_optional_asked|"
    r"frequency_canonical|trigger_canonical|alternative_covers_need"
)


def _never_empty(cleaned: str, original: str) -> str:
    """清洗结果为空时回退原文：宁可留一点工程腔，也不能让判决书缺段落。"""
    if cleaned.strip():
        return cleaned
    # 原文是"内部字段清单/调试串"时不要回退，否则内部词会原样漏给用户
    if INTERNAL_DUMP_PATTERN.search(original or ""):
        return ""
    return original


def sanitize_arguments(arguments: list[Any]) -> list[str]:
    """批量清洗论点，丢弃清洗后为空或与内部术语强绑定的条目。"""
    cleaned = [sanitize_user_text(item, force=True) for item in arguments or []]
    return [item for item in cleaned if item]


def has_internal_terms(text: Any) -> bool:
    """是否仍含内部字段名（供测试与断言使用）。"""
    return bool(_FIELD_LABEL_PATTERN.search(str(text or "")))


def public_fields(fields: Any) -> dict:
    """对外输出前剥离以下划线开头的内部键（_abstained/_field_conflicts/_evidence_spans 等）。"""
    if not isinstance(fields, dict):
        return {}
    return {k: v for k, v in fields.items() if not str(k).startswith("_")}


# 判定快照的键名 → 中文（快照会出现在报告里，键名不该是工程词）
SNAPSHOT_KEY_LABELS = {
    "product_name": "商品",
    "price": "价格",
    "monthly_budget_left": "本月剩余预算",
    "frequency": "使用频率",
    "trigger": "购买动机",
    "alternatives": "已有物品",
    "cost_ratio": "成本占比",
    "cost_risk": "成本风险",
    "basis": "计价口径",
    "price_basis": "计价口径",
    "quantity": "数量",
    "score": "决策评分",
    "evidence_count": "历史证据条数",
}

# 受控值（英文枚举）→ 中文；报告里不该出现 daily/weekly_3plus/need 这类内部取值
CONTROLLED_VALUE_LABELS = {
    "daily": "每天", "weekly_3plus": "每周三次以上", "weekly_1_2": "每周一两次",
    "monthly": "每月一次", "occasional": "偶尔", "unknown": "未说明",
    "need": "确实需要", "promotion": "促销打折", "recommendation": "他人推荐", "emotion": "情绪驱动",
    "total": "总价", "unit": "单价",
    # 风险档位
    "low": "低", "medium": "中等", "high": "高",
    # 计价口径取值
    "unit_price_x_quantity": "单价×数量", "unit_price": "按单价估算",
    "total_price": "按总价", "unknown": "未说明",
}
# 左右都不能紧邻标识符字符：否则 `covers_core_need` 里的 need 会被翻成"确实需要"（T06 同类事故）
_CONTROLLED_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_])"
    r"(daily|weekly_3plus|weekly_1_2|monthly|occasional|need|promotion|recommendation|emotion|"
    r"unit_price_x_quantity|unit_price|total_price|unknown|low|medium|high)"
    r"(?![A-Za-z0-9_])"
)
_FLOAT_PATTERN = re.compile(r"(\d+)\.0(?=\s*(元|块|%))")

# 纯 ASCII 标识符/受控取值：整体命中即视为机器契约，不做任何改写
_IDENTIFIER_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


def is_identifier_value(text: Any) -> bool:
    """字符串整体就是一个标识符或受控取值（daily / pro_agent / monthly_budget_left）。"""
    return isinstance(text, str) and bool(_IDENTIFIER_PATTERN.match(text.strip()))


# 内部英文词汇 → 中文。真实复验里模型写出过："两项工具均返回success"、
# "（已有物品能否满足需求 为 false）"、"usage_value 维度为 0.0、history 维度为 0.0"。
# 只在**成词**处替换（左右不紧邻标识符字符），所以 `success_rate`、`history_id` 不受影响；
# 而整体就是标识符的取值（status="success"）在 sanitize_user_text 开头就被守卫放行。
INTERNAL_EN_WORDS = {
    "usage_value": "使用价值",
    "usage_frequency": "使用频率",
    "history": "历史",
    "impulse": "冲动",
    "risk_level": "风险等级",
    "success": "成功",
    "failed": "失败",
    "true": "是",
    "false": "否",
}
_INTERNAL_EN_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_])(" + "|".join(INTERNAL_EN_WORDS) + r")(?![A-Za-z0-9_])"
)
# 中文与中文之间的空格（模型抄字段标签时留下），中文与数字/英文之间的空格保留
_CJK_SPACE_PATTERN = re.compile(r"(?<=[\u4e00-\u9fff])[ \t]+(?=[\u4e00-\u9fff])")

# 内部主键不该出现在文案里（真实复验：法官说明里出现"冷静期提醒（r_18b73537）"）。
# 注意：整体就是该 id 的取值由 sanitize_user_text 开头的标识符守卫保护，不受这里影响。
_INTERNAL_ID_PATTERN = re.compile(r"\b(?:r|case|report|event|msg|trace)_[0-9a-fA-F]{6,}\b")
_INTERNAL_ID_WRAPPER_PATTERN = re.compile(
    r"[（(]\s*(?:r|case|report|event|msg|trace)_[0-9a-fA-F]{6,}\s*[)）]"
)

PROSE_FIELDS = ("case_summary", "summary", "next_actions", "pro_points", "con_points")


def sanitize_report(report: Any) -> Any:
    """报告出参前的统一清洗：用户可见文本去工程腔，快照键名中文化。

    同时支持 dict 与 DecisionReport 这类 dataclass（judge 返回的是 dataclass，
    只处理 dict 会让清洗变成空操作）。
    """
    if not isinstance(report, dict):
        if report is None or not hasattr(report, "__dict__"):
            return report
        for field_name in PROSE_FIELDS:
            value = getattr(report, field_name, None)
            if isinstance(value, str):
                setattr(report, field_name, sanitize_user_text(value, force=True))
            elif isinstance(value, list):
                cleaned_list = [c for c in (sanitize_user_text(i, force=True) for i in value) if c]
                setattr(report, field_name, cleaned_list or list(value))
        snapshot = getattr(report, "input_snapshot", None)
        if isinstance(snapshot, dict):
            report.input_snapshot = {
                SNAPSHOT_KEY_LABELS.get(k, k): (sanitize_user_text(v) if isinstance(v, str) else v)
                for k, v in snapshot.items()
            }
        for event in getattr(report, "debate_events", None) or []:
            content = getattr(event, "content", None)
            if isinstance(content, str):
                event.content = sanitize_user_text(content, force=True)
        for point_attr in ("pro_points", "con_points"):
            value = getattr(report, point_attr, None)
            if isinstance(value, list):
                cleaned_points = [c for c in (sanitize_user_text(i, force=True) for i in value) if c]
                setattr(report, point_attr, cleaned_points or list(value))
        return report
    for field_name in PROSE_FIELDS:
        value = report.get(field_name)
        if isinstance(value, str):
            report[field_name] = sanitize_user_text(value, force=True)
        elif isinstance(value, list):
            cleaned_list = [sanitize_user_text(item, force=True) for item in value if sanitize_user_text(item, force=True)]
            report[field_name] = cleaned_list or list(value)
    snapshot = report.get("input_snapshot")
    if isinstance(snapshot, dict):
        report["input_snapshot"] = {
            SNAPSHOT_KEY_LABELS.get(k, k): (sanitize_user_text(v) if isinstance(v, str) else v)
            for k, v in snapshot.items()
        }  # SNAPSHOT_VALUE_CLEAN
    for event in report.get("debate_events") or []:
        if isinstance(event, dict) and isinstance(event.get("content"), str):
            event["content"] = sanitize_user_text(event["content"], force=True)
    return report


# 键名翻译表：只做「完全相等」匹配，绝不做子串替换。
# 教训：covers_core_need 因含子串 need 曾被翻译成"确实需要"，污染语义。
KEY_LABEL_MAP = {
    "frequency_canonical": "使用频率",
    "trigger_canonical": "购买动机",
    "expected_usage_frequency": "使用频率",
    "trigger_reason": "购买动机",
    "price_basis": "计价口径",
    "price_is_unit": "按单价计价",
    "monthly_budget_left": "本月剩余预算",
    "owned_alternatives": "已有物品",
    "product_name": "商品",
    "alternative_covers_need": "已有物品能否满足需求",
    "field_meta": "字段信息",
}

# 只在这些"非契约容器"里清洗键名；顶层契约键（final_decision/decision_basis…）绝不能改名，
# 否则调用方与前端会读不到字段（曾因此把 decision_basis 翻成"判决依据"而破坏契约）。
DEBUG_CONTAINER_KEYS = {"metrics", "field_meta", "input_snapshot", "evidence", "attributes",
                        "_field_conflicts", "_abstained", "_evidence_spans"}


# API 契约键：任何情况下都不得改名（前端与调用方依赖它们）
CONTRACT_KEYS = {
    "product_name", "price", "purpose", "monthly_budget_left", "owned_alternatives",
    "expected_usage_frequency", "trigger_reason", "quantity", "budget_ratio",
    "budget_left_after_purchase", "covers_core_need", "has", "known", "raw", "dimensions",
    "success", "data", "message", "case_id", "case_status", "final_decision", "confidence",
    "decision_basis", "decision_strength", "input_snapshot", "rule_version", "pro_points",
    "con_points", "next_actions", "summary", "case_summary", "report", "report_id", "steps",
    "rag_evidence", "tool_results", "debate_events", "trace", "trace_id", "step", "type", "name",
    "input_summary", "output_summary", "duration_ms", "status", "error", "created_at", "items",
    "total", "page", "page_size", "collected_fields", "missing_fields", "reply_plan", "title",
    "description", "user_id", "case_type", "tool_label", "metrics", "agent", "arguments",
    "used_rag_ids", "used_tool_names", "used_tool_labels", "content", "speaker", "phase", "order",
    "tags", "score", "source", "id", "warnings", "evidence", "field_meta",
}


# 这些键的值一定是"给人读的话"：即使是纯 ASCII 也必须清洗（避免工具名单独成句漏出）
PROSE_VALUE_KEYS = {
    "summary", "case_summary", "content", "reason", "next_actions", "pro_points", "con_points",
    "arguments", "title", "description", "message", "error", "input_summary", "output_summary",
    "next_question", "answer_to_user", "question", "insight", "ack",
}


def _deep_sanitize(node, sanitize_keys: bool = False, force_text: bool = False):
    """递归清洗结构里的字符串；仅在非契约容器内额外清洗键名。

    只改"文案"：标识符/受控取值（见 `sanitize_user_text`）与契约键名不动。
    """
    if isinstance(node, str):
        return sanitize_user_text(node, force=force_text)
    if isinstance(node, list):
        return [_deep_sanitize(item, sanitize_keys, force_text) for item in node]
    if isinstance(node, dict):
        result = {}
        for key, value in node.items():
            child_keys = sanitize_keys or (key in DEBUG_CONTAINER_KEYS)
            if sanitize_keys and key not in CONTRACT_KEYS:
                new_key = KEY_LABEL_MAP.get(key, key)   # 精确匹配，不做子串替换
            else:
                new_key = key
            result[new_key] = _deep_sanitize(value, child_keys, force_text or key in PROSE_VALUE_KEYS)
        return result
    return node


def public_report(report: Any) -> Any:
    """API 用户视图：补中文 tool_label，剥掉仅是调试副本的 debate_events.tool_results。

    契约字段一律保留：`tool_name`（docs/04_API.md §5.5，前端按它渲染/查表）、
    `metrics`（同一节的契约字段）、`used_tool_names`（§5.3）。
    """
    if not isinstance(report, dict):
        return report
    for tool in report.get("tool_results") or []:
        if isinstance(tool, dict):
            name = str(tool.get("tool_name", "") or "")
            if name:
                tool.setdefault("tool_label", tool_label_for(name))
    for event in report.get("debate_events") or []:
        if isinstance(event, dict):
            event.pop("tool_results", None)   # 事件级工具副本：与 steps 重复的调试载荷
    return report


def public_steps(steps: Any) -> Any:
    """步骤出参：补中文 used_tool_labels，并清洗文案；标识与契约字段保留。"""
    if not isinstance(steps, list):
        return steps
    for step in steps:
        if isinstance(step, dict):
            names = step.get("used_tool_names")
            if isinstance(names, list):
                step.setdefault("used_tool_labels", [tool_label_for(str(n)) for n in names])
            for field_name in ("arguments", "summary"):
                value = step.get(field_name)
                if isinstance(value, str):
                    step[field_name] = sanitize_user_text(value, force=True)
                elif isinstance(value, list):
                    step[field_name] = [c for c in (sanitize_user_text(i, force=True) for i in value) if c]
    return steps


# 喂给模型的 prompt 字段格式：模型未产出有效论点时不得把这些回显给用户（三方共用一份名单）
PROMPT_ECHO_MARKERS = (
    "已有替代情况：", "购买触发因素：", "应先确认现有物品", "已有替代品：", "当前收集字段",
    "已收集字段", "使用频率：", "购买动机：", "预算：", "触发因素：",
    "购买目的较明确：", "可参考正向历史证据：", "本案对",
)


# ==================== 用户视图边界：哪些路径要清洗 ====================
# 教训（T07）：边界中间件一旦"对所有 JSON 生效"，就会把调试面的原始契约一起改写。
# 调试/工具接口必须原样返回（调用方要拿 tool_name/metrics 做断言与联调），
# 所以这里用**白名单**：只有面向用户的读接口走清洗，其余一律放行。
USER_FACING_PREFIXES: tuple[str, ...] = (
    "/api/cases",      # 建案、会话、判决书、轨迹（chat 也在 /api/cases/{id}/messages 下）
    "/api/history",    # 历史记录
    "/api/watchlist",  # 冷静期清单
)

# 显式的非用户面（调试/框架）：列出来是为了让"新路由必须归类"这条约束可被测试检查
RAW_SURFACE_PREFIXES: tuple[str, ...] = (
    "/api/tools",        # 工具调试接口：契约结构原样返回
    "/api/health",
    "/auth",
    "/docs",
    "/openapi.json",
    "/redoc",
)


def _matches_prefix(path: str, prefixes: tuple[str, ...]) -> bool:
    """按路径段匹配：`/api/cases` 命中 `/api/cases` 与 `/api/cases/xxx`，不命中 `/api/casesfoo`。"""
    clean = str(path or "").rstrip("/") or "/"
    return any(clean == p or clean.startswith(p + "/") for p in prefixes)


def is_user_facing_path(path: str) -> bool:
    """该请求路径的响应是否需要按用户视图清洗。"""
    return _matches_prefix(path, USER_FACING_PREFIXES)


def is_classified_path(path: str) -> bool:
    """路径是否已被显式归类（用户面或调试面）——新路由漏归类时由测试兜底。"""
    return _matches_prefix(path, USER_FACING_PREFIXES + RAW_SURFACE_PREFIXES)

