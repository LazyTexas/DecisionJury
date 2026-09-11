from __future__ import annotations

import os
import re
from typing import Any

from backend.app.agents.field_normalizer import resolve_frequency, resolve_trigger
from backend.app.agents.reply_composer import (
    CLARIFY_FIELDS,
    ENHANCED_FIELDS,
    FIELD_LABELS,
    SKIPPED_VALUE,
    build_reply_plan,
    is_skip_signal,
    natural_question,
    optional_question,
)

# 澄清上限：每个字段最多确认一次，全局最多两轮（避免把收集变成审问）。
MAX_CLARIFY_ROUNDS = 2
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
MINIMUM_DECISION_FIELDS = ["product_name", "price", "monthly_budget_left"]

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
    recent_turns: list[str] | None = None,
    existing_is_authoritative: bool = False,
    is_first_turn: bool = False,
) -> ParserResult:
    """解析一轮输入。

    `existing_is_authoritative=True` 用于**判决阶段重放案件首条描述**的场景：
    此时 `raw_input` 是历史文本，而已收集字段是累计（含用户后续纠正）后的权威状态，
    因此本轮解析只允许补齐缺口，不允许用旧文本覆盖已有值。
    普通对话轮保持 False：最新一轮发言可以更新/纠正历史值。

    `is_first_turn=True`（建案那一轮）会额外产出欢迎语，用于"先欢迎、再收集"。
    """
    existing = dict(existing_collected_fields or {})
    normalized_input = _normalize_text(raw_input)

    high_risk = _is_high_risk(normalized_input)

    local_result = _build_rule_result(normalized_input, existing, existing_is_authoritative)
    if high_risk:
        local_result.is_high_risk = True
        local_result.reject_reason = "high_risk_domain"
        local_result.agent_step.summary = "输入包含高风险主题标记，但本次继续按案件信息进行分析。"
    client = get_llm_client()
    # 正常购物字段统一交给 DeepSeek，只有请求失败或结果校验失败时才使用本地规则。
    if isinstance(client, DeepSeekLLMClient):
        payload = {
            "current_message": normalized_input,
            "existing_collected_fields": existing,
            "existing_missing_fields": local_result.missing_fields,
            # 允许模型发问的目标字段（修复 1）：模型只能就这些字段提问，并在 dialogue.ask_field 里声明。
            "askable_fields": [f for f in local_result.missing_fields if f in FIELD_LABELS],
            # 对话上下文：让模型能承接上一句、不复读、能处理"就刚才那个"这类指代。
            "recent_turns": list(recent_turns or [])[-12:],
            "last_question": existing.get("_last_question"),
            "already_asked_fields": existing.get("_asked_fields", []),
        }
        result = None
        last_error: Exception | None = None
        attempts = 2 if os.getenv("PARSER_SELF_CONSISTENCY", "").strip() in {"1", "true", "yes"} else 1
        seen_canonical: dict[str, set] = {}
        for attempt in range(attempts):     # 失败重试一次：网络抖动/JSON 偶发不合法不至于整轮降级
            try:
                payload_result = client.complete_parser_json(payload)
                for key in ("frequency_canonical", "trigger_canonical"):
                    if payload_result.get(key):
                        seen_canonical.setdefault(key, set()).add(payload_result[key])
                result = _build_llm_result(payload_result, existing, normalized_input,
                                           existing_is_authoritative)
                break
            except Exception as exc:
                last_error = exc
        if result is not None and attempts > 1:
            # 自一致检查（可选）：两次采样给出不同受控值 → 按"不确定"处理，交给澄清。
            for key, values in seen_canonical.items():
                if len(values) > 1:
                    result.merged_fields.pop(key, None)
                    result.merged_fields.setdefault("_field_conflicts", {})[key] = {
                        "canonical": "/".join(sorted(values)),
                        "text": result.merged_fields.get(
                            "expected_usage_frequency" if key == "frequency_canonical" else "trigger_reason"
                        ),
                        "resolved": "unknown",
                    }
        if result is None:
            # 真实解析失败时保留已有本地规则结果，保证多轮收集不中断（并标记降级）。
            local_result.parser_used = "local_fallback"
            local_result.agent_step.error = f"deepseek_parser_failed: {type(last_error).__name__}"
            result = local_result
    else:
        result = local_result
    return _finalize(result, existing, normalized_input, existing_is_authoritative, is_first_turn)


