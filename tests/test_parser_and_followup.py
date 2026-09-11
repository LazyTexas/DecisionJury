# tests/test_parser_and_followup.py
"""解析与追问修复的回归集。

覆盖三类反馈：
  1. “预算 3000 元，芒果 4 元” 这类句式在本地规则下也要抽出商品名与价格；
  2. 核心信息已齐但增强字段缺失时，`next_question` 不能再是 None/空串；
  3. 模型返回带单位金额（`"5元/斤"`）时按字段降级，而不是整轮解析作废（静默降级到本地正则）。
"""

from __future__ import annotations

import pytest

from backend.app.agents.input_parser import _build_rule_result, parse_input
from backend.app.services.llm_client import MockLLMClient, _validate_parser_result


def _mock_client(monkeypatch):
    """强制本地规则路径，避免测试依赖真实 API Key。"""
    monkeypatch.setattr(
        "backend.app.agents.input_parser.get_llm_client", lambda: MockLLMClient()
    )


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


# ==================== 1. 本地规则的字段抽取 ====================

def test_budget_and_price_in_one_sentence():
    """"预算 3000 元，芒果 4 元" -> 商品名、价格、预算都要抽到。"""
    result = _build_rule_result("预算 3000 元，芒果 4 元", {})
    assert result.merged_fields.get("monthly_budget_left") == 3000
    assert result.merged_fields.get("price") == 4
    assert result.merged_fields.get("product_name") == "芒果"
    assert "product_name" not in result.missing_fields
    assert "price" not in result.missing_fields


def test_verb_after_amount_is_recognized():
    """"花4元买芒果" 这种动词在金额之后的写法也要抽出价格与商品名。"""
    result = _build_rule_result("花4元买芒果", {})
    assert result.merged_fields.get("price") == 4
    assert result.merged_fields.get("product_name") == "芒果"


def test_budget_only_message_does_not_invent_price():
    """只有预算时不能把预算金额当成商品价格。"""
    result = _build_rule_result("本月预算还剩3000元，已有普通耳机", {})
    assert result.merged_fields.get("monthly_budget_left") == 3000
    assert "price" not in result.merged_fields
    assert result.merged_fields.get("owned_alternatives") == "普通耳机"


def test_price_kept_and_budget_not_overwritten():
    result = _build_rule_result("预算不是3000，是2500", {"price": 2200, "monthly_budget_left": 3000})
    assert result.merged_fields.get("monthly_budget_left") == 2500
    assert result.merged_fields.get("price") == 2200


# ==================== 2. 追问文案 ====================

def test_next_question_when_core_complete(monkeypatch):
    """核心三字段齐全、增强字段缺失时，仍返回具体的可选追问。"""
    _mock_client(monkeypatch)
    result = parse_input("预算 3000 元，芒果 4 元", {})
    assert result.is_complete is True
    assert result.case_status == "ready_for_debate"
    assert result.missing_fields, "增强字段应仍在缺失列表中"
    assert result.next_question, "核心信息齐了也不能返回空追问"
    assert result.next_question.startswith("想更准的话")
    assert "？" in result.next_question
    assert result.next_question_key in result.missing_fields


def test_next_question_still_blocking_when_core_missing(monkeypatch):
    """核心字段缺失时，追问仍是阻塞式（不带“想更准的话”前缀）。"""
    _mock_client(monkeypatch)
    result = parse_input("我想买一副耳机", {})
    assert result.is_complete is False
    assert result.next_question == "这个大概多少钱？"
    assert "为了进入购物法庭分析" not in result.next_question


def test_no_question_when_everything_collected(monkeypatch):
    """七个字段都齐时不再追问。"""
    _mock_client(monkeypatch)
    existing = {
        "product_name": "芒果",
        "price": 4,
        "purpose": "补充营养",
        "monthly_budget_left": 3000,
        "owned_alternatives": "没有",
        "expected_usage_frequency": "每周两次",
        "trigger_reason": "刚需",
    }
    result = parse_input("就这些", existing)
    assert result.missing_fields == []
    assert result.next_question is None


# ==================== 3. 模型返回值的金额容错 ====================

def test_unit_price_string_is_coerced():
    """“5元/斤” 不能再让整轮解析作废。"""
    payload = _parser_payload(
        extracted_fields={"product_name": "水果", "price": "5元/斤", "monthly_budget_left": 2000},
    )
    out = _validate_parser_result(payload)
    assert out["extracted_fields"]["price"] == 5
    assert out["extracted_fields"]["product_name"] == "水果"
    assert out["field_meta"]["price"]["raw_text"] == "5元/斤"


