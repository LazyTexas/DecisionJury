from __future__ import annotations

import re
from typing import Any

from backend.app.schemas.decision import AgentStep, ParserResult
from backend.app.services.llm_client import DeepSeekLLMClient, get_llm_client


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

    local_result = _build_rule_result(normalized_input, existing)
    client = get_llm_client()
    # 正常购物字段统一交给 DeepSeek，只有请求失败或结果校验失败时才使用本地规则。
    if isinstance(client, DeepSeekLLMClient):
        try:
            llm_result = client.complete_parser_json(
                {
                    "current_message": normalized_input,
                    "existing_collected_fields": existing,
                    "existing_missing_fields": local_result.missing_fields,
                }
            )
            return _build_llm_result(llm_result, existing)
        except Exception:
            # 真实解析失败时保留已有本地规则结果，保证多轮收集不中断。
            return local_result
    return local_result


def _build_rule_result(normalized_input: str, existing: dict[str, Any]) -> ParserResult:
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


def _build_llm_result(
    llm_result: dict[str, Any],
    existing: dict[str, Any],
) -> ParserResult:
    if llm_result["is_high_risk"]:
        step = AgentStep(
            agent="input_parser",
            status="completed",
            summary="输入命中高风险领域，已拒绝进入购物法庭辩论。",
            confidence=llm_result["confidence"],
            arguments=["当前项目仅支持购物和时间类低风险日常决策。"],
            error=None,
        )
        return ParserResult(
            case_type=None,
            is_supported=False,
            is_high_risk=True,
            reject_reason=llm_result.get("reject_reason") or "high_risk_domain",
            extracted_fields={},
            merged_fields={},
            missing_fields=[],
            next_question=None,
            case_status="rejected",
            agent_step=step,
        )

    if not llm_result.get("is_supported", True):
        step = AgentStep(
            agent="input_parser",
            status="completed",
            summary="输入不属于当前支持的购物决策范围。",
            confidence=llm_result["confidence"],
            arguments=["当前项目仅支持购物类低风险日常决策。"],
            error=None,
        )
        return ParserResult(
            case_type=None,
            is_supported=False,
            is_high_risk=False,
            reject_reason=llm_result.get("reject_reason") or "unsupported_case_type",
            extracted_fields={},
            merged_fields={},
            missing_fields=[],
            next_question=None,
            case_status="rejected",
            agent_step=step,
        )

    extracted = {
        key: value
        for key, value in llm_result["extracted_fields"].items()
        if value not in (None, "")
    }
    corrections = {
        key: value
        for key, value in llm_result["correction_fields"].items()
        if value not in (None, "")
    }
    merged = {**existing, **extracted, **corrections}
    missing = [field for field in REQUIRED_SHOPPING_FIELDS if _is_missing(merged.get(field))]
    status = "ready_for_debate" if not missing else "collecting"
    next_question = None if not missing else (llm_result.get("next_question") or _build_next_question(missing))
    step = AgentStep(
        agent="input_parser",
        status="completed",
        summary=f"识别为 shopping，缺失字段：{', '.join(missing) if missing else '无'}。",
        confidence=llm_result["confidence"],
        arguments=[f"已收集字段：{', '.join(sorted(merged.keys())) or '无'}"],
        error=None,
    )
    return ParserResult(
        case_type="shopping",
        is_supported=True,
        is_high_risk=False,
        reject_reason=None,
        extracted_fields=extracted,
        merged_fields=merged,
        missing_fields=missing,
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
    correction_budget = _extract_budget_correction(text)
    budget = correction_budget if correction_budget is not None else (budget_match[0] if budget_match else None)
    if budget is not None:
        fields["monthly_budget_left"] = budget

    correction_price = _extract_price_correction(text)
    price = correction_price if correction_price is not None else _extract_price(text, budget_match[1] if budget_match else None)
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
    amount = r"(?:\d+(?:\.\d+)?|[零〇一二两三四五六七八九十百千万亿]+)"
    patterns = [
        rf"(?:本月|这个月)?(?:预算|生活费|可支配预算|可支配金额|剩余预算)[^\d零〇一二两三四五六七八九十百千万亿]{{0,8}}(?:还剩|剩余|还有|有)?\s*({amount})\s*(?:元|块)?",
        rf"(?:本月|这个月)?(?:还剩|剩余|还有)\s*({amount})\s*(?:元|块)?[^\n，。；;]{{0,8}}(?:预算|生活费|可支配)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return _parse_amount(match.group(1)), match.span(1)
    return None


def _extract_price(text: str, budget_span: tuple[int, int] | None) -> float | None:
    amount = r"(?:\d+(?:\.\d+)?|[零〇一二两三四五六七八九十百千万亿]+)"
    patterns = [
        rf"(?:想买|买|购买|入手|下单|换|办|考虑买|准备买)(?:(?:一|1|两|二|三|四|五|六|七|八|九)\s*)?(?:个|件|副|台|盏|份|部|张|只|套)?\s*[^\d零〇一二两三四五六七八九十百千万亿]{{0,6}}({amount})\s*(?:元|块|rmb|RMB)",
        rf"({amount})\s*(?:元|块|rmb|RMB)\s*的",
        rf"(?:价格|商品价|售价|金额)\s*(?:是|为|大约是|约为|大概是)?\s*({amount})\s*(?:元|块|rmb|RMB)",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            number_span = match.span(1)
            if budget_span and number_span == budget_span:
                continue
            if _is_budget_context(text, number_span):
                continue
            return _parse_amount(match.group(1))
    return None


def _extract_price_correction(text: str) -> float | None:
    """识别明确的价格纠正，避免本地 fallback 保留用户刚才说错的金额。"""
    if any(keyword in text for keyword in BUDGET_CONTEXT_KEYWORDS) and not any(
        keyword in text for keyword in ("价格", "商品价", "售价")
    ):
        return None

    amount = r"(?:\d+(?:\.\d+)?|[零〇一二两三四五六七八九十百千万亿]+)"
    patterns = [
        rf"(?:价格|金额)?\s*不是\s*{amount}\s*(?:元|块)?[，,\s]*?(?:是|应为|应该是|改为|改成)\s*({amount})",
        rf"刚才说错了[，,\s]*(?:价格|金额)?\s*(?:是|改为|改成)\s*({amount})",
        rf"(?:价格|金额)\s*(?:改为|改成)\s*({amount})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return _parse_amount(match.group(1))
    return None


def _extract_budget_correction(text: str) -> float | None:
    """预算纠正必须独立解析，避免新预算被误写进商品价格。"""
    amount = r"(?:\d+(?:\.\d+)?|[零〇一二两三四五六七八九十百千万亿]+)"
    patterns = [
        rf"(?:预算|生活费|可支配预算|可支配金额|剩余预算)\s*不是\s*{amount}\s*(?:元|块)?[，,\s]*?(?:是|应为|应该是|改为|改成)\s*({amount})",
        rf"刚才说错了[，,\s]*(?:预算|生活费|可支配金额)\s*(?:是|改为|改成)\s*({amount})",
        rf"(?:预算|生活费|可支配金额)\s*(?:改为|改成)\s*({amount})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return _parse_amount(match.group(1))
    return None


def _parse_amount(value: str) -> float:
    """把阿拉伯数字或常见中文数字金额转换为浮点数。"""
    value = value.strip()
    if not value:
        raise ValueError("amount is empty")
    if re.fullmatch(r"\d+(?:\.\d+)?", value):
        return float(value)

    if not re.fullmatch(r"[零〇一二两三四五六七八九十百千万亿]+", value):
        raise ValueError("amount contains invalid Chinese numerals")

    digits = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
              "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
    normalized = value.replace("两", "二")
    if normalized in digits:
        return float(digits[normalized])

    # 口语中的“三千五”通常表示三千五百，优先处理这个简写。
    shorthand = re.fullmatch(r"([一二三四五六七八九])([千百])([一二三四五六七八九])", normalized)
    if shorthand:
        multiplier = {"千": 1000, "百": 100}[shorthand.group(2)]
        return float(digits[shorthand.group(1)] * multiplier + digits[shorthand.group(3)] * multiplier // 10)

    units = {"十": 10, "百": 100, "千": 1000, "万": 10000, "亿": 100000000}
    total = 0
    section = 0
    number = 0
    for char in normalized:
        if char in digits:
            number = digits[char]
        elif char in units:
            unit = units[char]
            if unit >= 10000:
                section += number
                total += section * unit
                section = 0
            else:
                section += (number or 1) * unit
            number = 0
    result = total + section + number
    if result <= 0:
        raise ValueError("amount must be positive")
    return float(result)


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
    pattern = r"(每周[\d一二两三四五六七八九十]+次|一周[\d一二两三四五六七八九十]+次|每月[\d一二两三四五六七八九十]+次|每天|每日|每周|偶尔|经常|高频|低频)"
    for match in re.finditer(pattern, text):
        preceding = text[max(0, match.start() - 8):match.start()]
        if re.search(r"(?:不是|不会|并非|不)\s*$", preceding):
            continue
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
