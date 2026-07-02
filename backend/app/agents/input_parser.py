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


def parse_input(
    raw_input: str,
    existing_collected_fields: dict[str, Any] | None = None,
) -> ParserResult:
    existing = existing_collected_fields or {}

    if _is_high_risk(raw_input):
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

    extracted = _extract_shopping_fields(raw_input)
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
    price = _extract_first_number(text)
    if price is not None:
        fields["price"] = price

    budget = _extract_budget(text)
    if budget is not None:
        fields["monthly_budget_left"] = budget

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


def _extract_first_number(text: str) -> float | None:
    match = re.search(r"(\d+(?:\.\d+)?)\s*(?:元|块|rmb|RMB|￥)?", text)
    return float(match.group(1)) if match else None


def _extract_budget(text: str) -> float | None:
    patterns = [
        r"(?:预算|生活费|可支配)[^\d]{0,8}(?:还剩|剩余|有)?\s*(\d+(?:\.\d+)?)",
        r"(?:还剩|剩余)\s*(\d+(?:\.\d+)?)\s*(?:元|块)?.{0,8}(?:预算|生活费)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return float(match.group(1))
    return None


def _extract_product(text: str) -> str | None:
    patterns = [
        r"(\d+(?:\.\d+)?)\s*(?:元|块).{0,4}的([\u4e00-\u9fa5A-Za-z0-9]+)",
        r"(?:买|入手|下单|换|办|购买)(?:一[个件副台盏份])?\s*(?:(?:\d+(?:\.\d+)?)\s*(?:元|块)\s*的?)?\s*([\u4e00-\u9fa5A-Za-z]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            product = match.group(match.lastindex or 1)
            product = re.sub(r"^(一个|一件|一副|一台|一盏|一份)", "", product)
            return product[:20]
    return None


def _extract_purpose(text: str) -> str | None:
    patterns = [
        r"(?:为了|用于|用来|最近需要)([\u4e00-\u9fa5A-Za-z0-9，,。；; ]{2,30})",
        r"(学习|通勤|运动|降噪|提升效率|安静|备考)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return _clean_phrase(match.group(1))
    return None


def _extract_alternatives(text: str) -> str | None:
    patterns = [
        r"(?:已有|有|现在有)([\u4e00-\u9fa5A-Za-z0-9，,。；; ]{2,30})",
        r"(没有|无)(?:类似|替代|可替代|同类)?(?:物品|东西|替代品)?",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return _clean_phrase(match.group(1))
    return None


def _extract_frequency(text: str) -> str | None:
    patterns = [
        r"(每天|每日|每周\d?次|一周\d?次|偶尔|只用一次|经常|高频)",
        r"(?:预计|大概|可能).{0,6}(每天|每周|偶尔|经常)",
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


def _clean_phrase(value: str) -> str:
    return re.split(r"[。；;，,\n]", value.strip())[0].strip()


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
