# tests/test_input_parser.py
"""Input Parser 单元测试 —— 纯逻辑，无外部依赖"""

from backend.app.agents import input_parser
from backend.app.agents.input_parser import parse_input
from backend.app.services.llm_client import DeepSeekLLMClient


# ========== 高风险检测 ==========

def test_high_risk_medical():
    """含"吃药"时标记高风险，但不再因该标记直接拒绝。"""
    result = parse_input("我想吃药治疗一下")
    assert result.is_high_risk is True
    assert result.reject_reason == "high_risk_domain"
    assert result.case_status == "collecting"
    assert result.is_supported is True


def test_high_risk_financial():
    """含"股票"→ is_high_risk=True。"""
    result = parse_input("想买股票")
    assert result.is_high_risk is True


def test_high_risk_relationship():
    """含"分手"→ is_high_risk=True。"""
    result = parse_input("想分手复合")
    assert result.is_high_risk is True


def test_not_high_risk():
    """正常购物输入 → is_high_risk=False。"""
    result = parse_input("想买个 299 元的耳机用于学习")
    assert result.is_high_risk is False
    assert result.is_supported is True
    assert result.case_type == "shopping"


# ========== 字段提取 ==========

def test_extract_price():
    """"想买 299 元的耳机" → price=299.0。"""
    result = parse_input("想买 299 元的耳机")
    assert result.extracted_fields.get("price") == 299.0


def test_extract_explicit_price_statement():
    """明确价格补充消息应提取 price，供 /messages 多轮纠正和补充使用。"""
    for message, expected in (
        ("价格是2500元。", 2500.0),
        ("商品价约为三千元", 3000.0),
        ("售价大约是 1299 元", 1299.0),
    ):
        result = parse_input(message)
        assert result.extracted_fields.get("price") == expected


def test_extract_budget():
    """"预算还剩 1000 元" → monthly_budget_left=1000.0。"""
    result = parse_input("预算还剩 1000 元")
    assert result.extracted_fields.get("monthly_budget_left") == 1000.0


def test_extract_product():
    """"买一个耳机" → product_name 非空。"""
    result = parse_input("买一个耳机 299 元")
    assert result.extracted_fields.get("product_name") is not None


def test_extract_purpose():
    """"为了学习" → purpose 非空。"""
    result = parse_input("想买个降噪耳机，为了学习")
    assert result.extracted_fields.get("purpose") is not None


def test_extract_alternatives():
    """"已有旧耳机" → owned_alternatives 非空。"""
    result = parse_input("已有旧耳机")
    assert result.extracted_fields.get("owned_alternatives") is not None


def test_extract_frequency():
    """"每天都会用" → expected_usage_frequency="每天"。"""
    result = parse_input("每天都会用")
    assert result.extracted_fields.get("expected_usage_frequency") == "每天"


def test_extract_trigger():
    """含"促销"→ trigger_reason="促销"。"""
    result = parse_input("促销时看到的耳机")
    assert result.extracted_fields.get("trigger_reason") == "促销"


def test_extract_complete_chinese_shopping_description():
    """中文完整购物描述应尽量一次提取出演示链路所需核心字段。"""
    result = parse_input("我想买一副1299元的降噪耳机，最近学习需要安静，预计每天使用，这次是刚需。")

    assert result.extracted_fields.get("price") == 1299.0
    assert result.extracted_fields.get("product_name") == "降噪耳机"
    assert result.extracted_fields.get("purpose") == "学习需要安静"
    assert result.extracted_fields.get("expected_usage_frequency") == "每天"
    assert result.extracted_fields.get("trigger_reason") == "刚需"


def test_product_name_keeps_taideng_after_price():
    """“一个399元的台灯”里的“台”是商品名组成部分，不能被误当量词裁掉。"""
    result = parse_input("我想买一个399元的台灯")

    assert result.extracted_fields.get("price") == 399.0
    assert result.extracted_fields.get("product_name") == "台灯"


def test_product_name_keeps_taideng_without_price():
    """“一盏台灯”属于明确量词边界，应该去掉“一盏”，但保留完整商品名“台灯”。"""
    result = parse_input("我想买一盏台灯")

    assert result.extracted_fields.get("product_name") == "台灯"


def test_product_name_keeps_normal_classifier_behavior():
    """正常量词场景仍应继续工作，避免修复“台灯”时把“一台显示器”这类案例带坏。"""
    result = parse_input("我想买一台显示器")

    assert result.extracted_fields.get("product_name") == "显示器"


def test_product_name_keeps_taishiji():
    """“台式机”本身是名词，不应因为首字是“台”就被裁成“式机”。"""
    result = parse_input("我想买一台台式机")

    assert result.extracted_fields.get("product_name") == "台式机"
    assert "price" not in result.extracted_fields