# 单价 / 数量语义：用于避免把“5元/斤”的单价当成总价去算预算占比。
_PRICE_UNIT_PATTERN = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:元|块)\s*(?:[/／]|每)?\s*(?:一|1)?\s*"
    r"(斤|公斤|千克|克|两|个|件|盒|袋|瓶|包|只|张|套|台|支|份|颗|粒|片|条|寸|G|GB|T|TB|M|MB|ml|L|米|平方米|平米|升|毫升|公里|人|次|小时|天|月)"
)
_QUANTITY_PATTERN = re.compile(
    r"(?:买|要|来|需要|打算买|准备买|购)\s*(\d+)\s*(斤|公斤|千克|克|个|件|盒|袋|瓶|包|只|张|套|台|支|份|颗|粒|片|条|G|GB|T|TB|M|MB|ml|L)"
)
# 数量+单位的所有候选；纠正语序下取最后一个（"不是60颗，是30颗" → 30）
_QTY_UNIT_ALL = re.compile(
    r"(\d+)\s*(斤|公斤|千克|克|个|件|盒|袋|瓶|包|只|张|套|台|支|份|颗|粒|片|条|G|GB|T|TB|M|MB|ml|L)"
)
# 纠正语序：「不是60颗，是30颗」——取最后一个数量为准
_QUANTITY_CORRECTION_PATTERN = re.compile(
    r"(?:不是|改成|改为|其实|准确说)[^。；;，,]{0,12}?[，,]?\s*(?:是|要|买|有)?\s*(\d+)\s*"
    r"(斤|公斤|千克|克|个|件|盒|袋|瓶|包|只|张|套|台|支|份|颗|粒|片|条|G|GB|T|TB|M|MB|ml|L)"
)


def _assign(merged: dict[str, Any], key: str, value: Any, authoritative: bool) -> None:
    """权威模式（判决阶段重放历史文本）下，已有值优先：只补缺口，不覆盖累计状态。"""
    if authoritative and merged.get(key) not in (None, ""):
        return
    merged[key] = value


def _merge_layers(existing: dict[str, Any], *layers: dict[str, Any],
                  authoritative: bool = False) -> dict[str, Any]:
    """按层合并字段；后层优先。

    `authoritative=True`（判决阶段重放案件首条描述）时，已有非空值不被任何一层覆盖——
    否则"首条描述里的旧数字"会盖掉用户后来纠正的值（真实事故：
    `想买4袋` + 后续 `不是4袋，是2袋` → 判决按 4 袋算成 11%，实际应为 2 袋 5.6%）。
    """
    merged = {**existing}
    for layer in layers:
        for key, value in (layer or {}).items():
            if value in (None, ""):
                continue
            _assign(merged, key, value, authoritative)
    return merged


def _merge_price_semantics(merged: dict[str, Any], text: str, field_meta: dict[str, Any],
                           authoritative: bool = False) -> None:
    """补充 price_unit / quantity / price_is_unit，供成本工具与判决区分单价与总价。

    旧实现把“5元/斤”的数值 5 当作商品价格直接算预算占比，可能把单价当总价、
    也可能漏掉数量；这里把语义显式记下来（不改动 price 数值本身）。
    """
    meta = field_meta if isinstance(field_meta, dict) else {}
    quantity = meta.get("quantity")
    correction = re.search(r"(?:不是|改成|改为|其实|准确说)", text)
    if correction:
        found = _QTY_UNIT_ALL.findall(text[correction.start():])
        if found:
            quantity = int(found[-1][0])   # 纠正语序：以最后一个说法为准
    match = _QUANTITY_PATTERN.search(text)
    if quantity in (None, "") and match:
        quantity = match.group(1)
    if quantity in (None, ""):
        pass
        if match:
            quantity = int(match.group(1))
    if quantity not in (None, ""):
        try:
            _assign(merged, "quantity", int(quantity), authoritative)
        except (TypeError, ValueError):
            pass

    unit = meta.get("price_unit")
    match = _PRICE_UNIT_PATTERN.search(text)
    if not unit and match:
        unit = match.group(2)
    # 只有当入库价格就是那个单价值时才标记为单价；如果模型已经把它换算成总价
    # （例如“2元一寸×27寸=54元”），标记为单价会导致成本工具再乘一次数量。
    if unit and match is not None:
        # 原话给出的是单价（"1元一G"）。模型有时会自行换算成总价（128），
        # 此时以本地识别到的单价为准，并用该单位回抓数量，避免"纠正数量后金额不变"。
        try:
            unit_price = float(match.group(1))
            if merged.get("price") is None:
                merged["price"] = unit_price          # 缺口补齐：两种情况都允许
            elif not authoritative and abs(float(merged["price"]) - unit_price) > 1e-6:
                merged["price"] = unit_price          # 本轮文本改写金额：仅普通对话轮
                merged["_price_corrected_from"] = merged.get("price_before_correction")
        except (TypeError, ValueError):
            pass
        if merged.get("quantity") in (None, "", 0):
            hit = re.search(r"(\d+)\s*" + re.escape(str(unit)), text)
            if hit:
                try:
                    merged["quantity"] = int(hit.group(1))
                except (TypeError, ValueError):
                    pass
    if unit:
        _assign(merged, "price_unit", str(unit), authoritative)
        _assign(merged, "price_is_unit", True, authoritative)
        # 按单价单位回抓数量：'5元一颗…想买60颗'、'2元一寸…27寸' 这类商品名夹在中间的说法
        if merged.get("quantity") in (None, "", 0):
            hit = re.search(r"(\d+)\s*" + re.escape(str(unit)), text)
            if hit:
                try:
                    merged["quantity"] = int(hit.group(1))
                except (TypeError, ValueError):
                    pass
        # 供类型化事实层做一致性校验（声明单价但价格已是总价时按总价处理）
        try:
            merged["_price_unit_value"] = float(match.group(1))
        except (AttributeError, TypeError, ValueError):
            pass
    elif meta.get("price_is_unit") is None:
        merged.setdefault("price_is_unit", False)


