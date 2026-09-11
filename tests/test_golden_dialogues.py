# tests/test_golden_dialogues.py
"""黄金剧本集：把收集阶段与判决书的关键路径固化成可回归的验收剧本。

覆盖：一句话多字段 / 多轮推进 / 跳过 / 拒绝跳过核心字段 / 纠正 /
金额容错 / 判决边界（小额、替代品、冲动触发、无关证据、成本工具失败）/
文案口吻（无系统腔、一次只问一个）/ 报告可复算字段。

全部离线（本地规则 + 规则判决），不依赖真实 API Key。
"""

from __future__ import annotations

import pytest

from backend.app.agents.field_normalizer import normalize_alternatives
from backend.app.agents.input_parser import parse_input
from backend.app.agents.judge_agent import RULE_VERSION, _evaluate, run_judge_agent
from backend.app.schemas.decision import AgentStep, RagEvidence, ToolResult
from backend.app.services.llm_client import MockLLMClient

SYSTEM_TONE = ("为了进入", "购物法庭分析", "字段", "请补充", "已记录")


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    monkeypatch.setattr("backend.app.agents.input_parser.get_llm_client", lambda: MockLLMClient())


# ==================== 收集阶段剧本 ====================

def test_dialogue_1_one_sentence_three_fields():
    """剧本 1：一句话给全核心字段 → 承接三字段 + 只问一个可选问题 + 快捷选项。"""
    result = parse_input("想买个键盘，价格300元，本月预算还剩5000元", {})
    plan = result.reply_plan
    assert result.is_complete is True
    assert {"product_name", "price", "monthly_budget_left"} <= set(result.merged_fields)
    assert "商品是键盘" in plan["ack"] and "价格 300 元" in plan["ack"]
    assert plan["question"] and plan["question"].count("？") == 1
    assert plan["can_stop"] is True and plan["optional"] is True
    assert plan["chips"], "可选追问也应给快捷选项"
    assert not any(tone in plan["reply"] for tone in SYSTEM_TONE)


def test_dialogue_2_multi_turn_missing_fields_shrink():
    """剧本 2：多轮补充 → 缺失项单调减少，且不再追问已答字段。"""
    fields = {}
    seen = []
    for text in ["我想买芒果", "花4元买", "预算3000元", "想补充营养，没有其他水果", "差不多每天吃"]:
        result = parse_input(text, fields)
        fields = dict(result.merged_fields)
        seen.append((text, list(result.missing_fields), result.reply_plan.get("question")))
    counts = [len(m) for _, m, _ in seen]
    assert counts == sorted(counts, reverse=True), f"缺失项应单调减少：{counts}"
    assert counts[-1] < counts[0]
    for text, missing, question in seen:
        if question:
            assert question.count("？") == 1, f"{text} 的问题不止一个：{question}"
            assert not any(tone in question for tone in SYSTEM_TONE), question


def test_dialogue_3_skip_optional_field_is_not_asked_again():
    """剧本 3：对可选字段说“不知道” → 记为未说明且不再追问同一字段。"""
    fields = {"product_name": "键盘", "price": 300, "monthly_budget_left": 5000,
              "_current_question_key": "purpose"}
    result = parse_input("不知道", fields)
    assert result.merged_fields["purpose"] == "未说明"
    assert "purpose" not in result.missing_fields
    assert "跳过" in result.reply_plan["reply"]


def test_dialogue_4_core_field_cannot_be_skipped():
    """剧本 4：核心字段说“不知道” → 不放行，改用“给个范围”的追问。"""
    fields = {"product_name": "键盘", "_current_question_key": "price"}
    result = parse_input("不知道", fields)
    assert "price" not in result.merged_fields
    assert "price" in result.missing_fields
    assert "给个范围" in result.reply_plan["reply"]


def test_dialogue_5_correction_is_echoed():
    """剧本 5：纠正价格 → correction_fields 生效且回复明确“已改成”。"""
    fields = {"product_name": "键盘", "price": 300, "monthly_budget_left": 5000}
    result = parse_input("价格不是300，是500", fields)
    assert result.merged_fields["price"] == 500
    assert result.correction_fields.get("price") == 500
    assert "价格已改成 500 元" in result.reply_plan["reply"]


def test_dialogue_6_unit_price_does_not_kill_the_turn():
    """剧本 6：带单位金额（5元/斤）也要落成数值，且不整轮作废。"""
    result = parse_input("水果价格是5元一斤，我的预算是2000元", {})
    assert result.merged_fields.get("price") == 5
    assert result.merged_fields.get("monthly_budget_left") == 2000
    assert result.merged_fields.get("product_name") == "水果"


