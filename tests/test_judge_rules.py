# tests/test_judge_rules.py
"""判决规则回归集 —— 覆盖本次修复的边界与“同义不同判”问题。

背景：旧 `_decide` 用精确字符串比较自由文本，导致
    "每天"→buy 但 "每天使用"→delay；
    "没有"→视为无替代品，但 "暂无"/"没有其他水果"→被当成有替代品，判 alternative；
    "促销"→delay 但 "朋友推荐"/"旧物损坏"→buy；
    4 元商品落兜底 delay；无关历史证据也能把结论打成 delay。
本文件把这些反例固定下来，避免再次退化。
"""

from __future__ import annotations

from backend.app.agents.field_normalizer import (
    FREQ_DAILY,
    FREQ_OCCASIONAL,
    FREQ_UNKNOWN,
    FREQ_WEEKLY_3PLUS,
    TRIGGER_EMOTION,
    TRIGGER_NEED,
    TRIGGER_PROMOTION,
    TRIGGER_RECOMMENDATION,
    normalize_alternatives,
    normalize_frequency,
    normalize_trigger,
)
from backend.app.agents.judge_agent import _decide, _evaluate, run_judge_agent
from backend.app.schemas.decision import AgentStep, RagEvidence, ToolResult


# ==================== 辅助构造 ====================

def _fields(**overrides):
    base = {
        "product_name": "商品",
        "price": 100,
        "monthly_budget_left": 3000,
        "purpose": "日常使用",
        "owned_alternatives": "",
        "expected_usage_frequency": "",
        "trigger_reason": "",
    }
    base.update(overrides)
    return base


def _cost(risk_level="low", status="success", ratio=None):
    metrics = {}
    if ratio is not None:
        metrics["budget_ratio"] = ratio
    return ToolResult(
        tool_name="cost_analyzer",
        status=status,
        summary=f"成本风险：{risk_level}",
        risk_level=risk_level if status == "success" else None,
        metrics=metrics,
        error=None if status == "success" else "TOOL_ERROR",
    )


def _score(score=86, status="success"):
    return ToolResult(
        tool_name="decision_score",
        status=status,
        summary="综合评分",
        risk_level="low",
        metrics={"score": score},
        error=None if status == "success" else "TOOL_ERROR",
    )


def _evidence(title, tags):
    return RagEvidence(
        id=f"h_{abs(hash(title)) % 10000}",
        title=title,
        content=f"{title} 的复盘内容",
        score=9.0,
        source="seed",
        case_type="shopping",
        tags=tags,
        created_at=None,
    )


# ==================== 归一化：同义写法必须一致 ====================

def test_frequency_synonyms_map_to_same_value():
    for text in ["每天", "每日", "天天", "每天使用", "日常使用", "基本上天天用", "一周七天"]:
        assert normalize_frequency(text) == FREQ_DAILY, text
    for text in ["经常", "高频", "一周五天", "每周四次"]:
        assert normalize_frequency(text) == FREQ_WEEKLY_3PLUS, text
    assert normalize_frequency("偶尔") == FREQ_OCCASIONAL
    assert normalize_frequency("") == FREQ_UNKNOWN
    assert normalize_frequency("看情况") == FREQ_UNKNOWN
    # 幂等：已是受控值时原样返回
    assert normalize_frequency(FREQ_DAILY) == FREQ_DAILY


def test_trigger_synonyms_map_to_same_value():
    assert normalize_trigger("促销") == TRIGGER_PROMOTION
    for text in ["种草", "朋友推荐", "社交影响", "看到别人用", "被博主种草"]:
        assert normalize_trigger(text) == TRIGGER_RECOMMENDATION, text
    for text in ["情绪", "冲动", "奖励自己"]:
        assert normalize_trigger(text) == TRIGGER_EMOTION, text
    for text in ["刚需", "旧物损坏", "坏了", "学习需要"]:
        assert normalize_trigger(text) == TRIGGER_NEED, text


def test_alternatives_negation_variants():
    for text in ["无", "没有", "暂无", "暂时没有", "没有其他水果", "无其他替代品", "没有类似的"]:
        result = normalize_alternatives(text)
        assert result["has"] is False, text
        assert result["known"] is True, text
    # 空值 = 未说明（不是“没有”）
    empty = normalize_alternatives("")
    assert empty["has"] is False and empty["known"] is False
    # 真实物品名不能被误判成否定（“无线路由器”以“无”开头）
    assert normalize_alternatives("无线路由器")["has"] is True
    assert normalize_alternatives("旧耳机")["has"] is True