def _finalize(result: ParserResult, existing: dict[str, Any], normalized_input: str,
              authoritative: bool = False, is_first_turn: bool = False) -> ParserResult:
    """收集阶段的收尾：跳过处理 + 可选追问熔断计数 + 生成结构化回复计划。

    这里集中“怎么说话”的规则（承接、一次只问一个、跳过后不再重复问、
    可选追问最多两轮），保证本地规则路径与模型路径表现一致。
    `authoritative=True`：判决阶段重放历史文本，已有字段优先。
    `is_first_turn=True`：建案那一轮，额外产出欢迎语（先欢迎、再收集）。
    """
    this_turn_fields: dict[str, Any] = {**result.extracted_fields, **result.correction_fields}
    merged = dict(result.merged_fields)
    skipped_field: str | None = None
    skip_rejected_field: str | None = None
    _merge_price_semantics(merged, normalized_input, {}, authoritative)

    if is_skip_signal(normalized_input):
        current_field = existing.get("_current_question_key")
        if current_field in ENHANCED_FIELDS:
            # 增强字段允许跳过：记为“未说明”，之后不再重复追问
            merged[current_field] = SKIPPED_VALUE
            merged["_skipped_fields"] = sorted(set(merged.get("_skipped_fields") or []) | {current_field})
            this_turn_fields[current_field] = SKIPPED_VALUE
            result.extracted_fields = {**result.extracted_fields, current_field: SKIPPED_VALUE}
            result.merged_fields = merged
            result.missing_fields = [f for f in REQUIRED_SHOPPING_FIELDS if _is_missing(merged.get(f))]
            unresolved = [f for f in MINIMUM_DECISION_FIELDS if _is_missing(merged.get(f))]
            result.is_complete = not unresolved and not result.conflicts
            result.case_status = "ready_for_debate" if result.is_complete else "collecting"
            if result.is_complete:
                result.next_question_key, result.next_question = _enhanced_question(result.missing_fields)
            else:
                result.next_question_key, result.next_question = _next_question(
                    result.missing_fields, result.conflicts, normalized_input
                )
            skipped_field = current_field
        elif current_field:
            # 核心字段（商品/价格/预算）跳过会导致无法分析，换成给范围的追问
            skip_rejected_field = current_field

    # 修 1：把"受控值 vs 文本"的冲突真正消费掉——写入字段，供判决依据与下一轮追问使用。
    freq_value, freq_conflict = resolve_frequency(merged)
    trig_value, trig_conflict = resolve_trigger(merged)
    field_conflicts: dict[str, Any] = {}
    if freq_conflict:
        field_conflicts["expected_usage_frequency"] = {
            "canonical": merged.get("frequency_canonical"),
            "text": merged.get("expected_usage_frequency"),
            "resolved": freq_value,
        }
    if trig_conflict:
        field_conflicts["trigger_reason"] = {
            "canonical": merged.get("trigger_canonical"),
            "text": merged.get("trigger_reason"),
            "resolved": trig_value,
        }
    if merged.pop("_evidence_mismatch", None):
        field_conflicts.setdefault("_evidence_mismatch", {})["dropped"] = "canonical_value_without_quote"
    if field_conflicts:
        merged["_field_conflicts"] = field_conflicts
        result.merged_fields = merged

    # S2 澄清循环：冲突/弃权的字段 → 二选一确认；每字段最多 1 次、全局最多 2 轮。
    clarify_field: str | None = None
    asked = dict(merged.get("_clarify_asked") or {})
    rounds = int(merged.get("_clarify_rounds") or 0)
    if rounds < MAX_CLARIFY_ROUNDS:
        candidates = list((merged.get("_field_conflicts") or {}).keys()) + list((merged.get("_abstained") or {}).keys())
        for field_name in candidates:
            if field_name in CLARIFY_FIELDS and asked.get(field_name, 0) == 0:
                clarify_field = field_name
                break
    if clarify_field:
        asked[clarify_field] = asked.get(clarify_field, 0) + 1
        merged["_clarify_asked"] = asked
        merged["_clarify_rounds"] = rounds + 1
        result.merged_fields = merged

    optional_asked = int(merged.get("_optional_asked") or 0)
    plan = build_reply_plan(
        this_turn_fields=this_turn_fields,
        merged_fields=merged,
        missing_fields=result.missing_fields,
        is_complete=result.is_complete,
        next_question_key=result.next_question_key,
        next_question=result.next_question,
        conflicts=result.conflicts,
        skipped_field=skipped_field,
        skip_rejected_field=skip_rejected_field,
        optional_asked=optional_asked,
        dialogue=result.dialogue,
        last_question=existing.get("_last_question"),
        corrections=result.correction_fields,
        previous_fields=existing,
        user_text=normalized_input,
        clarify_field=clarify_field,
        asked_fields=list(merged.get("_asked_fields") or []),
        include_welcome=is_first_turn,
        closing_sent=bool(merged.get("_closing_sent")),
    )
    # 结束语只发一次：这一轮发了就记住；下一轮又开始追问时重新武装（下次收尾还要给）。
    if plan.get("closing"):
        merged["_closing_sent"] = True
    elif plan.get("question"):
        merged.pop("_closing_sent", None)
    # 熔断计数口径（修复 2）：只要"信息已齐之后仍在发问"就计数，不区分问题来自本地模板还是模型。
    if plan.get("counts_toward_optional") and plan.get("question"):
        merged["_optional_asked"] = optional_asked + 1
        result.merged_fields = merged
    # 记录本轮问了什么，供下一轮做"不复读"判定与上下文
    if plan.get("question"):
        merged["_last_question"] = plan["question"]
    # 记账用"实际问的那个字段"（模型声明并通过校验的 ask_field 优先），
    # 而不是本地模板原本想用的字段——否则模型自问的维度永远不进 already_asked_fields。
    asked_target = plan.get("ask_field") if plan.get("question") else None
    if not asked_target and plan.get("question"):
        asked_target = result.next_question_key
    if asked_target:
        asked = list(merged.get("_asked_fields") or [])
        if asked_target not in asked:
            asked.append(asked_target)
        merged["_asked_fields"] = asked
    # 降级可见（I1）：模型不可用时明确标记，前端据此提示“这轮用的是本地规则”。
    degraded = result.parser_used in {"local_fallback", "local"}
    plan["degraded"] = degraded
    if degraded:
        plan["degraded_reason"] = result.agent_step.error or "模型不可用，本轮使用本地规则解析"
    plan["parser_used"] = result.parser_used
    result.merged_fields = merged
    result.reply_plan = plan
    return result


