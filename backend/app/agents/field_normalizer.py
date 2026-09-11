"""字段归一化：把 parser 产出的自然语言字段映射为决策层可复用的受控值。

背景（本轮修复）：
    上游（LLM parser / 本地规则）写入的是自由文本，例如
    `expected_usage_frequency="每天使用"`、`owned_alternatives="暂无"`、
    `trigger_reason="朋友推荐"`；而下游判决与评分工具此前用 `in {...}` 做精确
    字符串比较，导致同一语义换个说法就得到不同结论：
        "每天" -> buy   /  "每天使用" -> delay
        "没有" -> 视为无替代品 / "暂无" -> 被当成“有替代品”
        "促销" -> delay / "朋友推荐" -> buy
    本模块把这类字段统一归一到受控枚举，判决（judge_agent）与评分
    （mcp_adapter -> decision_score）共用同一份实现，避免多处各写一套词表。

约定：
    - 已经是受控值的输入保持幂等（英文枚举原样返回）。
    - 无法识别时返回 `unknown`，由调用方按“信息不足”处理，不猜。
    - 原始文本由调用方保留在 `field_meta` / `collected_fields` 中，便于追溯。
"""

from __future__ import annotations

import re
from typing import Any

# ==================== 使用频率 ====================

FREQ_DAILY = "daily"
FREQ_WEEKLY_3PLUS = "weekly_3plus"
FREQ_WEEKLY_1_2 = "weekly_1_2"
FREQ_MONTHLY = "monthly"
FREQ_OCCASIONAL = "occasional"
FREQ_UNKNOWN = "unknown"

FREQUENCY_VALUES = {
    FREQ_DAILY,
    FREQ_WEEKLY_3PLUS,
    FREQ_WEEKLY_1_2,
    FREQ_MONTHLY,
    FREQ_OCCASIONAL,
    FREQ_UNKNOWN,
}

# 顺序敏感：先判“每天”，再判每周三次以上，最后才是每周一两次。
_FREQUENCY_PATTERNS: list[tuple[str, str]] = [
    (FREQ_DAILY, r"(每天|每日|天天|每一天|一周七天|每周七天|每星期七天|日常使用|日常都用|基本每天|几乎每天)"),
    (FREQ_WEEKLY_3PLUS, r"(高频|经常|频繁|每周[三四五六七3-7]|一周[三四五六七3-7]|每星期[三四五六七3-7]"
                        r"|(每周|一周|每星期)\s*(?:用|吃|跑|练|去|做|喝|看|玩|买|开)?\s*[三四五六七3-7]"
                        r"|[一二两2]\s*[到至~\-]?\s*[三四五六3-5]\s*次|[三四五六七3-7]\s*到\s*[四五3-5]\s*次)"),
    (FREQ_WEEKLY_1_2, r"(每周[一二两1-2]次?|一周[一二两1-2]次?|每星期[一二两1-2]次?"
                      r"|(每周|一周|每星期)\s*(?:用|吃|跑|练|去|做|喝|看|玩|买|开)?\s*[一二两1-2]\s*次"
                      r"|[一二两1-2]\s*[到至~\-]?\s*[一二两1-2]\s*次)"),
    (FREQ_MONTHLY, r"(每月|每个月|一月一次|月均)"),
    (FREQ_OCCASIONAL, r"(偶尔|很少|低频|几乎不用|很少用|不一定)"),
]

HIGH_FREQUENCY_VALUES = {FREQ_DAILY, FREQ_WEEKLY_3PLUS}


def normalize_frequency(raw: Any) -> str:
    """把使用频率自由文本归一为受控值；识别不了返回 unknown。"""
    text = _clean(raw)
    if not text:
        return FREQ_UNKNOWN
    if text in FREQUENCY_VALUES:
        return text
    # 否定优先：'不是每天用，只是偶尔' 不能因为含'每天'被判成 daily。
    negated = re.sub(r"不(是|算|太|怎么|会)?\s*(每天|每日|天天|经常|高频)", " ", text)
    # 日期词里的"天天"不是频率：'今天天气不错' 曾被误判为 daily（蜕变测试抓出）。
    negated = re.sub(r"[今明后昨前]天", " ", negated)
    for value, pattern in _FREQUENCY_PATTERNS:
        if re.search(pattern, negated):
            return value
    return FREQ_UNKNOWN


def is_high_frequency(value: str) -> bool:
    """高频使用：每天 / 每周三次以上。"""
    return value in HIGH_FREQUENCY_VALUES