# ==================== 判决边界 ====================

def test_low_cost_floor_short_circuits_to_buy():
    """4 元商品（占比≈0.13%）不再被判暂缓。"""
    decision, basis, strength = _evaluate(
        _fields(price=4, monthly_budget_left=3000, product_name="光敏印章"),
        [],
        _cost("low", ratio=0.0013),
        _score(52),
    )
    assert decision == "buy"
    assert basis[-1]["rule"] == "H2"
    assert strength >= 0.9


def test_watch_case_with_plain_alternative_is_buy():
    """截图 1/2 反例：占比 3%、评分 86、每天使用、只提到“已有手机” → buy（旧逻辑判 alternative）。"""
    decision, basis, _ = _evaluate(
        _fields(
            product_name="智能手表",
            price=1000,
            monthly_budget_left=29000,
            expected_usage_frequency="每天使用",
            owned_alternatives="手机",
            trigger_reason="日常使用",
        ),
        [_evidence("智能手表 消费复盘", ["electronics", "worth"])],
        _cost("low", ratio=0.03),
        _score(86),
    )
    assert decision == "buy"
    assert basis[-1]["rule"] == "R3"


def test_alternative_only_when_it_covers_core_need():
    """明确覆盖核心需求才判 alternative；仅提到已有物品时按 R4 提示比较。"""
    covering, basis, _ = _evaluate(
        _fields(owned_alternatives="旧耳机", alternative_covers_need=True),
        [],
        _cost("low", ratio=0.3),
    )
    assert covering == "alternative"
    assert basis[-1]["rule"] == "R2"

    mentioned, basis2, _ = _evaluate(
        _fields(owned_alternatives="旧耳机"),
        [],
        _cost("low", ratio=0.3),
    )
    assert mentioned == "alternative"
    assert basis2[-1]["rule"] == "R4"


def test_negated_alternative_no_longer_forces_alternative():
    """“暂无/没有其他水果”这类写法不再被当成有替代品。"""
    for text in ["暂无", "没有其他水果", "无其他替代品"]:
        decision, _, _ = _evaluate(
            _fields(owned_alternatives=text, expected_usage_frequency="每天"),
            [],
            _cost("low", ratio=0.3),
            _score(70),
        )
        assert decision == "buy", text


def test_impulse_triggers_include_recommendation():
    """朋友推荐/社交影响/旧物损坏 也按冲动触发处理（占比 20% ≥ 5% 门槛）。"""
    for text, expected in [
        ("促销", "delay"),
        ("种草", "delay"),
        ("朋友推荐", "delay"),
        ("社交影响", "delay"),
        ("情绪", "delay"),
        ("旧物损坏", "buy"),  # 归一到 need：不算冲动触发，按频率走
    ]:
        decision, _, _ = _evaluate(
            _fields(trigger_reason=text, expected_usage_frequency="每天", price=600, monthly_budget_left=3000),
            [],
            _cost("low", ratio=0.2),
            _score(70),
        )
        assert decision == expected, text


def test_small_impulse_purchase_is_only_a_reminder():
    """小额冲动消费（<5% 预算）只作提醒（E4），不强制冷静期。"""
    decision, basis, _ = _evaluate(
        _fields(trigger_reason="促销", expected_usage_frequency="每天", price=120, monthly_budget_left=3000),
        [],
        _cost("low", ratio=0.02),
        _score(86),
    )
    assert decision == "buy"
    assert any(item["rule"] == "E4" for item in basis)


def test_unrelated_risk_evidence_does_not_force_delay():
    """无关历史（围巾/投影仪）不再把智能手表案打成 delay。"""
    unrelated = _evidence("围巾 消费复盘", ["clothing", "regret"])
    decision, basis, _ = _evaluate(
        _fields(
            product_name="智能手表",
            price=1000,
            monthly_budget_left=29000,
            expected_usage_frequency="每天使用",
        ),
        [unrelated],
        _cost("low", ratio=0.03),
        _score(86),
    )
    assert decision == "buy"
    assert any(item["rule"] == "E0" for item in basis)


def test_related_risk_evidence_still_delays():
    # 占比 30% ≥ 10% 门槛：相关风险证据足以判暂缓
    related = _evidence("智能手表 消费复盘", ["electronics", "regret"])
    decision, basis, _ = _evaluate(
        _fields(product_name="智能手表", expected_usage_frequency="每天", price=600, monthly_budget_left=2000),
        [related],
        _cost("low", ratio=0.3),
        _score(70),
    )
    assert decision == "delay"
    assert basis[-1]["rule"] == "R1"