def _build_rule_result(normalized_input: str, existing: dict[str, Any],
                       authoritative: bool = False) -> ParserResult:
    extracted, corrections, field_meta, conflicts = _extract_shopping_details(normalized_input, existing)
    prior_product = existing.get("product_name")
    new_product = extracted.get("product_name")
    base_existing = dict(existing)
    if prior_product and new_product and prior_product != new_product:
        # 商品名由本轮明确表达覆盖；历史字段默认视为已确认信息并保留。
        field_meta["product_name"] = {
            "status": "confirmed", "confidence": 0.98, "provenance": "user_explicit",
            "action": "replace", "old_value": prior_product, "new_value": new_product,
        }
    merged = _merge_layers(base_existing, extracted, corrections, authoritative=authoritative)
    missing_fields = [field for field in REQUIRED_SHOPPING_FIELDS if _is_missing(merged.get(field))]
    for field in REQUIRED_SHOPPING_FIELDS:
        field_meta.setdefault(
            field,
            {
                "status": "missing" if _is_missing(merged.get(field)) else "confirmed",
                "provenance": "history" if field in existing else "unknown",
            },
        )
    unresolved_required = [field for field in MINIMUM_DECISION_FIELDS if _is_missing(merged.get(field))]
    is_complete = not unresolved_required and not conflicts
    status = "ready_for_debate" if is_complete else "collecting"
    termination_reason = "complete_minimum_fields" if is_complete else (
        "uncertain_required_fields" if conflicts else "missing_required_fields"
    )
    next_question_key, next_question = _next_question(missing_fields, conflicts, normalized_input)
    if is_complete and missing_fields:
        # 与 LLM 路径保持一致：核心信息已齐时给“可选补充”的追问，而不是阻塞式追问。
        next_question_key, next_question = _enhanced_question(missing_fields)

    step = AgentStep(
        agent="input_parser",
        status="completed",
        summary=f"识别为 shopping，缺失字段：{', '.join(missing_fields) if missing_fields else '无'}。",
        confidence=0.9 if extracted or corrections or existing else 0.65,
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
        correction_fields=corrections,
        field_meta=field_meta,
        conflicts=conflicts,
        next_question_key=next_question_key,
        is_complete=is_complete,
        termination_reason=termination_reason,
        parser_used="local",
    )


