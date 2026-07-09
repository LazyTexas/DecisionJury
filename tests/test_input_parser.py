# tests/test_input_parser.py
"""Input Parser 单元测试 —— 纯逻辑，无外部依赖"""

from backend.app.agents.input_parser import parse_input


# ========== 高风险检测 ==========

def test_high_risk_medical():
    """含"吃药"→ is_high_risk=True, reject_reason="high_risk_domain"。"""
    result = parse_input("我想吃药治疗一下")
    assert result.is_high_risk is True
    assert result.reject_reason == "high_risk_domain"
    assert result.case_status == "rejected"


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