def test_extract_chinese_budget_and_alternative_message():
    """中文补充消息应提取预算和已有替代品，且预算不能误写到 price。"""
    result = parse_input("本月预算还剩3000元，已有普通耳机。")

    assert result.extracted_fields.get("monthly_budget_left") == 3000.0
    assert result.extracted_fields.get("owned_alternatives") == "普通耳机"
    assert "price" not in result.extracted_fields


def test_budget_message_does_not_become_price():
    """预算语义必须优先于通用金额兜底，避免 3000 元预算被当成商品价格。"""
    result = parse_input("预算还剩 3000 元")

    assert result.extracted_fields.get("monthly_budget_left") == 3000.0
    assert result.extracted_fields.get("price") is None


def test_extract_chinese_number_budget():
    """本地 fallback 应能识别常见中文数字预算。"""
    result = parse_input("预算大概还有三千左右")

    assert result.extracted_fields.get("monthly_budget_left") == 3000.0
    assert "price" not in result.extracted_fields


def test_negative_frequency_uses_later_frequency():
    """否定“每天”后出现更具体的“一周两次”时，不能返回被否定的频率。"""
    result = parse_input("我不是每天用，大概一周两次")

    assert result.extracted_fields.get("expected_usage_frequency") == "一周两次"


# ========== 缺失字段与状态判断 ==========

def test_missing_fields_detection():
    """缺字段时 missing_fields 非空，case_status="collecting"。"""
    result = parse_input("想买个耳机")
    assert len(result.missing_fields) > 0
    assert result.case_status == "collecting"


def test_all_fields_present_ready():
    """全部字段齐全 → case_status="ready_for_debate"。"""
    existing = {
        "product_name": "耳机",
        "price": 299,
        "purpose": "学习",
        "monthly_budget_left": 1000,
        "owned_alternatives": "无",
        "expected_usage_frequency": "每天",
        "trigger_reason": "刚需",
    }
    result = parse_input("想买个耳机", existing_collected_fields=existing)
    assert result.case_status == "ready_for_debate"
    assert result.missing_fields == []


# ========== 合并逻辑 ==========

def test_merge_with_existing_fields():
    """existing_collected_fields 与新提取字段合并，新值覆盖旧值。"""
    existing = {"monthly_budget_left": 500, "purpose": "学习"}
    result = parse_input("预算还剩 800 元", existing_collected_fields=existing)
    assert result.merged_fields["monthly_budget_left"] == 800.0
    assert result.merged_fields["purpose"] == "学习"


def test_local_parser_explicit_price_correction():
    """本地 fallback 应支持明确的金额纠正。"""
    result = parse_input(
        "不是1299，是999",
        existing_collected_fields={"price": 1299, "product_name": "耳机"},
    )

    assert result.merged_fields["price"] == 999.0


def test_local_parser_common_price_corrections():
    existing = {"price": 1299, "product_name": "耳机"}

    corrected_statement = parse_input("刚才说错了，价格是999", existing_collected_fields=existing)
    changed_statement = parse_input("价格改成999", existing_collected_fields=existing)

    assert corrected_statement.merged_fields["price"] == 999.0
    assert changed_statement.merged_fields["price"] == 999.0


def test_local_parser_budget_correction_does_not_set_price():
    result = parse_input(
        "预算不是3000，是2500",
        existing_collected_fields={"monthly_budget_left": 3000, "product_name": "耳机"},
    )

    assert result.merged_fields["monthly_budget_left"] == 2500.0
    assert "price" not in result.extracted_fields


def test_chinese_message_merge_and_missing_fields():
    """中文创建案件与补充消息组合后，应只剩真正未补齐的字段。"""
    existing = {
        "price": 1299.0,
        "product_name": "降噪耳机",
        "purpose": "学习需要安静",
        "expected_usage_frequency": "每天",
        "trigger_reason": "刚需",
    }
    result = parse_input("本月预算还剩3000元，已有普通耳机。", existing_collected_fields=existing)

    assert result.merged_fields["monthly_budget_left"] == 3000.0
    assert result.merged_fields["owned_alternatives"] == "普通耳机"
    assert result.missing_fields == []
    assert result.case_status == "ready_for_debate"


# ========== next_question ==========

def test_build_next_question():
    """缺失字段时 next_question 不为空。"""
    result = parse_input("想买个耳机")
    assert result.next_question is not None
    assert "还需要补充" in result.next_question


