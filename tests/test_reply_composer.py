# tests/test_reply_composer.py
"""收集阶段对话体验的回归集：承接句、一次一问、快捷选项、跳过、可选追问熔断。"""

from __future__ import annotations

from backend.app.agents.input_parser import parse_input
from backend.app.agents.reply_composer import (
    SKIPPED_VALUE,
    build_ack,
    build_reply_plan,
    is_skip_signal,
    question_chips,
)
from backend.app.services.llm_client import MockLLMClient


def _offline(monkeypatch):
    """强制本地规则路径（无 Key 时模型不可用），保证测试确定。"""
    monkeypatch.setattr(
        "backend.app.agents.input_parser.get_llm_client", lambda: MockLLMClient()
    )


COMPLETE_FIELDS = {
    "product_name": "键盘",
    "price": 30,
    "monthly_budget_left": 5000,
}


# ==================== 承接句 ====================

def test_ack_echoes_new_fields():
    ack = build_ack({"price": 30, "monthly_budget_left": 5000}, {})
    assert "价格 30 元" in ack and "预算还剩 5000 元" in ack
    assert ack.startswith("记下了")


def test_ack_empty_when_nothing_new():
    assert build_ack({}, {"price": 30}) == ""


def test_ack_says_no_alternative():
    ack = build_ack({"owned_alternatives": "没有"}, {})
    assert "没有替代品" in ack


def test_ack_marks_skipped_field():
    """用户说“不知道”时，承接句不能写成“没有替代品”。"""
    ack = build_ack({"owned_alternatives": SKIPPED_VALUE}, {})
    assert "先跳过" in ack
    assert "没有替代品" not in ack


# ==================== 回复计划 ====================

def test_blocking_question_is_conversational():
    plan = build_reply_plan(
        this_turn_fields={}, merged_fields={}, missing_fields=["price"],
        is_complete=False, next_question_key="price",
        next_question="这个大概多少钱？", conflicts=[],
    )
    assert plan["question"] == "这个大概多少钱？"
    assert "为了进入购物法庭分析" not in plan["reply"]
    assert plan["can_stop"] is False
    assert plan["optional"] is False


def test_optional_question_is_marked_optional_and_stoppable():
    plan = build_reply_plan(
        this_turn_fields={"purpose": "工作用"},
        merged_fields={**COMPLETE_FIELDS, "purpose": "工作用"},
        missing_fields=["owned_alternatives", "expected_usage_frequency", "trigger_reason"],
        is_complete=True, next_question_key="owned_alternatives",
        next_question="想更准的话，再补一句：你手上已经有能替代它的东西吗？",
        conflicts=[],
    )
    assert plan["can_stop"] is True and plan["optional"] is True
    assert "记下了：用途：工作用" in plan["reply"]
    assert plan["chips"], "可选问题也应给快捷选项"


def test_optional_questions_stop_after_two_rounds():
    plan = build_reply_plan(
        this_turn_fields={}, merged_fields=COMPLETE_FIELDS, missing_fields=["owned_alternatives"],
        is_complete=True, next_question_key="owned_alternatives",
        next_question="想更准的话，再补一句：你手上已经有能替代它的东西吗？",
        conflicts=[], optional_asked=2,
    )
    assert plan["question"] is None and plan["optional"] is False
    assert plan["can_stop"] is True
    # 熔断后不再追问 → 收尾给结束语（而不是把对话停在系统提问上）
    assert plan["closing"] is True
    assert "判决书" in plan["reply"]


def test_conflict_question_replaces_normal_question():
    plan = build_reply_plan(
        this_turn_fields={}, merged_fields={}, missing_fields=["price", "monthly_budget_left"],
        is_complete=False, next_question_key="price_or_budget", next_question="这个大概多少钱？",
        conflicts=[{"type": "amount_ambiguity"}],
    )
    assert "哪个是商品价格" in plan["question"]
    assert plan["chips"] == []


def test_chips_per_field():
    assert question_chips("expected_usage_frequency") == ["每天", "每周几次", "偶尔"]
    assert question_chips(None) == []


# ==================== 跳过 ====================

def test_skip_signal_detection():
    for text in ["不知道", "不太确定", "跳过", "你看着办"]:
        assert is_skip_signal(text), text
    assert not is_skip_signal("每天")


def test_skipping_enhanced_field_marks_and_moves_on(monkeypatch):
    _offline(monkeypatch)
    existing = {**COMPLETE_FIELDS, "_current_question_key": "purpose"}
    result = parse_input("不知道", existing)
    assert result.merged_fields["purpose"] == SKIPPED_VALUE
    assert "purpose" not in result.missing_fields, "跳过之后不应再重复追问同一字段"
    assert "跳过" in result.reply_plan["reply"]
    assert result.reply_plan["question"], "应继续问下一个可选字段"