def resolve_frequency(fields: Any) -> tuple[str, bool]:
    """频率取值 + 冲突标记。

    受控值优先，但**不与文本归一结果矛盾时**才采信；两者不一致说明模型自述与用户
    原话冲突（例如受控值 daily、原话“只是偶尔”），此时降级为 unknown 并标记冲突，
    避免"模型给错受控值反而覆盖正确文本"。

    例外（真实事故）：受控值为 `unknown` 时它**不是主张、只是"模型不知道"**，
    不该与用户明确说过的文本冲突。用户实测案例：原话"一周三次"（归一 weekly_3plus）
    被模型的 `frequency_canonical="unknown"` 判成冲突、降级为"未说明"，
    判决依据出现 E5、结论从 alternative 翻成 reject。现在 unknown 让位给文本归一值。
    """
    if not isinstance(fields, dict):
        return normalize_frequency(fields), False
    canonical = fields.get("frequency_canonical")
    canonical = canonical if isinstance(canonical, str) and canonical in FREQUENCY_VALUES else None
    if canonical == FREQ_UNKNOWN:
        canonical = None
    text_value = normalize_frequency(fields.get("expected_usage_frequency"))
    if canonical and text_value != FREQ_UNKNOWN and canonical != text_value:
        return FREQ_UNKNOWN, True
    return (canonical or text_value), False


def resolve_trigger(fields: Any) -> tuple[str, bool]:
    """触发原因取值 + 冲突标记（规则同上：`unknown` 不是主张，让位给文本归一）。"""
    if not isinstance(fields, dict):
        return normalize_trigger(fields), False
    canonical = fields.get("trigger_canonical")
    canonical = canonical if isinstance(canonical, str) and canonical in TRIGGER_VALUES else None
    if canonical == TRIGGER_UNKNOWN:
        canonical = None
    text_value = normalize_trigger(fields.get("trigger_reason"))
    if canonical and text_value != TRIGGER_UNKNOWN and canonical != text_value:
        return TRIGGER_UNKNOWN, True
    return (canonical or text_value), False


def canonical_frequency(fields: Any) -> str:
    """频率取用入口：优先模型直接给出的受控值，其次才从自由文本归一。

    契约优先后，"猜中文"只在模型没给受控值（或走了本地兜底）时发生。
    受控值与文本冲突时按 unknown 处理（见 resolve_frequency）。
    """
    return resolve_frequency(fields)[0]


def canonical_trigger(fields: Any) -> str:
    """触发原因取用入口：优先受控值，其次才从自由文本归一；冲突时按 unknown。"""
    return resolve_trigger(fields)[0]


# ==================== 触发原因 ====================

TRIGGER_NEED = "need"
TRIGGER_PROMOTION = "promotion"
TRIGGER_RECOMMENDATION = "recommendation"
TRIGGER_EMOTION = "emotion"
TRIGGER_UNKNOWN = "unknown"

TRIGGER_VALUES = {
    TRIGGER_NEED,
    TRIGGER_PROMOTION,
    TRIGGER_RECOMMENDATION,
    TRIGGER_EMOTION,
    TRIGGER_UNKNOWN,
}

_TRIGGER_PATTERNS: list[tuple[str, str]] = [
    (TRIGGER_PROMOTION, r"(促销|打折|降价|优惠|满减|秒杀|大促|特价|活动价|折扣)"),
    (TRIGGER_RECOMMENDATION, r"(种草|推荐|社交影响|别人有|同事买了|看到别人用|跟风|网红|博主)"),
    (TRIGGER_EMOTION, r"(情绪|冲动|心情|压力|奖励自己|报复性|焦虑|不开心)"),
    (TRIGGER_NEED, r"(刚需|必需|坏了|坏掉|损坏|开胶|不能用|没法用|用不了|用完了|用完|缺一个|不保暖|翻烂|磨破|过敏|医生建议|身体|腰疼|颈椎|睡眠|睡不好|健康|治疗|康复|需要|备考|工作要用)"),
]

IMPULSE_TRIGGER_VALUES = {TRIGGER_PROMOTION, TRIGGER_RECOMMENDATION, TRIGGER_EMOTION}


def normalize_trigger(raw: Any) -> str:
    """把触发原因自由文本归一为受控值；识别不了返回 unknown。"""
    text = _clean(raw)
    if not text:
        return TRIGGER_UNKNOWN
    if text in TRIGGER_VALUES:
        return text
    for value, pattern in _TRIGGER_PATTERNS:
        if re.search(pattern, text):
            return value
    return TRIGGER_UNKNOWN


def is_impulse_trigger(value: str) -> bool:
    """冲动型触发（促销 / 他人推荐 / 情绪），需要冷静期而不是直接放行。"""
    return value in IMPULSE_TRIGGER_VALUES