def test_related_risk_evidence_is_only_a_note_when_amount_small():
    # 占比 3% < 10%：历史教训只作为参考（E3），不单独否决购买
    related = _evidence("智能手表 消费复盘", ["electronics", "regret"])
    decision, basis, _ = _evaluate(
        _fields(product_name="智能手表", expected_usage_frequency="每天", price=90, monthly_budget_left=3000),
        [related],
        _cost("low", ratio=0.03),
        _score(86),
    )
    assert decision == "buy"
    assert any(item["rule"] == "E3" for item in basis)


# ==================== 替代品优先于"中等成本风险"（R2 先于 R1-medium） ====================
# 真实复验（换电饭煲 299/1200，用户说"旧的没坏，就是想换个新的"）：字段 covers_core_need=True、
# 成本风险 medium，旧实现先命中 R1(medium) 直接返回 delay，判定依据只写"预算压力需要先观察"，
# 而判决书正文却在讲"需求已被现有替代品覆盖"——同一份文书自相矛盾，且后续动作也偏
# （delay 让用户复盘真实需求，真相是旧物已经够用）。现在 R2 先判：不需要重复买强于先别买。

def test_covering_alternative_outranks_medium_cost_risk():
    decision, basis, _ = _evaluate(
        _fields(owned_alternatives="旧电饭煲", alternative_covers_need=True, price=299, monthly_budget_left=1200),
        [],
        _cost("medium", ratio=0.25),
        _score(40),
    )
    assert decision == "alternative"
    assert basis[-1]["rule"] == "R2"


def test_covering_alternative_outranks_impulse_trigger():
    """冲动触发 + 替代品可覆盖 → alternative（"根本不需要买"强于"冲动了先冷静"）。"""
    decision, basis, _ = _evaluate(
        _fields(owned_alternatives="旧耳机", alternative_covers_need=True, trigger_reason="促销"),
        [],
        _cost("low", ratio=0.2),
        _score(60),
    )
    assert decision == "alternative"
    assert basis[-1]["rule"] == "R2"


def test_covering_alternative_outranks_related_risk_evidence():
    """相关风险证据 + 替代品可覆盖 → alternative（同理：冗余结论不被历史教训改写成暂缓）。"""
    related = _evidence("智能手表 消费复盘", ["electronics", "regret"])
    decision, basis, _ = _evaluate(
        _fields(owned_alternatives="旧手表", alternative_covers_need=True,
                expected_usage_frequency="每天", price=600, monthly_budget_left=2000),
        [related],
        _cost("low", ratio=0.3),
        _score(70),
    )
    assert decision == "alternative"
    assert basis[-1]["rule"] == "R2"


def test_high_risk_path_still_wins_over_covering_alternative():
    """高风险档不受新优先级影响（这是刻意的边界，不是顺带）。

    超预算 → reject（H1）；高额刚需 + 替代品可覆盖 → 仍走 E6 的 fall-through（R3 放行或 R6 冷静），
    不因为一个模型判断的 covers_core_need 就改判 alternative。
    """
    over_budget, basis1, _ = _evaluate(
        _fields(owned_alternatives="旧相机", alternative_covers_need=True, price=6000, monthly_budget_left=3000),
        [],
        _cost("high", ratio=2.0),
        _score(30),
    )
    assert over_budget == "reject"
    assert basis1[-1]["rule"] == "H1"

    necessary, basis2, _ = _evaluate(
        _fields(owned_alternatives="旧手机", alternative_covers_need=True, price=4300,
                monthly_budget_left=5000, expected_usage_frequency="每天"),
        [],
        _cost("high", ratio=0.86),
        _score(46),
    )
    assert necessary != "alternative"
    assert any(item["rule"] == "E6" for item in basis2)
    assert basis2[-1]["rule"] in {"R3", "R6"}


def test_unknown_frequency_low_cost_buy():
    decision, basis, _ = _evaluate(
        _fields(expected_usage_frequency="", price=300, monthly_budget_left=3000),
        [],
        _cost("low", ratio=0.0167),
        _score(66),
    )
    assert decision == "buy"
    assert basis[-1]["rule"] == "R5"


def test_cost_tool_failure_is_conservative():
    """成本工具失败时不放行，走保守口径。"""
    decision, _, _ = _evaluate(
        _fields(price=4, expected_usage_frequency="每天"),
        [],
        _cost(status="failed"),
        _score(90),
    )
    assert decision == "delay"


