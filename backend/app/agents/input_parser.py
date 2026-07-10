from __future__ import annotations

import re
from typing import Any

from backend.app.schemas.decision import AgentStep, ParserResult


REQUIRED_SHOPPING_FIELDS = [
    "product_name",
    "price",
    "purpose",
    "monthly_budget_left",
    "owned_alternatives",
    "expected_usage_frequency",
    "trigger_reason",
]

HIGH_RISK_KEYWORDS = [
    "吃药",
    "药",
    "手术",
    "治疗",
    "起诉",
    "合同",
    "律师",
    "股票",
    "基金",
    "币",
    "投资",
    "理财",
    "借钱",
    "贷款",
    "网贷",
    "分期贷",
    "辞职",
    "离职",
    "分手",
    "复合",
    "结婚",
    "离婚",
    "转学",
    "移民",
    "买房",
]

BUY_INTENT_KEYWORDS = [
    "想买",
    "买",
    "购买",
    "入手",
    "下单",
    "换",
    "办",
    "考虑买",
    "准备买",
]

BUDGET_CONTEXT_KEYWORDS = [
    "预算",
    "生活费",
    "可支配",
    "本月",
    "这个月",
    "还剩",
    "剩余",
    "余额",
]


def parse_input(
    raw_input: str,
    existing_collected_fields: dict[str, Any] | None = None,
) -> ParserResult:
    existing = existing_collected_fields or {}
    normalized_input = _normalize_text(raw_input)

    if _is_high_risk(normalized_input):
        step = AgentStep(
            agent="input_parser",
            status="completed",
            summary="输入命中高风险领域，已拒绝进入购物法庭辩论。",
            confidence=0.95,
            arguments=["当前项目仅支持购物和时间类低风险日常决策。"],
            used_rag_ids=[],
            used_tool_names=[],
            error=None,
        )
        return ParserResult(
            case_type=None,
            is_supported=False,
            is_high_risk=True,
            reject_reason="high_risk_domain",
            extracted_fields={},
            merged_fields={},
            missing_fields=[],
            next_question=None,
            case_status="rejected",
            agent_step=step,
        )

    extracted = _extract_shopping_fields(normalized_input)
    merged = {**existing, **{key: value for key, value in extracted.items() if value not in (None, "")}}
    missing_fields = [field for field in REQUIRED_SHOPPING_FIELDS if _is_missing(merged.get(field))]
    status = "ready_for_debate" if not missing_fields else "collecting"
    next_question = _build_next_question(missing_fields)

    step = AgentStep(
        agent="input_parser",
        status="completed",
        summary=f"识别为 shopping，缺失字段：{', '.join(missing_fields) if missing_fields else '无'}。",
        confidence=0.9 if extracted or existing else 0.65,
        arguments=[f"已收集字段：{', '.join(sorted(merged.keys())) or '无'}"],
        used_rag_ids=[],
        used_tool_names=[],
        error=None,
    )
    return ParserResult(
        case_type="shopping",
        is_supported=True,
        is_high_risk=False,
        reject_reason=None,
        extracted_fields=extracted,
        merged_fields=merged,
        missing_fields=missing_fields,
        next_question=next_question,
        case_status=status,
        agent_step=step,
    )


def _is_high_risk(text: str) -> bool:
    return any(keyword in text for keyword in HIGH_RISK_KEYWORDS)


def _extract_shopping_fields(text: str) -> dict[str, Any]:
    fields: dict[str, Any] = {}

    # 预算和价格都表现为“数字 + 元”，但业务语义完全不同。
    # 这里必须先识别预算语义，再决定某个金额能不能当作商品价格，
    # 否则“本月预算还剩3000元”这类补充消息会被错误写进 price。
    budget_match = _extract_budget_match(text)
    budget = budget_match[0] if budget_match else None
    if budget is not None:
        fields["monthly_budget_left"] = budget

    price = _extract_price(text, budget_match[1] if budget_match else None)
    if price is not None:
        fields["price"] = price

    product = _extract_product(text)
    if product:
        fields["product_name"] = product

    purpose = _extract_purpose(text)
    if purpose:
        fields["purpose"] = purpose

    alternatives = _extract_alternatives(text)
    if alternatives:
        fields["owned_alternatives"] = alternatives

    frequency = _extract_frequency(text)
    if frequency:
        fields["expected_usage_frequency"] = frequency

    trigger = _extract_trigger(text)
    if trigger:
        fields["trigger_reason"] = trigger

    return fields