def test_skipping_core_field_is_rejected(monkeypatch):
    _offline(monkeypatch)
    existing = {"product_name": "键盘", "_current_question_key": "price"}
    result = parse_input("不知道", existing)
    assert "price" not in result.merged_fields, "核心字段不能被跳过值占用"
    assert "price" in result.missing_fields
    assert "给个范围" in result.reply_plan["reply"]


# ==================== 与解析链路的整合 ====================

def test_first_turn_ack_and_single_question(monkeypatch):
    _offline(monkeypatch)
    result = parse_input("键盘30元，预算5000元", {})
    plan = result.reply_plan
    assert plan["ack"] and "价格 30 元" in plan["ack"]
    assert plan["question"] and plan["reply"].count("？") == 1, "一次只问一个问题"
    assert plan["can_stop"] is True


def test_collecting_turn_has_no_stop_flag(monkeypatch):
    _offline(monkeypatch)
    result = parse_input("我想买一副耳机", {})
    assert result.reply_plan["can_stop"] is False
    assert result.reply_plan["question"]


# ==================== 复读防护：口语衔接词不应绕过比较 ====================

def test_repeat_guard_ignores_leading_discourse_filler():
    """真实复现（猫粮案）：模型在下一轮给同一句话加了"那"，逐字符比较判不出复读。"""
    from backend.app.agents.reply_composer import _normalize_for_compare

    first = "这次是想给自家猫囤着吃，还是喂流浪猫呀？"
    second = "那这次是想给自家猫囤着吃，还是喂流浪猫呀？"
    assert _normalize_for_compare(first) == _normalize_for_compare(second)
    # 内容真的不同时不能被误判成复读
    assert _normalize_for_compare(first) != _normalize_for_compare("那这袋猫粮大概能吃多久呢？")


# ==================== 追问闸门与按目标字段判重（用户实测第 2 轮修复） ====================

def _plan(**overrides):
    from backend.app.agents.reply_composer import build_reply_plan

    kwargs = dict(
        this_turn_fields={},
        merged_fields={"product_name": "筋膜枪", "price": 200, "monthly_budget_left": 200},
        missing_fields=["purpose", "owned_alternatives"],
        is_complete=True,
        next_question_key="owned_alternatives",
        next_question="想更准的话，再补一句：你手上已经有能替代它的东西吗？",
        last_question="你打算什么时候入手？",
    )
    kwargs.update(overrides)
    return build_reply_plan(**kwargs)


def test_asked_optional_field_is_not_asked_again():
    """按目标字段判重：同一可选字段问过一次就换下一个，不再换说法重复问。"""
    plan = _plan(asked_fields=["owned_alternatives"])
    assert plan["ask_field"] == "purpose"
    assert "已有能替代它的东西" not in (plan["question"] or "")


def test_all_optional_fields_asked_stops_asking():
    plan = _plan(asked_fields=["owned_alternatives", "purpose"])
    assert plan["question"] is None
    assert plan["can_stop"] is True


def test_core_field_dedupe_does_not_stall_collection():
    """核心字段不受判重限制：没问到就没法出判决书，必须继续问。"""
    plan = _plan(missing_fields=["price"], is_complete=False,
                 next_question_key="price", next_question="这个东西多少钱？",
                 asked_fields=["price"])
    assert plan["question"] == "这个东西多少钱？"


def test_model_question_accepted_when_target_declared_and_allowed():
    plan = _plan(missing_fields=["purpose"], next_question_key="purpose",
                 next_question="主要拿来做什么用？（可选）", asked_fields=[],
                 dialogue={"ack": "收到", "question": "你主要拿它放松哪儿呀？",
                           "ask_field": "purpose", "intent": "provide_info"})
    assert plan["question"] == "你主要拿它放松哪儿呀？"
    assert plan["question_source"] == "model"
    assert plan["ask_field"] == "purpose"


def test_off_target_model_question_falls_back_to_local():
    """模型问了字段表以外的维度（如"几天内到手"）→ 丢弃，回落本地问句。"""
    plan = _plan(missing_fields=["purpose"], next_question_key="purpose",
                 next_question="主要拿来做什么用？（可选）", asked_fields=[],
                 dialogue={"ack": "收到", "question": "你希望几天内到手？",
                           "ask_field": "delivery_days", "intent": "provide_info"})
    assert plan["question"] == "主要拿来做什么用？（可选）"
    assert plan["question_source"] == "local"
    assert (plan["off_target_question"] or "").startswith("ask_field_not_allowed")