def test_high_risk_and_medium_risk_unchanged():
    assert _evaluate(_fields(), [], _cost("high"), _score(90))[0] == "reject"
    assert _evaluate(_fields(), [], _cost("medium", ratio=0.43), _score(30))[0] == "delay"


def test_basis_and_strength_present_in_report():
    step, report = run_judge_agent(
        case_id="case_basis",
        collected_fields=_fields(price=1000, monthly_budget_left=29000,
                                expected_usage_frequency="每天使用", product_name="智能手表"),
        pro_step=AgentStep(agent="pro_agent", status="completed", summary="支持", confidence=0.7, arguments=["a"]),
        con_step=AgentStep(agent="con_agent", status="completed", summary="反对", confidence=0.7, arguments=["b"]),
        rag_evidence=[],
        tool_results=[_cost("low", ratio=0.03), _score(86)],
    )
    assert report.final_decision in {"buy", "delay", "reject", "alternative"}
    assert report.decision_basis, "报告应带判决依据"
    assert 0.0 < (report.decision_strength or 0) <= 1.0
    assert any("R3" in arg or "H2" in arg for arg in step.arguments)


# ==================== 评分工具输入同样归一化 ====================

def test_score_adapter_uses_normalized_fields(monkeypatch):
    """'每天使用' 必须按高频传给 decision_score（旧实现只认精确的 '每天'）。"""
    from backend.app.services import mcp_adapter

    captured: dict = {}

    def fake_call_tool(name, arguments):
        captured["name"] = name
        captured["arguments"] = arguments
        return {"tool_name": name, "status": "success", "summary": "ok",
                "risk_level": "low", "metrics": {"score": 80}, "error": None}

    monkeypatch.setattr("backend.app.services.mcp_adapter.call_tool", fake_call_tool)
    mcp_adapter.score_decision(
        case_id="case_001",
        case_type="shopping",
        fields={"product_name": "智能手表", "purpose": "日常使用",
                "expected_usage_frequency": "每天使用", "trigger_reason": "朋友推荐"},
        rag_evidence=[],
        cost_result=_cost("low", ratio=0.03),
    )
    assert captured["arguments"]["usage_value"] == 0.9
    assert captured["arguments"]["impulse_trigger"] is True


def test_unconfirmed_alternative_still_waits_for_budget_pressure():
    """刻意的不对称：**确认**能覆盖的替代品（R2）优先于中等成本风险；
    **只提到、能否替代未知**（R4）不优先——预算压力中等时仍先判 delay，
    由后续动作"比较已有替代品或低价替代方案"承担提醒职责。
    """
    decision, basis, _ = _evaluate(
        _fields(owned_alternatives="旧耳机", price=299, monthly_budget_left=1200),
        [],
        _cost("medium", ratio=0.25),
        _score(50),
    )
    assert decision == "delay"
    assert basis[-1]["rule"] == "R1"


# ==================== 用户实测案：unknown 受控值不该抹掉明确的文本频率 ====================
# 原始输入：筋膜枪 200 元 / 预算 200 / 已有泡沫轴（覆盖核心需求）/ 原话"一周三次"，
# 但模型给的 frequency_canonical="unknown"。旧实现判冲突→按"未说明"→非刚需→H1 reject；
# 修复后按文本归一 weekly_3plus→刚需→走 E6 后由替代品规则给出 alternative。

def test_user_case_weekly_three_times_is_not_downgraded():
    fields = _fields(product_name="筋膜枪", price=200, monthly_budget_left=200,
                     purpose="家里和健身房都用", owned_alternatives="泡沫轴",
                     alternative_covers_need=True, trigger_reason="最近就买",
                     expected_usage_frequency="一周三次",
                     frequency_canonical="unknown", trigger_canonical="unknown")
    decision, basis, _ = _evaluate(fields, [], _cost("high", ratio=1.0), _score(40))
    assert decision == "alternative"
    rules = [item["rule"] for item in basis]
    assert "E6" in rules                    # 高额但刚需：按冷静期口径说明，而不是"非刚需直接拒"
    assert rules[-1] == "R4"                # 替代品承接结论（高风险档不走 R2 优先）
    assert "可以覆盖核心需求" in basis[-1]["detail"]
    assert not any(item["rule"] == "E5" for item in basis), "明确的文本频率不该再被判成冲突"