def test_dialogue_8_negated_frequency_is_not_high():
    """剧本 14：'不是每天用，只是偶尔' 不能被归一成 daily（真实验收抓出的 bug）。"""
    from backend.app.agents.field_normalizer import (
        FREQ_OCCASIONAL,
        FREQ_UNKNOWN,
        FREQ_WEEKLY_1_2,
        FREQ_WEEKLY_3PLUS,
        normalize_frequency,
    )

    assert normalize_frequency("偶尔使用，不是每天用") == FREQ_OCCASIONAL
    assert normalize_frequency("不是每天，一周两三次") != "daily"
    assert normalize_frequency("不算经常") == FREQ_UNKNOWN
    # 肯定表达不受影响
    assert normalize_frequency("每天使用") == "daily"
    # 动词插入与区间次数（20 案真实验收抓出的 bug）
    assert normalize_frequency("一周用两三次") == FREQ_WEEKLY_3PLUS
    assert normalize_frequency("每周去两三次") == FREQ_WEEKLY_3PLUS
    assert normalize_frequency("一周用一两次") == FREQ_WEEKLY_1_2


def test_dialogue_7_optional_questions_are_capped():
    """剧本 7：可选追问最多两轮，之后不再追问并给收尾结束语。"""
    fields = {"product_name": "键盘", "price": 300, "monthly_budget_left": 5000,
              "_optional_asked": 2, "_current_question_key": "purpose"}
    result = parse_input("键盘手感一般", fields)
    plan = result.reply_plan
    assert plan["question"] is None
    assert plan["can_stop"] is True
    assert plan["closing"] is True
    assert "判决书" in plan["reply"]


# ==================== 判决书剧本 ====================

def _cost(risk="low", status="success", ratio=None):
    metrics = {} if ratio is None else {"budget_ratio": ratio}
    return ToolResult("cost_analyzer", status, f"成本风险：{risk}",
                      risk if status == "success" else None, metrics,
                      None if status == "success" else "TOOL_ERROR")


def _score(value=70, status="success"):
    return ToolResult("decision_score", status, "综合评分", "low", {"score": value},
                      None if status == "success" else "TOOL_ERROR")


def _evidence(title, tags):
    return RagEvidence(id=f"h{abs(hash(title)) % 9999}", title=title,
                       content=f"{title} 的复盘", score=9.0, source="seed",
                       case_type="shopping", tags=tags, created_at=None)


def _fields(**kw):
    base = {"product_name": "键盘", "price": 300, "monthly_budget_left": 5000,
            "purpose": "写代码", "expected_usage_frequency": "每天", "trigger_reason": "刚需"}
    base.update(kw)
    return base


def test_verdict_1_low_cost_floor():
    """剧本 8：4 元小额低风险 → buy（H2）。"""
    decision, basis, _ = _evaluate(_fields(product_name="印章", price=4),
                                   [], _cost("low", ratio=0.001), _score(57))
    assert decision == "buy" and basis[-1]["rule"] == "H2"


def test_verdict_2_covering_alternative_is_alternative():
    """剧本 9：替代品明确覆盖核心需求 → alternative（R2，归一化后 has=False 不再误判）。"""
    decision, basis, _ = _evaluate(
        _fields(owned_alternatives="旧键盘", alternative_covers_need=True),
        [], _cost("low", ratio=0.3), _score(80))
    assert decision == "alternative" and basis[-1]["rule"] == "R2"
    # 反例：“没有手表”不能被当成有替代品
    assert normalize_alternatives("没有手表")["has"] is False


def test_verdict_3_impulse_triggers_delay():
    """剧本 10：促销/推荐/情绪触发 → delay（R1）。"""
    for trigger in ["促销", "朋友推荐", "种草", "情绪"]:
        decision, basis, _ = _evaluate(_fields(trigger_reason=trigger), [],
                                       _cost("low", ratio=0.3), _score(70))
        assert decision == "delay", trigger
        assert basis[-1]["rule"] == "R1"


def test_verdict_4_unrelated_risk_evidence_does_not_delay():
    """剧本 11：无关历史（围巾）带 regret 也不该把键盘案打成 delay。"""
    decision, basis, _ = _evaluate(_fields(), [_evidence("围巾 消费复盘", ["clothing", "regret"])],
                                   _cost("low", ratio=0.03), _score(86))
    assert decision == "buy"
    assert any(item["rule"] == "E0" for item in basis)