# ==================== 已有替代品 ====================

# 整句等于这些写法 = 明确“没有替代品”。
_ALTERNATIVE_NEGATION_EXACT = {
    "无", "没有", "暂无", "暂时没有", "没", "无替代品", "没有替代品",
    "暂无替代品", "没有其他", "无其他", "none", "no", "null",
}
# 以这些前缀开头 = 明确“没有替代品”（覆盖“没有其他水果”“无其他替代品”这类带宾语的写法）。
_ALTERNATIVE_NEGATION_PREFIXES = (
    "没有", "暂无", "暂时没有", "无其他", "无类似", "没有任何", "没别的", "没其他",
)


def normalize_alternatives(raw: Any, covers_core_need: Any = None) -> dict[str, Any]:
    """归一已有替代品字段。

    返回：
        {
          "has": bool,               # 用户是否提到了已有的替代品/同类物品
          "known": bool,             # 该判断是否有明确依据（空值时为 False）
          "items": list[str],        # 提到的替代品文本（无则空列表）
          "covers_core_need": bool | None,  # 是否覆盖核心需求；None 表示未知
          "raw": str,
        }

    只有 `covers_core_need is True`（明确能覆盖核心需求）才足以把结论推向
    `alternative`；仅仅“提到已有物品”不足以否决购买（见 judge_agent）。
    """
    text = _clean(raw)
    covers = _as_bool(covers_core_need)

    if not text:
        return {"has": False, "known": False, "items": [], "covers_core_need": covers, "raw": ""}

    lowered = text.lower()
    if lowered in _ALTERNATIVE_NEGATION_EXACT or text in _ALTERNATIVE_NEGATION_EXACT:
        return {"has": False, "known": True, "items": [], "covers_core_need": covers, "raw": text}
    if text.startswith(_ALTERNATIVE_NEGATION_PREFIXES):
        return {"has": False, "known": True, "items": [], "covers_core_need": covers, "raw": text}

    return {"has": True, "known": True, "items": [text], "covers_core_need": covers, "raw": text}


# ==================== 证据相关性 ====================

RISK_TAGS = {"idle", "regret", "budget", "cooling"}


def evidence_is_relevant(item: Any, fields: dict[str, Any]) -> bool:
    """历史证据是否与本案相关（用于决定它能不能影响判决）。

    之前只要召回证据带 idle/regret/budget 标签就会把结论打成 delay，而 BM25
    是词面检索，可能召回“围巾”“人体工学椅”这类无关记录，造成无关历史一票否决。
    这里用“类目一致 + 商品名词面重合”做最小相关性门槛：
        - 取不到商品名 -> 无法判断相关性，返回 False（只展示，不参与判决）。
        - 商品名出现在证据标题/正文，或与标题/正文有 2 字以上的片段重合 -> 相关。
    """
    product = _clean(fields.get("product_name"))
    if not product:
        return False

    case_type = getattr(item, "case_type", None)
    if case_type and case_type != "shopping":
        return False

    text = f"{getattr(item, 'title', '')} {getattr(item, 'content', '')}"
    if not text.strip():
        return False
    if product in text:
        return True

    # 中文商品名常带修饰词（“无线降噪耳机” vs “降噪耳机”），退化为 2~4 字片段重合。
    for size in (4, 3, 2):
        for start in range(0, max(len(product) - size + 1, 1)):
            fragment = product[start:start + size]
            if len(fragment) == size and fragment in text:
                return True
    return False


def split_evidence_by_relevance(
    rag_evidence: list[Any], fields: dict[str, Any]
) -> tuple[list[Any], list[Any]]:
    """把证据拆成 (相关, 无关)；无关证据只用于展示，不参与判决。"""
    related: list[Any] = []
    unrelated: list[Any] = []
    for item in rag_evidence:
        (related if evidence_is_relevant(item, fields) else unrelated).append(item)
    return related, unrelated


def has_related_risk_evidence(related: list[Any]) -> bool:
    """相关证据里是否存在风险信号（闲置 / 后悔 / 预算 / 冷静期）。"""
    return any(RISK_TAGS.intersection(set(getattr(item, "tags", []) or [])) for item in related)


# ==================== 内部工具 ====================


def _clean(raw: Any) -> str:
    if raw is None:
        return ""
    text = str(raw).strip()
    return re.sub(r"\s+", " ", text)


def _as_bool(value: Any) -> bool | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"true", "1", "yes", "y", "是", "能", "可以"}:
            return True
        if text in {"false", "0", "no", "n", "否", "不能", "不可以"}:
            return False
    return None
