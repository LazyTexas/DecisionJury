# tests/test_quality_gate.py
"""质量门禁（离线可跑，供 CI 使用）。

把"判决书能不能给人看"这件事变成可断言的指标，而不是靠人肉 review：
1. 用户可见文案里不得出现内部字段名/工具名（工程腔）；
2. 案件摘要不得出现模板回填腔（"未说明用途"）与浮点显示（"499.0 元"）；
3. 离线黄金剧本的关键不变量（受控值归一、否定、替代品、金额口径）必须成立。

真实 API 的准确率/降级率由 scripts/dialogue_quality_eval.py 度量（需要 Key，不进 CI）。
"""

from __future__ import annotations

import pytest

from backend.app.agents.judge_agent import _build_case_summary
from backend.app.agents.user_facing import has_internal_terms, sanitize_arguments, sanitize_user_text

# ==================== 指标 1：用户可见文案零工程腔 ====================

DIRTY_SAMPLES = [
    "触发原因是旧鞋开胶，属于装备失效后的替换性需求，且 alternative_covers_need 为 false。",
    "decision_score 总分81、风险low，但其 cost 维度得分为0。",
    "两项 MCP 工具（cost_analyzer、decision_score）均返回成功，无失败项。",
    "price_basis 显示为 total_price，quantity 为 null。",
]


def test_user_facing_text_has_no_internal_terms():
    for sample in DIRTY_SAMPLES:
        cleaned = sanitize_user_text(sample)
        assert not has_internal_terms(cleaned), cleaned
        assert "cost_analyzer" not in cleaned and "MCP" not in cleaned


def test_internal_only_sentences_are_dropped():
    text = "旧鞋开胶属于刚需。field_meta 中 _abstained 记了 price。"
    cleaned = sanitize_user_text(text)
    assert "field_meta" not in cleaned and "_abstained" not in cleaned
    assert "刚需" in cleaned


def test_arguments_sanitizer_keeps_meaning():
    args = sanitize_arguments(["成本占比不低：499元占剩余月预算约25%。", "decision_score 给81分。"])
    assert len(args) == 2
    assert all(not has_internal_terms(item) for item in args)
    assert "决策评分" in args[1]


# 真实 API 复验里模型写出的"工程腔残留"（原文照抄，用于回归门禁）
ENGINEERING_ECHO_SAMPLES = [
    ("两项工具（成本分析、决策评分）均返回success，无失败项。", ("success",), "返回成功"),
    ("RAG证据为空，决策评分中历史维度得分为0.0。", ("RAG",), "历史证据"),
    ("（已有物品能否满足需求 为 false）", ("false",), "为否"),
    ("决策评分 的 usage_value 维度为 0.0、history 维度为 0.0。", ("usage_value", "history"), "使用价值"),
    ("成本分析 提示本次支出占剩余预算约 86%、风险等级为 高。", (" 提示",), "提示"),
]


@pytest.mark.parametrize("sample,forbidden,expected", ENGINEERING_ECHO_SAMPLES)
def test_engineering_vocabulary_is_translated(sample: str, forbidden: tuple, expected: str):
    """英文状态词/评分维度名/RAG 缩写不得留在用户可见文案里（语义要保留）。"""
    cleaned = sanitize_user_text(sample, force=True)
    for word in forbidden:
        assert word not in cleaned, f"{word!r} 仍在文案里：{cleaned}"
    assert expected in cleaned, cleaned


# ==================== 指标 2：案件摘要自然化 ====================

def test_case_summary_is_natural_and_integral():
    summary = _build_case_summary(
        {"price": 499, "monthly_budget_left": 2000, "expected_usage_frequency": "每周跑三四次",
         "trigger_reason": "旧鞋开胶了"},
        "跑步鞋", 499.0,
    )
    assert "499.0" not in summary, summary
    assert "未说明" not in summary, summary
    assert "499" in summary and "跑步鞋" in summary
    assert "每周三次以上" in summary          # 受控值渲染成中文
    assert "确实需要" in summary              # 触发原因渲染成中文