def test_verdict_5_related_risk_evidence_delays():
    # 占比 30% ≥ 10% 门槛：相关风险证据可单独判暂缓
    decision, basis, _ = _evaluate(_fields(price=600, monthly_budget_left=2000),
                                   [_evidence("键盘 消费复盘", ["idle"])],
                                   _cost("low", ratio=0.3), _score(70))
    assert decision == "delay" and basis[-1]["rule"] == "R1"
    # 占比 3% < 门槛：只作参考（E3），不改变结论
    decision2, basis2, _ = _evaluate(_fields(price=90, monthly_budget_left=3000),
                                     [_evidence("键盘 消费复盘", ["idle"])],
                                     _cost("low", ratio=0.03), _score(86))
    assert decision2 == "buy"
    assert any(item["rule"] == "E3" for item in basis2)


def test_verdict_6_cost_tool_failure_is_conservative():
    decision, _, _ = _evaluate(_fields(), [], _cost(status="failed"), _score(95))
    assert decision == "delay"


def test_verdict_7_unit_price_does_not_short_circuit():
    """剧本 13：单价（5元/斤）不能被当成 5 元总价走小额短路；带上数量才允许。"""
    unit_only = parse_input("水果价格是5元一斤，我的预算是2000元", {})
    assert unit_only.merged_fields.get("price_is_unit") is True
    assert unit_only.merged_fields.get("price_unit") == "斤"
    decision, basis, _ = _evaluate(dict(unit_only.merged_fields), [], _cost("low", ratio=0.002), _score(60))
    assert decision != "buy", "单价未知数量时不允许小额放行"
    assert any(item["rule"] == "E2" for item in basis)

    with_qty = parse_input("水果5元一斤，我要买10斤，预算还剩2000元", {})
    assert with_qty.merged_fields.get("quantity") == 10
    assert with_qty.merged_fields.get("price_is_unit") is True


def test_verdict_report_is_reproducible_and_clean():
    """剧本 12：报告带规则版本与输入快照；反方论点里不再混入工具摘要。"""
    pro = AgentStep("pro_agent", "completed", "支持购买", 0.7, ["用途明确"])
    con = AgentStep("con_agent", "completed", "谨慎", 0.7, ["预算占比需要关注"])
    _, report = run_judge_agent(
        case_id="case_golden",
        collected_fields=_fields(price=4),
        pro_step=pro,
        con_step=con,
        rag_evidence=[],
        tool_results=[_cost("low", ratio=0.001), _score(57)],
    )
    assert report.rule_version == RULE_VERSION
    # 占比用原始金额现算（4/5000），不受工具两位小数近似值影响
    assert abs(report.input_snapshot.get("成本占比") - 4 / 5000) < 1e-9
    assert report.input_snapshot.get("使用频率") == "daily"
    assert report.decision_basis and report.decision_strength
    assert not any("风险等级为" in point for point in report.con_points), "论点里不应出现工具 summary 原文"


def test_dialogue_9_canonical_value_beats_free_text():
    """剧本 16：模型直接给受控值时，判决/评分优先采用它，不再从中文里猜。"""
    from backend.app.agents.field_normalizer import canonical_frequency, canonical_trigger, resolve_frequency

    fields = {"expected_usage_frequency": "一周用两三次", "frequency_canonical": "weekly_3plus",
              "trigger_reason": "最近打折促销", "trigger_canonical": "promotion"}
    assert canonical_frequency(fields) == "weekly_3plus"
    assert canonical_trigger(fields) == "promotion"
    # 受控值非法时回落到文本归一
    assert canonical_frequency({"expected_usage_frequency": "每天", "frequency_canonical": "bogus"}) == "daily"
    # 受控值与文本冲突时降级为 unknown（不能拿模型的错误受控值覆盖正确文本）
    value, conflict = resolve_frequency({"expected_usage_frequency": "只是偶尔", "frequency_canonical": "daily"})
    assert value == "unknown" and conflict is True


def test_dialogue_10_total_price_is_not_treated_as_unit_price():
    """剧本 17：模型说“单价”但价格已是总价（2元一寸→54）时，不能再乘一次数量。"""
    result = parse_input("显示器2元一寸，我想买27寸的，预算还剩4000", {})
    fields = result.merged_fields
    if fields.get("price_is_unit"):
        assert abs(float(fields.get("price")) - 2.0) < 1e-6, "标记为单价时价格必须等于单价值"
    else:
        assert "price_unit" not in fields


def test_verdict_9_rounded_tool_ratio_does_not_trigger_floor():
    """剧本 15：成本工具把 1.35% 报成 0.01 时，不能因此触发 1% 小额短路。"""
    fields = _fields(price=128, monthly_budget_left=4000)
    decision, basis, _ = _evaluate(fields, [], _cost("low", ratio=0.03), _score(60))
    # 精确占比 54/4000 = 1.35% > 1%，H2 不应命中（走 R3/R5 的低风险放行）
    assert not any(item["rule"] == "H2" for item in basis), basis
    assert decision in {"buy", "delay"}