def _build_llm_result(
    llm_result: dict[str, Any],
    existing: dict[str, Any],
    normalized_input: str = "",
    authoritative: bool = False,
) -> ParserResult:
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
    # 明确纠正优先于本轮普通表达，再覆盖历史值；普通补充不会覆盖已确认历史值。
    # 重放历史文本（authoritative）时反过来：已有值优先，本轮只补缺口。
    merged = _merge_layers(existing, extracted, corrections, authoritative=authoritative)
    # 模型的替代品等效判断（存在 field_meta 里）并入字段，供判决 R2 分支使用。
    covers = (llm_result.get("field_meta") or {}).get("owned_alternatives", {})
    if isinstance(covers, dict) and covers.get("covers_core_need") is not None:
        _assign(merged, "alternative_covers_need", covers["covers_core_need"], authoritative)
    if llm_result.get("alternative_covers_need") is not None:
        _assign(merged, "alternative_covers_need", llm_result["alternative_covers_need"], authoritative)
    # 模型直接给的受控值（契约优先）：存下来，判决与评分优先读它，其次才从中文文本归一。
    for canonical_key in ("frequency_canonical", "trigger_canonical"):
        value = llm_result.get(canonical_key)
        if value:
            _assign(merged, canonical_key, value, authoritative)
    if llm_result.get("price_basis") == "unit":
        _assign(merged, "price_is_unit", True, authoritative)
        if llm_result.get("price_unit"):
            _assign(merged, "price_unit", llm_result["price_unit"], authoritative)
    if llm_result.get("quantity") is not None:
        _assign(merged, "quantity", llm_result["quantity"], authoritative)

    # 证据契约（span grounding）：模型填的每个字段都要引用用户原话片段；
    # 片段不在原话里 → 该字段直接作废（宁可留空，也不要无依据的值）。
    # 字符偏移由服务端从片段定位得到（确定性），不让模型自己数位置。
    evidence = llm_result.get("evidence") or {}
    abstained: dict[str, str] = {}
    spans: dict[str, dict[str, Any]] = {}
    for field_name, quote in evidence.items():
        quote = str(quote)
        start = normalized_input.find(quote)
        if start >= 0:
            spans[field_name] = {
                "text": quote,
                "start": start,
                "end": start + len(quote),
            }
        if field_name not in merged or merged.get(field_name) in (None, ""):
            continue
        if start >= 0:
            continue
        merged.pop(field_name, None)
        extracted.pop(field_name, None)
        corrections.pop(field_name, None)
        abstained[field_name] = quote
    if spans:
        merged["_evidence_spans"] = spans
    if abstained:
        merged["_abstained"] = abstained

    # 漂移兜底（零延迟）：受控值必须能被它自己的证据片段佐证——
    # evidence 归一出另一个值，说明模型这次"给错了值"，丢弃受控值并回落文本归一。
    from backend.app.agents.field_normalizer import normalize_frequency, normalize_trigger

    for canonical_key, evidence_key, normalizer in (
        ("frequency_canonical", "frequency_evidence", normalize_frequency),
        ("trigger_canonical", "trigger_evidence", normalize_trigger),
    ):
        value = merged.get(canonical_key)
        quote = llm_result.get(evidence_key)
        if not value or not quote:
            continue
        implied = normalizer(str(quote))
        if implied != "unknown" and implied != value:
            merged.pop(canonical_key, None)
            merged.setdefault("_field_conflicts", {})[canonical_key] = {
                "canonical": value,
                "text": str(quote),
                "resolved": implied,
            }
    # 修 3：受控值必须能被原话佐证——evidence 与原话不匹配就丢弃受控值，回落文本归一。
    for canonical_key, evidence_key in (("frequency_canonical", "frequency_evidence"),
                                        ("trigger_canonical", "trigger_evidence")):
        value = merged.get(canonical_key)
        evidence = llm_result.get(evidence_key)
        if value and evidence:
            if str(evidence).strip() and str(evidence).strip() in normalized_input:
                continue
            merged.pop(canonical_key, None)
            merged.setdefault("_evidence_mismatch", []).append(canonical_key)
    _merge_price_semantics(merged, normalized_input, llm_result.get("field_meta") or {}, authoritative)
    missing = [field for field in REQUIRED_SHOPPING_FIELDS if _is_missing(merged.get(field))]
    conflicts = list(llm_result.get("conflicts") or [])
    unresolved_required = [field for field in MINIMUM_DECISION_FIELDS if _is_missing(merged.get(field))]
    is_complete = not unresolved_required and not conflicts
    status = "ready_for_debate" if is_complete else "collecting"
    # 追问只有**一个**来源：本地算出的目标字段（key）+ 本地模板文案（base question）。
    # 模型想用自己的措辞，必须走 dialogue.question + dialogue.ask_field，由 reply_composer 的
    # 闸门校验目标是否合法——见下面的"旧字段折叠"。
    next_question_key, generated_question = _next_question(missing, conflicts, "")
    if is_complete:
        # 核心信息已齐、但增强字段仍缺失时，给一句“可选补充”的追问，
        # 而不是返回 None 让 B 端只能拼兜底文案（旧的空 next_question 问题）。
        next_question_key, next_question = _enhanced_question(missing)
    else:
        # 本地模板作为兜底文案；模型措辞经由 dialogue 走闸门（不在这里直接采用）
        next_question = generated_question

    # 旧字段折叠（真实事故的根因）：模型常把问句写进 next_question、把目标写成另一个字段，
    # 于是"屏幕显示的文本"和"系统记账的追问目标"长期不一致——显示上在问价格，记账里却一直是
    # missing[0]（本案七轮全是 product_name），判重/闸门全部落空。
    # 现在把它折叠成同一条受闸门管的路径：只有在 dialogue.question 为空时，才把旧措辞当
    # "候选问句 + 候选目标"塞进 dialogue，由闸门校验（目标不在允许集合内就丢弃、回落本地模板）。
    dialogue = dict(llm_result.get("dialogue") or {})
    legacy_question = str(llm_result.get("next_question") or "").strip()
    if not str(dialogue.get("question") or "").strip() and legacy_question:
        dialogue["question"] = legacy_question
        if not str(dialogue.get("ask_field") or "").strip():
            dialogue["ask_field"] = str(llm_result.get("next_question_key") or "").strip()
    step = AgentStep(
        agent="input_parser",
        status="completed",
        summary=(
            f"识别为 shopping，包含高风险主题标记，缺失字段：{', '.join(missing) if missing else '无'}。"
            if llm_result["is_high_risk"]
            else f"识别为 shopping，缺失字段：{', '.join(missing) if missing else '无'}。"
        ),
        confidence=llm_result["confidence"],
        arguments=[f"已收集字段：{', '.join(sorted(merged.keys())) or '无'}"],
        error=None,
    )
    return ParserResult(
        case_type="shopping",
        is_supported=True,
        is_high_risk=llm_result["is_high_risk"],
        reject_reason=llm_result.get("reject_reason") if llm_result["is_high_risk"] else None,
        extracted_fields=extracted,
        merged_fields=merged,
        missing_fields=missing,
        next_question=next_question,
        case_status=status,
        agent_step=step,
        correction_fields=corrections,
        field_meta=dict(llm_result.get("field_meta") or {}),
        conflicts=conflicts,
        # 记账目标只认本地算出的字段（模型想换目标只能通过 dialogue.ask_field 走闸门）
        next_question_key=next_question_key,
        is_complete=is_complete,
        termination_reason=("complete_minimum_fields" if is_complete else ("uncertain_required_fields" if conflicts else "missing_required_fields")),
        parser_used="deepseek",
        dialogue=dialogue,
    )