def test_case_summary_omits_unknown_instead_of_filling_placeholders():
    summary = _build_case_summary({"price": 88, "monthly_budget_left": 1000}, "儿童绘本", 88.0)
    assert "未说明" not in summary
    assert summary.endswith("。")
    assert "绘本" in summary


# ==================== 指标 3：关键不变量（离线黄金剧本） ====================

def test_core_invariants_hold():
    from backend.app.agents.field_normalizer import (
        FREQ_WEEKLY_3PLUS,
        normalize_alternatives,
        normalize_frequency,
        normalize_trigger,
    )
    from backend.app.domain.semantic import build_facts

    # 频率与触发
    assert normalize_frequency("一周用两三次") == FREQ_WEEKLY_3PLUS
    assert normalize_frequency("不是每天用，只是偶尔") != "daily"
    assert normalize_trigger("种草很久了") == "recommendation"
    assert normalize_trigger("旧的不能用") == "need"
    # 替代品
    assert normalize_alternatives("没有手表")["has"] is False
    assert build_facts({"owned_alternatives": "旧的那套绘本", "alternative_covers_need": False}).alternative.blocks_purchase is False
    # 金额口径
    facts = build_facts({"price": 5, "price_is_unit": True, "quantity": 3, "monthly_budget_left": 2000})
    assert facts.money.effective_amount == 15.0


# ==================== 指标 4：案件摘要的金额口径不能张冠李戴 ====================
# 真实复验发现（第 4 轮，读完整判决书时抓到）：摘要把价格写成"预算"、把"单价×数量"的合计写成"单价"。
#   原文示例：手机支架 9.9 元 → "预算约 9.9 元，本月还剩 800 元可用"（预算另有其值）
#             洗衣液 45 元/桶 × 2 → "单价约 90 元"（单价是 45，90 是合计）
# 这类错误出现在判决书第一句，用户最容易读到，且不会被"判决结果对不对"的检查发现。

def test_case_summary_labels_total_price_as_price_not_budget():
    summary = _build_case_summary(
        {"price": 9.9, "monthly_budget_left": 800, "price_is_unit": False}, "手机支架", 9.9
    )
    assert "价格约 9.9 元" in summary
    assert "预算约" not in summary          # 预算是 800，不能被写成 9.9
    assert "本月还剩 800 元可用" in summary


def test_case_summary_unit_price_shows_unit_quantity_and_total():
    summary = _build_case_summary(
        {"price": 45, "monthly_budget_left": 600, "price_is_unit": True,
         "price_unit": "桶", "quantity": 2}, "洗衣液", 45
    )
    assert "单价约 45 元/桶" in summary
    assert "共 2 桶" in summary
    assert "合计约 90 元" in summary
    assert "单价约 90" not in summary       # 90 是合计，不是单价


def test_case_summary_unit_price_without_quantity_is_marked_pending():
    summary = _build_case_summary(
        {"price": 5, "monthly_budget_left": 1200, "price_is_unit": True, "price_unit": "斤"},
        "水果", 5,
    )
    assert "单价约 5 元/斤" in summary
    assert "数量未确认" in summary          # 不能把单价当总价，也不能假装知道总量
    assert "预算约" not in summary


def test_internal_ids_are_stripped_from_prose():
    """真实复验：法官说明里出现"已成功创建 3 天冷静期提醒（r_18b73537）"。"""
    cleaned = sanitize_user_text("已成功创建 3 天冷静期提醒（r_18b73537），到期可复盘。", force=True)
    assert "r_18b73537" not in cleaned
    assert cleaned.startswith("已成功创建 3 天冷静期提醒")
    # 整体就是该 id 的取值（结构化字段）不受影响
    assert sanitize_user_text("r_18b73537") == "r_18b73537"