def test_approximate_and_symbol_amounts_are_coerced():
    payload = _parser_payload(
        extracted_fields={"price": "约1000元", "monthly_budget_left": "¥1,299"},
    )
    out = _validate_parser_result(payload)
    assert out["extracted_fields"]["price"] == 1000
    assert out["extracted_fields"]["monthly_budget_left"] == 1299


def test_chinese_numeral_amount_is_coerced():
    out = _validate_parser_result(_parser_payload(extracted_fields={"price": "一千二"}))
    assert out["extracted_fields"]["price"] == 1200


def test_unparsable_amount_drops_only_that_field():
    """抽不到数字时只丢该字段，保留同一轮的其他合法字段（字段级降级）。"""
    out = _validate_parser_result(
        _parser_payload(extracted_fields={"product_name": "水果", "price": "面议", "monthly_budget_left": 2000})
    )
    assert "price" not in out["extracted_fields"]
    assert out["extracted_fields"]["product_name"] == "水果"
    assert out["extracted_fields"]["monthly_budget_left"] == 2000


def test_boolean_amount_is_dropped_not_raised():
    out = _validate_parser_result(_parser_payload(extracted_fields={"price": True}))
    assert "price" not in out["extracted_fields"]


def test_contract_violations_are_tolerated_field_level():
    """未知字段/未知顶层键只做字段级降级，不再让整轮解析作废（否则用户信息会被整体丢弃）。"""
    out = _validate_parser_result(
        _parser_payload(extracted_fields={"unknown_field": 1, "product_name": "键盘"}, unexpected_key=1)
    )
    assert out["extracted_fields"]["product_name"] == "键盘"
    assert "unknown_field" not in out["extracted_fields"]
    assert out["field_meta"]["unknown_field"]["dropped"] == "unknown_field"


def test_missing_required_key_still_raises():
    payload = _parser_payload()
    payload.pop("confidence")
    with pytest.raises(ValueError):
        _validate_parser_result(payload)


# ==================== 判决阶段重放历史文本：不得覆盖累计状态 ====================

_CAT_LITTER_TEXT = "猫砂，一袋25，想买4袋，预算还剩900"


def _corrected_fields() -> dict:
    """用户后续纠正后的累计字段（"不是4袋，是2袋"）。"""
    return {
        "product_name": "猫砂",
        "price": 25.0,
        "price_is_unit": True,
        "price_unit": "袋",
        "quantity": 2,
        "monthly_budget_left": 900.0,
    }


def test_debate_replay_keeps_corrected_quantity(monkeypatch):
    """真实事故回归：判决阶段重放案件首条描述时，旧文本里的"4袋"不得盖掉纠正后的"2袋"。

    否则判决书按 4×25=100 元（占预算 11%）计算，而实际应为 2×25=50 元（5.6%）。
    """
    _mock_client(monkeypatch)

    replay = parse_input(_CAT_LITTER_TEXT, _corrected_fields(), existing_is_authoritative=True)
    assert replay.merged_fields["quantity"] == 2
    assert replay.merged_fields["price"] == 25.0
    assert replay.merged_fields["price_is_unit"] is True

    # 缺口仍可补齐：已有字段缺失时，历史文本里的信息照常填进来
    partial = {"product_name": "猫砂", "monthly_budget_left": 900.0}
    filled = parse_input(_CAT_LITTER_TEXT, partial, existing_is_authoritative=True)
    assert filled.merged_fields["quantity"] == 4
    assert filled.merged_fields["monthly_budget_left"] == 900.0


def test_latest_turn_still_can_correct_previous_value(monkeypatch):
    """普通对话轮的语义不变：最新一轮发言可以覆盖历史值（纠正是用户显式指令）。"""
    _mock_client(monkeypatch)
    result = parse_input("不是4袋，是2袋", {**_corrected_fields(), "quantity": 4})
    assert result.merged_fields["quantity"] == 2



def test_resolve_frequency_ignores_unknown_canonical():
    """resolve_* 与 facts 层语义必须一致：unknown 受控值让位给文本归一。"""
    from backend.app.agents.field_normalizer import resolve_frequency, resolve_trigger

    assert resolve_frequency({"frequency_canonical": "unknown",
                              "expected_usage_frequency": "一周三次"}) == ("weekly_3plus", False)
    assert resolve_trigger({"trigger_canonical": "unknown",
                            "trigger_reason": "最近打折促销"}) == ("promotion", False)
    # 具体受控值与文本矛盾时仍判冲突
    assert resolve_frequency({"frequency_canonical": "daily",
                              "expected_usage_frequency": "只是偶尔用"}) == ("unknown", True)
