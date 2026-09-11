# tests/test_semantic_facts.py
"""类型化语义表示（唯一事实层）的不变量测试。

对应研究结论：
- 富槽位/属性化状态：槽位值带属性，"提到旧物" ≠ "旧物可用"；
- 否定作用域（NegEx 式）：先判断否定线索与作用域，再取值；
- 数量-单位联合抽取：金额 = 数值 + 口径（单价/总价）+ 单位 + 数量。
"""

from __future__ import annotations

from backend.app.domain.semantic import build_facts, negation_scope


# ==================== 否定作用域 ====================

def test_negation_scope_detects_cue_before_keyword():
    assert negation_scope("不是每天用", ("每天",))[0] is True
    assert negation_scope("没有其他水果", ("有",))[0] is True
    assert negation_scope("每天都要用", ("每天",))[0] is False


def test_negated_frequency_does_not_survive():
    """'不是每天用' 即使模型给了 daily，也不得按 daily 使用。"""
    facts = build_facts({"expected_usage_frequency": "不是每天用，只是偶尔", "frequency_canonical": "daily"})
    assert facts.frequency.effective == "unknown"
    assert facts.frequency.conflict is True
    assert "expected_usage_frequency" in facts.conflicts


# ==================== 替代品：提到 ≠ 可用 ====================

def test_mentioned_but_unusable_alternative_does_not_block():
    """'旧的那套翻烂了' 是提到替代品，但它不能覆盖需求 → 不进入替代方案分支。"""
    facts = build_facts({"owned_alternatives": "旧的那套绘本", "alternative_covers_need": False})
    assert facts.alternative.mentioned is True
    assert facts.alternative.usable is False
    assert facts.alternative.blocks_purchase is False


def test_usable_alternative_blocks():
    facts = build_facts({"owned_alternatives": "旧键盘", "alternative_covers_need": True})
    assert facts.alternative.blocks_purchase is True


def test_negated_alternative_is_not_an_alternative():
    facts = build_facts({"owned_alternatives": "没有其他水果"})
    assert facts.alternative.mentioned is False
    assert facts.alternative.blocks_purchase is False


# ==================== 金额：口径 / 单位 / 数量 ====================

def test_unit_price_times_quantity():
    facts = build_facts({"price": 5, "price_is_unit": True, "price_unit": "斤",
                         "quantity": 3, "monthly_budget_left": 2000})
    assert facts.money.basis == "unit"
    assert facts.money.effective_amount == 15.0
    assert abs(facts.cost_ratio - 0.0075) < 1e-9
    assert facts.money.is_estimate is False


def test_unit_price_without_quantity_is_only_an_estimate():
    """单价但数量未知 → 只能估算，不允许据此走小额放行。"""
    facts = build_facts({"price": 5, "price_is_unit": True, "price_unit": "斤",
                         "monthly_budget_left": 2000})
    assert facts.money.is_estimate is True
    assert facts.cost_ratio == 0.0025


def test_total_price_is_not_multiplied_again():
    """模型说 unit 但价格已是总价（2元一寸×27寸=54）→ 按总价处理，不得再乘数量。"""
    facts = build_facts({"price": 54, "price_is_unit": True, "price_unit": "寸",
                         "quantity": 27, "_price_unit_value": 2, "monthly_budget_left": 4000})
    assert facts.money.basis == "total"
    assert facts.money.effective_amount == 54.0
    assert abs(facts.cost_ratio - 0.0135) < 1e-9


# ==================== 触发原因：冲突降级 ====================

def test_conflicting_trigger_degrades_to_unknown():
    facts = build_facts({"trigger_reason": "种草很久了", "trigger_canonical": "emotion"})
    assert facts.trigger.effective == "unknown"
    assert "trigger_reason" in facts.conflicts


def test_consistent_trigger_is_kept():
    facts = build_facts({"trigger_reason": "最近打折促销", "trigger_canonical": "promotion"})
    assert facts.trigger.effective == "promotion"
    assert facts.conflicts == {}


# ==================== unknown 受控值不是主张（真实事故回归） ====================
# 用户实测：原话"一周三次"（文本归一 weekly_3plus），模型给的 frequency_canonical="unknown"，
# 旧实现把 unknown 当成模型的主张 → 判冲突 → 降级"未说明" → 判决依据出现 E5、
# 结论从 alternative 翻成 reject（H1 非刚需）。unknown 只是"模型不知道"，应让位给文本归一。

def test_unknown_canonical_yields_to_text_frequency():
    facts = build_facts({"expected_usage_frequency": "一周三次", "frequency_canonical": "unknown"})
    assert facts.frequency.effective == "weekly_3plus"
    assert facts.frequency.conflict is False
    assert "expected_usage_frequency" not in facts.conflicts


def test_unknown_canonical_yields_to_text_trigger():
    facts = build_facts({"trigger_reason": "最近打折促销", "trigger_canonical": "unknown"})
    assert facts.trigger.effective == "promotion"
    assert facts.conflicts == {}


def test_real_canonical_conflict_still_degrades():
    """模型给了具体受控值且与文本矛盾时，仍按冲突降级（这条防护不能被削弱）。"""
    facts = build_facts({"expected_usage_frequency": "只是偶尔用", "frequency_canonical": "daily"})
    assert facts.frequency.effective == "unknown"
    assert facts.frequency.conflict is True
    assert "expected_usage_frequency" in facts.conflicts


def test_negated_daily_still_blocked_with_unknown_canonical():
    """否定作用域不受本次修改影响："不是每天用" 仍不得算 daily。"""
    facts = build_facts({"expected_usage_frequency": "不是每天用", "frequency_canonical": "unknown"})
    assert facts.frequency.effective != "daily"
