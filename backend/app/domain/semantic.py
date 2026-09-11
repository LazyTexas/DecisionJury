"""类型化语义表示（唯一事实层）：判决与评分只读这里构造出的对象。

设计依据：
- 富槽位/属性化状态（Enriched Dialog States）：槽位值不是裸字符串，而是带属性的结构；
- 否定作用域检测（NegEx / PyConText 一路）：先判断否定线索及其作用域，再取值，
  而不是"看到关键词就算命中"；
- 数量-单位联合抽取（CQE）：金额 = 数值 + 单位 + 计价口径（单价/总价）+ 数量。

构造规则（build_facts）：
1. 受控值优先（模型直接给的枚举），缺失时才从中文自由文本归一；
2. 受控值与原话冲突 → 取 unknown 并记 conflict；
3. 单价只有在"入库价格 == 原话里的单价值"时才成立，避免总价被再乘一次数量。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from backend.app.agents.field_normalizer import (
    FREQ_UNKNOWN,
    FREQUENCY_VALUES,
    TRIGGER_UNKNOWN,
    TRIGGER_VALUES,
    normalize_frequency,
    normalize_trigger,
    normalize_alternatives,
)

# 否定线索（长词优先，避免"不是"被"不"抢先匹配）
NEGATION_CUES = ("不是", "不算", "不太", "不怎么", "并没有", "没有", "没", "不", "非", "无", "别", "无需", "不用")
# 取值关键词：用于判断"否定是否作用在这个值上"
VALUE_KEYWORDS = {
    "frequency": ("每天", "每日", "天天", "每天用", "经常", "高频", "一周", "每周", "偶尔", "很少"),
    "trigger": ("刚需", "需要", "坏了", "促销", "打折", "推荐", "种草", "情绪", "冲动"),
    "alternative": ("有", "还在用", "能用", "旧"),
}


def negation_scope(text: str, keywords: tuple[str, ...], window: int = 6) -> tuple[bool, str]:
    """判断否定是否作用在某个取值关键词上，返回（是否被否定, 命中的否定线索）。

    只做"否定线索 → 关键词"的窗口内检测：线索出现在关键词之前且距离不超过 window 个字符，
    即认为该关键词处在否定作用域内（如"不是每天用""没有其他水果"）。
    """
    cleaned = text or ""
    for keyword in keywords:
        start = cleaned.find(keyword)
        if start < 0:
            continue
        left = cleaned[max(0, start - window):start]
        for cue in NEGATION_CUES:
            if cue in left:
                return True, cue
    return False, ""


@dataclass(frozen=True)
class Polarized:
    """带极性的取值：值 + 是否被否定 + 否定线索。"""

    value: str
    negated: bool = False
    cue: str = ""

    @property
    def effective(self) -> str:
        """被否定的取值不参与判决（按 unknown 处理）。"""
        return "unknown" if self.negated else self.value


@dataclass(frozen=True)
class Money:
    """金额：数值 + 计价口径 + 单位 + 数量。"""

    amount: float | None = None
    basis: str = "total"          # unit | total
    unit: str | None = None
    quantity: float | None = None

    @property
    def effective_amount(self) -> float | None:
        """进入成本计算的口径：单价 × 数量（有数量时），否则按原值估算。"""
        if self.amount is None:
            return None
        if self.basis == "unit" and self.quantity:
            return self.amount * self.quantity
        return self.amount

    @property
    def is_estimate(self) -> bool:
        """单价且数量未知 → 只能估算，不允许走小额放行。"""
        return self.basis == "unit" and not self.quantity


@dataclass(frozen=True)
class Frequency:
    canonical: str = FREQ_UNKNOWN
    raw: str = ""
    evidence: str | None = None
    negated: bool = False
    conflict: bool = False

    @property
    def effective(self) -> str:
        return FREQ_UNKNOWN if self.conflict else self.canonical


@dataclass(frozen=True)
class Alternative:
    mentioned: bool = False
    usable: bool | None = None      # 提到 ≠ 可用：翻烂了/坏了 → False
    items: list[str] = field(default_factory=list)
    raw: str = ""
    evidence: str | None = None

    @property
    def blocks_purchase(self) -> bool:
        """存在"仍可用"的替代品时才可能在判决里走替代方案分支。"""
        return self.mentioned and self.usable is True


@dataclass(frozen=True)
class CaseFacts:
    """一次判决真正读到的事实（判决/评分/报告共用同一份）。"""

    product_name: str | None
    money: Money
    budget: float | None
    frequency: Frequency
    trigger: Polarized
    alternative: Alternative
    purpose: str | None = None
    conflicts: dict[str, Any] = field(default_factory=dict)

    @property
    def cost_ratio(self) -> float | None:
        amount, budget = self.money.effective_amount, self.budget
        if amount is None or not budget or budget <= 0:
            return None
        return amount / budget


def _as_float(value: Any) -> float | None:
    if isinstance(value, bool) or value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def build_facts(fields: dict[str, Any] | None) -> CaseFacts:
    """把原始字段一次性转换成类型化事实；所有下游只读这里。"""
    data = dict(fields or {})

    # ---- 金额 ----
    amount = _as_float(data.get("price"))
    basis = "unit" if data.get("price_is_unit") else "total"
    if data.get("price_basis") in {"unit", "total"}:
        basis = data["price_basis"]
    money = Money(amount=amount, basis=basis, unit=data.get("price_unit"),
                  quantity=_as_float(data.get("quantity")))
    # 一致性：声明是单价但价格不等于原话里的单价值 → 按总价处理（避免重复乘数量）
    if money.basis == "unit" and money.quantity and amount is not None:
        raw = data.get("_price_unit_value")
        if raw is not None and abs(amount - float(raw)) > 1e-6:
            money = Money(amount=amount, basis="total", unit=None, quantity=money.quantity)

    # ---- 频率 ----
    freq_raw = str(data.get("expected_usage_frequency") or "")
    canonical = data.get("frequency_canonical")
    canonical = canonical if isinstance(canonical, str) and canonical in FREQUENCY_VALUES else None
    if canonical == FREQ_UNKNOWN:
        # unknown 不是主张、只是"模型不知道"：让位给用户原话的文本归一，
        # 否则"一周三次"会被判成冲突并降级为"未说明"（真实事故，见 resolve_frequency 注释）。
        canonical = None
    text_value = normalize_frequency(freq_raw)
    negated, cue = negation_scope(freq_raw, VALUE_KEYWORDS["frequency"])
    conflict = bool(canonical and text_value != FREQ_UNKNOWN and canonical != text_value)
    if negated and (canonical == "daily" or text_value == "daily"):
        # "不是每天用"：否定作用域内的 daily 无效
        canonical, conflict = None, True
    frequency = Frequency(
        canonical=canonical or text_value,
        raw=freq_raw,
        evidence=data.get("frequency_evidence"),
        negated=negated,
        conflict=conflict,
    )

    # ---- 触发原因 ----
    trigger_raw = str(data.get("trigger_reason") or "")
    trig_canonical = data.get("trigger_canonical")
    trig_canonical = trig_canonical if isinstance(trig_canonical, str) and trig_canonical in TRIGGER_VALUES else None
    if trig_canonical == TRIGGER_UNKNOWN:
        trig_canonical = None
    trig_text = normalize_trigger(trigger_raw)
    trig_negated, trig_cue = negation_scope(trigger_raw, VALUE_KEYWORDS["trigger"])
    trig_conflict = bool(trig_canonical and trig_text != TRIGGER_UNKNOWN and trig_canonical != trig_text)
    trigger = Polarized(
        value=(FREQ_UNKNOWN if trig_conflict else (trig_canonical or trig_text)),
        negated=trig_negated,
        cue=trig_cue,
    )

    # ---- 替代品 ----
    alt_raw = data.get("owned_alternatives")
    normalized_alt = normalize_alternatives(alt_raw)
    usable = data.get("alternative_covers_need")
    usable = bool(usable) if isinstance(usable, bool) else None
    alt_negated, _ = negation_scope(str(alt_raw or ""), VALUE_KEYWORDS["alternative"])
    alternative = Alternative(
        mentioned=bool(normalized_alt.get("has")),
        usable=False if alt_negated else usable,
        items=list(normalized_alt.get("items") or []),
        raw=str(alt_raw or ""),
        evidence=data.get("alternative_evidence"),
    )

    conflicts = dict(data.get("_field_conflicts") or {})
    if frequency.conflict and "expected_usage_frequency" not in conflicts:
        conflicts["expected_usage_frequency"] = {"canonical": canonical, "text": freq_raw, "resolved": FREQ_UNKNOWN}
    if trig_conflict and "trigger_reason" not in conflicts:
        conflicts["trigger_reason"] = {"canonical": trig_canonical, "text": trigger_raw, "resolved": TRIGGER_UNKNOWN}

    return CaseFacts(
        product_name=data.get("product_name"),
        money=money,
        budget=_as_float(data.get("monthly_budget_left")),
        frequency=frequency,
        trigger=trigger,
        alternative=alternative,
        purpose=data.get("purpose"),
        conflicts=conflicts,
    )
