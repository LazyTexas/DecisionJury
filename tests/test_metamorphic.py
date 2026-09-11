# tests/test_metamorphic.py
"""蜕变测试（metamorphic testing）：不依赖标注，验证"输入变换下关系不变"。

思想来自蜕变测试研究：与其为每个反例补一条字面规则，不如声明**不变量**，
再对输入做保持语义的变换，断言输出关系不变。这样能覆盖没见过的说法（长尾）。

同时包含性质断言（property），例如"任何受控值都必须有原文依据"。
"""

from __future__ import annotations

import pytest

from backend.app.agents.field_normalizer import (
    FREQ_DAILY,
    canonical_frequency,
    canonical_trigger,
    normalize_frequency,
    normalize_trigger,
)
from backend.app.agents.input_parser import _build_llm_result, _extract_price, _extract_product
from backend.app.services.llm_client import MockLLMClient


def _parser_payload(**overrides):
    payload = {
        "case_type": "shopping",
        "is_high_risk": False,
        "reject_reason": None,
        "extracted_fields": {},
        "correction_fields": {},
        "next_question": None,
        "confidence": 0.9,
    }
    payload.update(overrides)
    return payload


# ==================== 变换 1：同义替换 → 受控值必须相同 ====================

@pytest.mark.parametrize("variants", [
    ["每天", "每日", "天天", "每天使用", "日常使用"],
    ["一周五次", "每周五回", "每周去五次"],
    ["偶尔", "很少用", "低频"],
])
def test_synonym_substitution_keeps_canonical_value(variants):
    """同一语义的不同说法，归一结果必须一致（否则下游判决就会随措辞漂移）。"""
    values = {normalize_frequency(v) for v in variants}
    assert len(values) == 1, f"{variants} 归一不一致: {values}"


def test_trigger_synonym_substitution():
    groups = [
        (["促销", "打折", "降价", "优惠"], "promotion"),
        (["种草", "朋友推荐", "看到别人用"], "recommendation"),
        (["情绪", "冲动", "压力大"], "emotion"),
        (["刚需", "坏了", "旧的不能用"], "need"),
    ]
    for variants, expected in groups:
        for text in variants:
            assert normalize_trigger(text) == expected, text


# ==================== 变换 2：插入无关内容 → 结果必须不变 ====================

def test_inserting_irrelevant_clause_does_not_change_extraction():
    base = "想买个键盘，300元，预算还剩5000"
    noisy = "今天天气不错，我先说下，想买个键盘，300元，预算还剩5000，对了周末要下雨"
    assert _extract_price(base, None) == _extract_price(noisy, None)
    assert _extract_product(base) == _extract_product(noisy)
    assert normalize_frequency(base) == normalize_frequency(noisy)


# ==================== 变换 3：加否定 → 不得保持原判 ====================

def test_adding_negation_must_change_or_clear_value():
    """'每天用' → '不是每天用'：高频结论必须失效（这是曾经的真 bug）。"""
    assert normalize_frequency("每天用") == FREQ_DAILY
    assert normalize_frequency("不是每天用") != FREQ_DAILY
    assert normalize_frequency("并不是每天都用") != FREQ_DAILY


# ==================== 变换 4：换单位 → 单价语义必须保持 ====================

@pytest.mark.parametrize("text", [
    "水果5元一斤，预算还剩2000",
    "水果5元/斤，预算还剩2000",
    "水果5元每斤，预算还剩2000",
    "水果5元一公斤，预算还剩2000",
])
def test_unit_expression_variants_are_all_recognized(text):
    """单价的不同写法（一斤 / 每斤 / /斤 / 一公斤）都必须识别为单位语义。"""
    from backend.app.agents.input_parser import _PRICE_UNIT_PATTERN

    assert _PRICE_UNIT_PATTERN.search(text), f"未识别单位: {text}"


# ==================== 性质断言：无依据的值必须被丢弃 ====================

def test_value_without_valid_quote_is_dropped():
    """证据契约：片段不在原话里 → 该字段作废（宁可留空，不要编造）。"""
    payload = _parser_payload(
        extracted_fields={"product_name": "键盘", "price": 300},
        evidence={"product_name": "想买个键盘", "price": "其实是五百块"},
    )
    result = _build_llm_result(payload, {}, "想买个键盘，300元，预算还剩5000")
    assert result.merged_fields.get("product_name") == "键盘"
    assert "price" not in result.merged_fields, "证据不匹配的价格必须作废"
    assert result.merged_fields.get("_abstained", {}).get("price") == "其实是五百块"
    # 合法片段要有偏移，非法片段不进 spans
    spans = result.merged_fields.get("_evidence_spans") or {}
    assert spans.get("product_name", {}).get("text") == "想买个键盘"
    assert spans["product_name"]["start"] == 0
    assert spans["product_name"]["end"] == len("想买个键盘")
    assert "price" not in spans


def test_evidence_span_points_at_the_right_slice():
    """span 必须是"可回指的原文区间"：按 start/end 切片要能取回片段本身。"""
    text = "预算还剩 5000，想买个键盘，价格 300 元"
    payload = _parser_payload(
        extracted_fields={"product_name": "键盘", "price": 300},
        evidence={"product_name": "想买个键盘", "price": "300 元"},
    )
    result = _build_llm_result(payload, {}, text)
    spans = result.merged_fields["_evidence_spans"]
    for field_name in ("product_name", "price"):
        span = spans[field_name]
        assert text[span["start"]:span["end"]] == span["text"], field_name


def test_valid_quote_keeps_value():
    payload = _parser_payload(
        extracted_fields={"product_name": "键盘", "price": 300},
        evidence={"product_name": "想买个键盘", "price": "300元"},
    )
    result = _build_llm_result(payload, {}, "想买个键盘，300元，预算还剩5000")
    assert result.merged_fields.get("price") == 300
    assert "_abstained" not in result.merged_fields


# ==================== 性质断言：受控值冲突必须降级 ====================

def test_conflicting_canonical_and_text_resolves_to_unknown():
    fields = {"expected_usage_frequency": "只是偶尔", "frequency_canonical": "daily"}
    assert canonical_frequency(fields) == "unknown"
    conflict_free = {"expected_usage_frequency": "种草", "trigger_canonical": "recommendation"}
    assert canonical_trigger(conflict_free) == "recommendation"


# ==================== 离线兜底路径不崩 ====================

def test_offline_path_never_raises(monkeypatch):
    monkeypatch.setattr("backend.app.agents.input_parser.get_llm_client", lambda: MockLLMClient())
    from backend.app.agents.input_parser import parse_input

    for text in ["", "？", "5元/斤", "不是每天", "一二三", "买"]:
        result = parse_input(text, {})
        assert result.parser_used in {"local", "local_fallback", "deepseek"}