def test_no_next_question_when_ready():
    """字段齐全时 next_question 为 None。"""
    existing = {
        "product_name": "耳机",
        "price": 299,
        "purpose": "学习",
        "monthly_budget_left": 1000,
        "owned_alternatives": "无",
        "expected_usage_frequency": "每天",
        "trigger_reason": "刚需",
    }
    result = parse_input("想买个耳机", existing_collected_fields=existing)
    assert result.next_question is None


# ========== agent_step ==========

def test_parser_result_agent_step():
    """agent_step.agent="input_parser"。"""
    result = parse_input("想买个耳机")
    assert result.agent_step.agent == "input_parser"
    assert result.agent_step.status == "completed"


def test_shopping_fields_use_llm_when_configured(monkeypatch):
    """配置 DeepSeek 后，正常购物字段统一走模型解析。"""
    called = False
    client = DeepSeekLLMClient(api_key="test-key")

    def parse_with_llm(payload):
        nonlocal called
        called = True
        return {
            "case_type": "shopping",
            "is_supported": True,
            "is_high_risk": False,
            "reject_reason": None,
            "extracted_fields": {"price": 2500},
            "correction_fields": {},
            "next_question": "还需要补充商品名称和用途。",
            "confidence": 0.9,
        }

    monkeypatch.setattr(client, "complete_parser_json", parse_with_llm)
    monkeypatch.setattr(input_parser, "get_llm_client", lambda: client)

    result = parse_input("价格是2500元")

    assert called is True
    assert result.extracted_fields["price"] == 2500.0


def test_ambiguous_input_uses_llm_parser(monkeypatch):
    """口语化购物输入应交给 DeepSeek 解析。"""
    called = False
    client = DeepSeekLLMClient(api_key="test-key")

    def parse_with_llm(payload):
        nonlocal called
        called = True
        return {
            "case_type": "shopping",
            "is_supported": True,
            "is_high_risk": False,
            "reject_reason": None,
            "extracted_fields": {"purpose": "备考时需要安静"},
            "correction_fields": {},
            "next_question": "还需要补充商品、价格和预算。",
            "confidence": 0.86,
        }

    monkeypatch.setattr(client, "complete_parser_json", parse_with_llm)
    monkeypatch.setattr(input_parser, "get_llm_client", lambda: client)

    result = parse_input("最近备考特别吵，想弄个能安静点的东西")

    assert called is True
    assert result.merged_fields["purpose"] == "备考时需要安静"


def test_llm_parser_result_is_used(monkeypatch):
    client = DeepSeekLLMClient(api_key="test-key")
    monkeypatch.setattr(
        client,
        "complete_parser_json",
        lambda payload: {
            "case_type": "shopping",
            "is_high_risk": False,
            "reject_reason": None,
            "extracted_fields": {
                "product_name": "降噪耳机",
                "price": 999,
                "purpose": "备考",
                "monthly_budget_left": 3000,
                "owned_alternatives": "普通耳机",
                "expected_usage_frequency": "每天",
                "trigger_reason": "刚需",
            },
            "correction_fields": {},
            "next_question": None,
            "confidence": 0.92,
        },
    )
    monkeypatch.setattr(input_parser, "get_llm_client", lambda: client)

    result = parse_input("最近备考特别吵，想弄个能安静点的耳机")

    assert result.merged_fields["price"] == 999.0
    assert result.case_status == "ready_for_debate"
    assert result.agent_step.confidence == 0.92


def test_llm_parser_explicit_correction_updates_merged_fields(monkeypatch):
    client = DeepSeekLLMClient(api_key="test-key")
    monkeypatch.setattr(
        client,
        "complete_parser_json",
        lambda payload: {
            "case_type": "shopping",
            "is_high_risk": False,
            "reject_reason": None,
            "extracted_fields": {},
            "correction_fields": {"price": 999},
            "next_question": "还想了解一下预计使用频率。",
            "confidence": 0.88,
        },
    )
    monkeypatch.setattr(input_parser, "get_llm_client", lambda: client)

    result = parse_input(
        "刚才说错了，不是1299，是999",
        existing_collected_fields={"price": 1299, "product_name": "耳机"},
    )

    assert result.extracted_fields == {}
    assert result.merged_fields["price"] == 999.0
    assert result.next_question == "还想了解一下预计使用频率。"


def test_llm_parser_failure_falls_back_to_local_rules(monkeypatch):
    client = DeepSeekLLMClient(api_key="test-key")

    def raise_error(payload):
        raise TimeoutError("parser timeout")

    monkeypatch.setattr(client, "complete_parser_json", raise_error)
    monkeypatch.setattr(input_parser, "get_llm_client", lambda: client)

    result = parse_input("我想买一个399元的台灯")

    assert result.extracted_fields["price"] == 399.0
    assert result.extracted_fields["product_name"] == "台灯"