def test_undeclared_model_question_accepted_only_when_single_candidate():
    """放宽（用户要求 2）：没声明 ask_field 时，只剩唯一可问字段才采纳模型问法。"""
    single = _plan(missing_fields=["expected_usage_frequency"],
                   next_question_key="expected_usage_frequency",
                   next_question="想更准的话，再补一句：你大概多久用一次？", asked_fields=[],
                   dialogue={"ack": "收到", "question": "这东西你多久用一回呀？", "intent": "provide_info"})
    assert single["question"] == "这东西你多久用一回呀？"
    assert single["ask_field"] == "expected_usage_frequency"

    multiple = _plan(missing_fields=["expected_usage_frequency", "trigger_reason"],
                     next_question_key="expected_usage_frequency",
                     next_question="想更准的话，再补一句：你大概多久用一次？", asked_fields=[],
                     dialogue={"ack": "收到", "question": "这东西你多久用一回呀？", "intent": "provide_info"})
    assert multiple["question"] == "想更准的话，再补一句：你大概多久用一次？"
    assert multiple["question_source"] == "local"


def test_no_question_when_nothing_is_missing():
    """信息已齐且没有可问字段 → 不接受模型自创问题，回复变成收尾邀请。"""
    plan = _plan(missing_fields=[], next_question_key=None, next_question=None, asked_fields=[],
                 dialogue={"ack": "收到", "question": "你更看重轻便还是力度？",
                           "ask_field": "purpose", "intent": "provide_info"})
    assert plan["question"] is None
    assert plan["can_stop"] is True


# ==================== 欢迎语与结束语（用户要求：先欢迎再收集 / 收尾给结束语） ====================

def test_welcome_only_on_first_turn_and_names_the_product():
    from backend.app.agents.reply_composer import build_welcome

    first = _plan(include_welcome=True)
    assert first["welcome"]
    assert "筋膜枪" in first["welcome"]
    assert "判决书" in first["welcome"]

    later = _plan(include_welcome=False)
    assert later["welcome"] == ""
    # 欢迎语是给产品名的自然句，没有产品名时也不能出现空括号
    assert "「」" not in build_welcome(None)


def test_closing_message_appears_once_when_collection_stops():
    from backend.app.agents.reply_composer import CLOSING_MESSAGE

    stopping = _plan(missing_fields=[], next_question_key=None, next_question=None)
    assert stopping["question"] is None
    assert stopping["closing"] is True
    assert CLOSING_MESSAGE in stopping["reply"]

    # 已经给过结束语 → 不再重复刷
    already = _plan(missing_fields=[], next_question_key=None, next_question=None, closing_sent=True)
    assert already["closing"] is False
    assert CLOSING_MESSAGE not in already["reply"]


def test_closing_not_emitted_while_still_asking():
    from backend.app.agents.reply_composer import CLOSING_MESSAGE

    asking = _plan(missing_fields=["purpose"], next_question_key="purpose",
                   next_question="主要拿来做什么用？（可选）")
    assert asking["question"] == "主要拿来做什么用？（可选）"
    assert asking["closing"] is False
    assert CLOSING_MESSAGE not in asking["reply"]


def test_model_text_path_keeps_closing_message():
    """模型写了承接语时，收尾结束语也不能被吞掉（真实缺陷：只在 parts 为空时才补）。"""
    from backend.app.agents.reply_composer import CLOSING_MESSAGE

    plan = _plan(missing_fields=[], next_question_key=None, next_question=None,
                 dialogue={"ack": "明白，两头用得上", "insight": "便携比力度更值得看",
                           "intent": "provide_info"})
    assert plan["question"] is None
    assert "明白，两头用得上" in plan["reply"]
    assert CLOSING_MESSAGE in plan["reply"]


def test_enhanced_field_not_asked_twice_even_before_complete():
    """增强字段永远判重（信息没齐也一样）：问过 purpose 就换核心字段，不再重复问它。"""
    plan = _plan(missing_fields=["product_name", "purpose"], is_complete=False,
                 next_question_key="purpose", next_question="主要拿来做什么用？",
                 asked_fields=["purpose"])
    assert plan["ask_field"] == "product_name"
    assert plan["question"] == "你想买的是什么？"


def test_core_field_still_reasks_before_complete():
    """核心字段例外保留：信息没齐时核心字段必须继续问（否则收集会卡死）。"""
    plan = _plan(missing_fields=["price"], is_complete=False,
                 next_question_key="price", next_question="这个大概多少钱？",
                 asked_fields=["price"])
    assert plan["question"] == "这个大概多少钱？"
    assert plan["ask_field"] == "price"


def test_repeat_guard_switches_target_along_with_text():
    """复读防护换文案时必须同时换目标字段——否则又造出"显示问预算、记账记价格"的双来源。"""
    plan = _plan(missing_fields=["price", "monthly_budget_left"], is_complete=False,
                 next_question_key="price", next_question="这个大概多少钱？",
                 last_question="这个大概多少钱？", asked_fields=[])
    assert plan["question"] != "这个大概多少钱？"
    assert plan["question"] == "本月还剩多少可支配预算？"
    assert plan["ask_field"] == "monthly_budget_left"    # 目标跟着文案一起换