def _is_high_risk(text: str) -> bool:
    return any(keyword in text for keyword in HIGH_RISK_KEYWORDS)


def _extract_shopping_fields(text: str) -> dict[str, Any]:
    fields, _, _, _ = _extract_shopping_details(text, {})
    return fields


def _extract_shopping_details(
    text: str, existing: dict[str, Any] | None = None
) -> tuple[dict[str, Any], dict[str, Any], dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """返回本轮字段、明确纠正、字段状态元数据和金额歧义。"""
    fields: dict[str, Any] = {}
    corrections: dict[str, Any] = {}
    field_meta: dict[str, dict[str, Any]] = {}
    conflicts: list[dict[str, Any]] = []

    # 预算和价格都表现为“数字 + 元”，但业务语义完全不同。
    # 这里必须先识别预算语义，再决定某个金额能不能当作商品价格，
    # 否则“本月预算还剩3000元”这类补充消息会被错误写进 price。
    budget_match = _extract_budget_match(text)
    correction_budget = _extract_budget_correction(text)
    budget = correction_budget if correction_budget is not None else (budget_match[0] if budget_match else None)
    if budget is not None:
        fields["monthly_budget_left"] = budget
        field_meta["monthly_budget_left"] = _amount_meta(text, budget, budget_match[2] if budget_match else None)

    correction_price = _extract_price_correction(text)
    price = correction_price if correction_price is not None else _extract_price(text, budget_match[1] if budget_match else None)
    if price is not None:
        fields["price"] = price
        field_meta["price"] = _amount_meta(text, price, None)

    if correction_price is not None:
        corrections["price"] = correction_price
        fields.pop("price", None)
    if correction_budget is not None:
        corrections["monthly_budget_left"] = correction_budget
        fields.pop("monthly_budget_left", None)

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

    # 只有没有价格/预算语义时，才把多个带单位金额作为候选歧义，不强行归类。
    if budget is None and price is None:
        candidates = _amount_candidates(text)
        if len(candidates) >= 2:
            product = fields.get("product_name") or _extract_bare_product(text, candidates)
            if product:
                fields["product_name"] = product
            conflicts.append({"type": "amount_ambiguity", "candidates": candidates})
            field_meta["price"] = {"status": "uncertain", "candidates": candidates}
            field_meta["monthly_budget_left"] = {"status": "uncertain", "candidates": candidates}

    for key in set(fields) | set(corrections):
        field_meta.setdefault(key, {"status": "confirmed", "confidence": 0.9, "provenance": "user_explicit"})
    return fields, corrections, field_meta, conflicts


def _normalize_text(text: str) -> str:
    # 这里只做最轻量的文本归一化：统一空白和货币符号，避免中文输入里
    # 因为全角字符、额外空格或换行导致正则边界失效。我们不做激进清洗，
    # 是为了保留“最近学习需要安静”“已有普通耳机”这类句子原本的语义线索。
    normalized = text.replace("\u3000", " ")
    normalized = normalized.replace("￥", "元")
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def _extract_budget_match(text: str) -> tuple[float, tuple[int, int], str] | None:
    amount = r"(?:\d+(?:\.\d+)?|[零〇一二两三四五六七八九十百千万亿]+)"
    patterns = [
        rf"(?:本月|这个月)?(?:预算|生活费|可支配预算|可支配金额|剩余预算)[^\d零〇一二两三四五六七八九十百千万亿]{{0,8}}(?:还剩|剩余|还有|有)?\s*({amount})\s*(?:元|块)?",
        rf"(?:本月|这个月)?(?:还剩|剩余|还有)\s*({amount})\s*(?:元|块)?[^\n，。；;]{{0,8}}(?:预算|生活费|可支配)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return _parse_amount(match.group(1)), match.span(1), match.group(1)
    return None


def _extract_price(text: str, budget_span: tuple[int, int] | None) -> float | None:
    amount = r"(?:\d+(?:\.\d+)?|[零〇一二两三四五六七八九十百千万亿]+)"
    patterns = [
        # 动词在金额之后：“花4元买”“4块钱入手”——旧正则要求动词在前，这类句式全部漏识别。
        rf"(?:花|花了|用了|掏了|掏)\s*({amount})\s*(?:元|块|rmb|RMB)?\s*(?:钱)?\s*(?:买|购|入手|下单|办)",
        rf"(?:想买|买|购买|入手|下单|换|办|考虑买|准备买)(?:(?:一|1|两|二|三|四|五|六|七|八|九)\s*)?(?:个|件|副|台|盏|份|部|张|只|套)?\s*[^\d零〇一二两三四五六七八九十百千万亿]{{0,6}}({amount})\s*(?:元|块|rmb|RMB)",
        rf"({amount})\s*(?:元|块|rmb|RMB)\s*的",
        rf"(?:价格|商品价|售价|金额)\s*(?:是|为|大约是|约为|大概是)?\s*({amount})\s*(?:元|块|rmb|RMB)?",
    ]
    if budget_span is not None:
        # 只有当同句已经识别出预算时，另一个带“元/块”的金额才兜底当作商品价格
        # （如“预算 3000 元，芒果 4 元”）。没有预算时必须保留金额歧义判定，
        # 不能把“2000，冰可乐，3块”这类输入直接猜成价格。
        patterns.append(rf"({amount})\s*(?:元|块|rmb|RMB)")
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

    # 口语中的“两千五”“三千五”通常表示两千五百/三千五百。
    shorthand_thousand = re.fullmatch(r"([一二三四五六七八九])千([一二三四五六七八九])", normalized)
    if shorthand_thousand:
        return float(digits[shorthand_thousand.group(1)] * 1000 + digits[shorthand_thousand.group(2)] * 100)
    # 口语中的“三百五”通常表示三百五十。
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
    # Limit each side to the amount's clause so nearby budget statements stay separate.
    clause_boundary = r"[，,。.;；!?！？]"
    before = re.split(clause_boundary, text[context_start:span[0]])[-1]
    after = re.split(clause_boundary, text[span[1]:context_end])[0]
    context = before + text[span[0]:span[1]] + after
    return any(keyword in context for keyword in BUDGET_CONTEXT_KEYWORDS)


def _extract_product(text: str) -> str | None:
    patterns = [
        r"(?:想买|买|购买|入手|下单|换|办|考虑买|准备买)(?:[一1]?(?:个|件|副|台|盏|份|部|张|只|套))?\s*(?:(?:\d+(?:\.\d+)?)\s*(?:元|块|rmb|RMB)\s*的?)?\s*([^\s，。；;]+)",
        # “<商品>价格是N元”这类句式：商品名在“价格”之前（水果价格是5元一斤）。
        r"([^\s，。；;、]{2,12}?)的?价格\s*(?:是|为|大约|大概)?\s*(?:\d+(?:\.\d+)?|[零〇一二两三四五六七八九十百千万亿]+)",
        # 动词在金额之后：“花4元买芒果” / “4块钱入手键盘”。
        r"(?:花|花了|用了|掏了|掏)\s*(?:\d+(?:\.\d+)?|[零〇一二两三四五六七八九十百千万亿]+)\s*(?:元|块|rmb|RMB)?\s*(?:钱)?\s*(?:买|购|入手|下单|办)\s*([^\s，。；;]+)",
        r"\d+(?:\.\d+)?\s*(?:元|块|rmb|RMB)\s*的([^\s，。；;]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            product = _clean_product_name(match.group(match.lastindex or 1))
            if product:
                return product[:20]
    # 兜底：没有购买动词时，从“<商品> N 元”结构里取商品名（如“预算 3000 元，芒果 4 元”）。
    return _extract_product_before_amount(text, _extract_budget_match(text))


# 这些词单独出现在金额前面时不是商品名（“花4元买”里的“花”）。
_PRODUCT_STOPWORDS = {
    "花", "花了", "用", "用了", "掏", "掏了", "买", "想买", "购买", "大概", "大约", "约",
    "价格", "钱", "预算", "本月", "这个月", "还剩", "剩余", "余额", "生活费", "可支配",
}


def _extract_product_before_amount(text: str, budget_match: tuple[float, tuple[int, int], str] | None) -> str | None:
    """从“<商品> N 元”里取商品名；跳过预算金额本身与预算上下文。"""
    amount = r"(?:\d+(?:\.\d+)?|[零〇一二两三四五六七八九十百千万亿]+)"
    budget_span = budget_match[1] if budget_match else None
    for match in re.finditer(rf"({amount})\s*(?:元|块|rmb|RMB)", text):
        span = match.span(1)
        if budget_span and span == budget_span:
            continue
        if _is_budget_context(text, span):
            continue
        clause = re.split(r"[，,。；;\n]", text[:match.start()])[-1]
        candidate = _clean_product_name(clause)
        if not candidate or candidate in _PRODUCT_STOPWORDS:
            continue
        if re.fullmatch(r"[\d\s.]+", candidate):
            continue
        if any(word in candidate for word in ("预算", "本月", "剩余", "生活费", "可支配", "价格", "售价")):
            continue
        return candidate[:20]
    return None


def _amount_candidates(text: str) -> list[dict[str, Any]]:
    amount = r"(?:\d+(?:\.\d+)?|[零〇一二两三四五六七八九十百千万亿]+)"
    candidates: list[dict[str, Any]] = []
    for match in re.finditer(rf"({amount})\s*(元|块|大洋|人民币|rmb|RMB)", text):
        try:
            value = _parse_amount(match.group(1))
        except ValueError:
            continue
        candidates.append({"value": value, "raw_text": match.group(0), "approximate": bool(re.search(r"左右|大概|大约|来块|多", text[max(0, match.start()-4):match.end()+4])), "unit": "CNY"})
    # 速记输入允许第一个金额省略单位，例如“2000，冰可乐，3块”。
    if len(candidates) < 2:
        for part in re.split(r"[，,、;；]", text):
            token = part.strip()
            match = re.fullmatch(rf"({amount})", token)
            if not match:
                continue
            try:
                value = _parse_amount(match.group(1))
            except ValueError:
                continue
            candidates.insert(0, {"value": value, "raw_text": token, "approximate": False, "unit": "CNY"})
    return candidates


def _extract_bare_product(text: str, candidates: list[dict[str, Any]]) -> str | None:
    # 覆盖“2000，冰可乐，3块”这类没有动词的简短输入。
    parts = [part.strip() for part in re.split(r"[，,、;；]", text) if part.strip()]
    for part in parts:
        if not re.search(r"(?:\d|元|块|大洋|人民币)", part) and len(part) <= 20:
            return _clean_product_name(part)
    return None


def _amount_meta(text: str, value: float, raw: str | None) -> dict[str, Any]:
    raw_text = raw or str(value).rstrip("0").rstrip(".")
    window = text[max(0, text.find(raw_text)-5): text.find(raw_text)+len(raw_text)+5] if raw_text in text else text
    return {
        "status": "confirmed",
        "confidence": 0.95,
        "provenance": "user_explicit",
        "value": value,
        "raw_text": raw_text,
        "approximate": bool(re.search(r"大概|大约|左右|来块|多", window)),
        "unit": "CNY",
    }


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
    triggers = ["刚需", "促销", "种草", "朋友推荐", "情绪", "旧物损坏", "学习需要", "工作需要", "别人有", "同事买了", "看到别人用"]
    for trigger in triggers:
        if trigger in text:
            return trigger
    if "最近需要" in text or "需要安静" in text:
        return "刚需"
    if any(item in text for item in ("别人有", "同事买了", "看到别人用")):
        return "社交影响"
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


def _next_question(
    missing_fields: list[str], conflicts: list[dict[str, Any]] | None = None, text: str = ""
) -> tuple[str | None, str | None]:
    if conflicts:
        return "price_or_budget", "这两个金额我有点分不清：哪个是商品价格，哪个是本月预算？"
    if not missing_fields:
        return None, None
    key = missing_fields[0]
    return key, natural_question(key)


# 核心三字段之外的增强字段：核心信息已齐时仍可“可选补充”，用于提高分析质量。
# 核心三字段之外的增强字段：定义已下沉到 reply_composer（两处共用，避免漂移）


def _enhanced_question(missing_fields: list[str]) -> tuple[str | None, str | None]:
    """核心信息已齐、但增强字段仍缺失时的“可选补充”追问。

    文案取自 reply_composer，保证与 B 端展示、快捷选项一致；
    仍按“一次问一个”，且不改变 case_status（不阻塞进入分析）。
    """
    for field in ENHANCED_FIELDS:
        if field in missing_fields:
            return field, optional_question(field)
    return None, None


def _build_next_question(missing_fields: list[str]) -> str | None:
    """兼容旧内部调用：现在每次只询问一个字段。"""
    return _next_question(missing_fields)[1]