def _normalize_text(text: str) -> str:
    # 这里只做最轻量的文本归一化：统一空白和货币符号，避免中文输入里
    # 因为全角字符、额外空格或换行导致正则边界失效。我们不做激进清洗，
    # 是为了保留“最近学习需要安静”“已有普通耳机”这类句子原本的语义线索。
    normalized = text.replace("\u3000", " ")
    normalized = normalized.replace("￥", "元")
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def _extract_budget_match(text: str) -> tuple[float, tuple[int, int]] | None:
    patterns = [
        r"(?:本月|这个月)?(?:预算|生活费|可支配预算|可支配金额|剩余预算)[^\d]{0,8}(?:还剩|剩余|还有|有)?\s*(\d+(?:\.\d+)?)\s*(?:元|块)?",
        r"(?:本月|这个月)?(?:还剩|剩余|还有)\s*(\d+(?:\.\d+)?)\s*(?:元|块)?[^\n，。；;]{0,8}(?:预算|生活费|可支配)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return float(match.group(1)), match.span(1)
    return None


def _extract_price(text: str, budget_span: tuple[int, int] | None) -> float | None:
    patterns = [
        r"(?:想买|买|购买|入手|下单|换|办|考虑买|准备买)[^\d]{0,6}(\d+(?:\.\d+)?)\s*(?:元|块|rmb|RMB)?",
        r"(\d+(?:\.\d+)?)\s*(?:元|块|rmb|RMB)\s*的",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            number_span = match.span(1)
            if budget_span and number_span == budget_span:
                continue
            if _is_budget_context(text, number_span):
                continue
            return float(match.group(1))
    return None


def _is_budget_context(text: str, span: tuple[int, int]) -> bool:
    context_start = max(0, span[0] - 8)
    context_end = min(len(text), span[1] + 8)
    context = text[context_start:context_end]
    return any(keyword in context for keyword in BUDGET_CONTEXT_KEYWORDS)


def _extract_product(text: str) -> str | None:
    patterns = [
        r"(?:想买|买|购买|入手|下单|换|办|考虑买|准备买)(?:[一1]?(?:个|件|副|台|盏|份|部|张|只|套))?\s*(?:(?:\d+(?:\.\d+)?)\s*(?:元|块|rmb|RMB)\s*的?)?\s*([^\s，。；;]+)",
        r"\d+(?:\.\d+)?\s*(?:元|块|rmb|RMB)\s*的([^\s，。；;]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            product = _clean_product_name(match.group(match.lastindex or 1))
            if product:
                return product[:20]
    return None


def _extract_purpose(text: str) -> str | None:
    patterns = [
        r"(?:为了|用于|用来)([^，。；;\n]{2,30})",
        r"最近([^，。；;\n]{2,20}?需要[^，。；;\n]{0,12})",
        r"([^，。；;\n]{1,16}?需要[^，。；;\n]{1,12})",
        r"(学习|通勤|运动|降噪|提升效率|安静|备考)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return _clean_phrase(match.group(1), strip_quantity=False)
    return None


def _extract_alternatives(text: str) -> str | None:
    patterns = [
        r"(?:已有|已经有|现在有|手头有)\s*([^，。；;\n]{1,20})",
        r"(?:有[一1]?(?:个|件|副|台|盏|份|部|张|只|套))\s*([^，。；;\n]{1,20})",
        r"(没有|无)(?:类似|替代|可替代|同类)?(?:物品|东西|替代品)?",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            value = match.group(1)
            if value in {"没有", "无"}:
                return value
            return _clean_phrase(value)
    return None


def _extract_frequency(text: str) -> str | None:
    patterns = [
        r"(?:预计|大概|可能|平时|基本|一般)?\s*(每天|每日|每周\d+次|一周\d+次|每周|每月\d+次|偶尔|经常|高频|低频)\s*(?:使用|会用)?",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    return None


def _extract_trigger(text: str) -> str | None:
    triggers = ["刚需", "促销", "种草", "朋友推荐", "情绪", "旧物损坏", "学习需要", "工作需要"]
    for trigger in triggers:
        if trigger in text:
            return trigger
    if "最近需要" in text or "需要安静" in text:
        return "刚需"
    return None


def _clean_product_name(value: str) -> str:
    # 商品名只应该保留“要买什么”，不能把用途、预算、补充说明一起吞进去。
    # 所以这里专门按照购物描述里常见的语义分隔词截断，而不是简单按长度硬切。
    product = re.split(r"(?:为了|用于|用来|最近|预计|本月|这次|已有|已经有|现在有|手头有|还剩|预算)", value.strip())[0]
    product = re.split(r"[。；;，,\n]", product)[0]
    return _strip_leading_quantity(product)


def _clean_phrase(value: str, strip_quantity: bool = True) -> str:
    cleaned = re.split(r"[。；;，,\n]", value.strip())[0].strip()
    return _strip_leading_quantity(cleaned) if strip_quantity else cleaned


def _strip_leading_quantity(value: str) -> str:
    # 这里不能再像旧逻辑那样“只要首字像量词就删掉”，因为中文里很多真实商品名
    # 本身就是以这些字开头的，例如“台灯”“台式机”。如果无条件删除首字，会把真实
    # 商品名误裁成“灯”“式机”，直接影响后续 create_case 和主流程演示。
    #
    # 因此这里只移除“数量词边界明确”的前缀，例如“一个键盘”“一副耳机”“1台显示器”。
    # 这类前缀同时满足两个条件：
    # 1. 前面有数量信息（如“一”“1”“两”“2”）；
    # 2. 数量后面跟的是量词。
    #
    # 这样既能保留正常的量词清洗能力，也能避免把“台灯”“台式机”这种本体词误伤。
    cleaned = re.sub(
        r"^(?:(?:一|1|两|2)\s*(?:个|件|副|台|盏|份|部|张|只|套))",
        "",
        value,
    ).strip()
    return cleaned


def _is_missing(value: Any) -> bool:
    return value is None or value == "" or value == "不知道"


def _build_next_question(missing_fields: list[str]) -> str | None:
    if not missing_fields:
        return None
    questions = {
        "product_name": "你具体想买的商品或服务是什么？",
        "price": "这个商品大约多少钱？",
        "purpose": "你买它主要是为了解决什么问题，或用于什么场景？",
        "monthly_budget_left": "你本月剩余可支配预算大约还有多少？",
        "owned_alternatives": "你现在是否已经有类似物品或可以替代它的东西？",
        "expected_usage_frequency": "如果买了，你预计多久会使用一次？",
        "trigger_reason": "这次想买它的直接原因是什么，比如刚需、促销、种草、朋友推荐、情绪驱动或旧物损坏？",
    }
    selected = missing_fields[:3]
    return "为了进入购物法庭分析，还需要补充：" + " ".join(questions[field] for field in selected)
