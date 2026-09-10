from __future__ import annotations

from typing import Any

from backend.app.agents.field_normalizer import (
    FREQ_UNKNOWN,
    canonical_frequency,
    canonical_trigger,
    is_high_frequency,
    is_impulse_trigger,
    normalize_alternatives,
    has_related_risk_evidence,
    split_evidence_by_relevance,
)
from backend.app.schemas.decision import AgentStep, DecisionReport, RagEvidence, ToolResult, now_iso
from backend.app.services.llm_client import DeepSeekLLMClient, get_llm_client


# ==================== 判决参数（集中在此，便于评审与调参） ====================

# 规则版本：报告里一并落库，便于事后复算"当时按哪一版规则判的"。
RULE_VERSION = "judge-rules-v2"

# 成本占比低于该值且成本风险为 low：属于小额低风险消费，直接放行，不进冷静期。
LOW_COST_RATIO = 0.01
# 仅凭"相关历史风险证据"判暂缓的最低金额门槛（占剩余预算）。
# 低于该比例时，历史教训只作为报告里的参考，不单独否决购买。
RISK_EVIDENCE_RATIO_FLOOR = 0.1
# 冲动型触发（促销/种草/推荐/情绪）判暂缓的最低金额门槛。
# 低于该比例的小额冲动消费只作提醒，不强制进入冷静期。
IMPULSE_TRIGGER_RATIO_FLOOR = 0.05
# 综合评分达到该值才允许规则把结论推向 buy（评分不达标时退回到更保守的结论）。
SCORE_BUY_FLOOR = 45


def run_judge_agent(
    case_id: str,
    collected_fields: dict[str, Any],
    pro_step: AgentStep,
    con_step: AgentStep,
    rag_evidence: list[RagEvidence],
    tool_results: list[ToolResult],
) -> tuple[AgentStep, DecisionReport]:
    cost_result = next((item for item in tool_results if item.tool_name == "cost_analyzer"), None)
    score_result = next((item for item in tool_results if item.tool_name == "decision_score"), None)

    final_decision, decision_basis, decision_strength = _evaluate(
        collected_fields, rag_evidence, cost_result, score_result
    )
    confidence = _confidence(rag_evidence, cost_result)
    product = collected_fields.get("product_name", "该商品")
    price = collected_fields.get("price", "未知价格")
    purpose = collected_fields.get("purpose", "未说明用途")

    local_summary = _summary(final_decision, product, rag_evidence)
    cooling_result = next((item for item in tool_results if item.tool_name == "cooling_reminder"), None)
    next_actions = _next_actions(final_decision, rag_evidence, cost_result, cooling_result)
    local_arguments = _judge_arguments(final_decision, rag_evidence, cost_result, decision_basis)
    explanation = _generate_judge_explanation(
        final_decision,
        collected_fields,
        pro_step,
        con_step,
        rag_evidence,
        tool_results,
        local_summary,
        local_arguments,
    )
    report = DecisionReport(
        report_id=f"report_{case_id}",
        case_id=case_id,
        case_type="shopping",
        final_decision=final_decision,
        confidence=confidence,
        summary=explanation["summary"],
        case_summary=f"用户想购买 {price} 元的{product}，主要用途是{purpose}。",
        pro_points=pro_step.arguments,
        con_points=con_step.arguments,
        rag_evidence=rag_evidence,
        tool_results=tool_results,
        next_actions=next_actions,
        created_at=now_iso(),
        decision_basis=decision_basis,
        decision_strength=decision_strength,
        rule_version=RULE_VERSION,
        input_snapshot=_input_snapshot(collected_fields, cost_result, score_result, rag_evidence),
    )
    judge_step = AgentStep(
        agent="judge_agent",
        status="completed",
        summary=explanation["summary"],
        confidence=confidence,
        arguments=explanation["arguments"],
        used_rag_ids=[item.id for item in rag_evidence],
        used_tool_names=[item.tool_name for item in tool_results],
        error=None,
    )
    return judge_step, report


def _generate_judge_explanation(
    final_decision: str,
    collected_fields: dict[str, Any],
    pro_step: AgentStep,
    con_step: AgentStep,
    rag_evidence: list[RagEvidence],
    tool_results: list[ToolResult],
    fallback_summary: str,
    fallback_arguments: list[str],
) -> dict[str, Any]:
    client = get_llm_client()
    if not isinstance(client, DeepSeekLLMClient):
        return {"summary": fallback_summary, "arguments": fallback_arguments}

    try:
        response = client.complete_json(
            "judge_agent",
            {
                "collected_fields": collected_fields,
                "final_decision": final_decision,
                "pro_agent_result": {
                    "summary": pro_step.summary,
                    "arguments": pro_step.arguments,
                    "confidence": pro_step.confidence,
                },
                "con_agent_result": {
                    "summary": con_step.summary,
                    "arguments": con_step.arguments,
                    "confidence": con_step.confidence,
                },
                "rag_evidence": [
                    {"id": item.id, "title": item.title, "content": item.content, "tags": item.tags}
                    for item in rag_evidence
                ],
                "tool_results": [
                    {
                        "tool_name": item.tool_name,
                        "status": item.status,
                        "summary": item.summary,
                        "risk_level": item.risk_level,
                        "metrics": item.metrics,
                        "error": item.error,
                    }
                    for item in tool_results
                ],
            },
        )
        # complete_json uses mock output after transport failure; do not expose generic mock text as a verdict.
        if response.get("summary") == "mock LLM returned no task-specific content":
            raise ValueError("judge explanation fallback response")
        return {"summary": response["summary"], "arguments": list(response["arguments"])}
    except Exception:
        return {"summary": fallback_summary, "arguments": fallback_arguments}


def _decide(
    fields: dict[str, Any],
    rag_evidence: list[RagEvidence],
    cost_result: ToolResult | None,
    score_result: ToolResult | None = None,
) -> str:
    """兼容旧调用：只返回结论。完整依据见 `_evaluate`。"""
    return _evaluate(fields, rag_evidence, cost_result, score_result)[0]


def _evaluate(
    fields: dict[str, Any],
    rag_evidence: list[RagEvidence],
    cost_result: ToolResult | None,
    score_result: ToolResult | None = None,
) -> tuple[str, list[dict[str, str]], float]:
    """判决入口：核心规则 + 与决策评分的一致性说明。"""
    decision, basis, strength = _evaluate_core(fields, rag_evidence, cost_result, score_result)
    score = _score_value(score_result)
    score_risk = (score_result.metrics or {}).get("risk_level") if score_result and score_result.status == "success" else None
    if score is not None and score_risk == "low" and decision != "buy":
        # 评分工具说“积极执行”，规则却给出更保守的结论：把分歧写进依据，避免报告自相矛盾。
        basis.append({
            "rule": "E1",
            "detail": (
                f"决策评分为 {score} 分（工具建议积极执行），但规则基于成本风险/触发原因/证据相关性"
                f"给出了 {decision}；本报告以规则结论为准，评分仅作参考。"
            ),
            "effect": "info",
        })
    return decision, basis, strength


def _evaluate_core(
    fields: dict[str, Any],
    rag_evidence: list[RagEvidence],
    cost_result: ToolResult | None,
    score_result: ToolResult | None = None,
) -> tuple[str, list[dict[str, str]], float]:
    """按“硬约束短路 + 决策表”产生结论。

    与旧实现的区别（本轮修复）：
      1. 字段先归一到受控值（每天使用 == 每天、暂无 == 没有、朋友推荐 == 推荐）；
      2. 只有“明确能覆盖核心需求的替代品”才判 alternative，不再仅凭“提到过已有物品”一票否决；
      3. 新增小额低风险短路与“评分参与 buy 门槛”，4 元级消费不再被判暂缓；
      4. 历史证据先做相关性过滤，无关记录只展示、不参与判决；
      5. 输出判决依据与结论强度，报告里可解释、可回归测试。

    返回 (final_decision, decision_basis, decision_strength)。
    """
    risk_level = cost_result.risk_level if cost_result and cost_result.status == "success" else None
    ratio = _cost_ratio(fields, cost_result)
    score = _score_value(score_result)
    frequency = canonical_frequency(fields)
    trigger = canonical_trigger(fields)
    alternatives = normalize_alternatives(
        fields.get("owned_alternatives"), fields.get("alternative_covers_need")
    )
    related, unrelated = split_evidence_by_relevance(rag_evidence, fields)
    related_risk = has_related_risk_evidence(related)

    basis: list[dict[str, str]] = []

    def hit(rule: str, detail: str, effect: str) -> None:
        basis.append({"rule": rule, "detail": detail, "effect": effect})

    if unrelated:
        hit(
            "E0",
            f"{len(rag_evidence)} 条历史证据中 {len(related)} 条与本案相关，"
            f"{len(unrelated)} 条仅作参考、未计入判决。",
            "info",
        )

    for field_name, detail in (fields.get("_field_conflicts") or {}).items():
        if isinstance(detail, dict) and detail.get("canonical"):
            hit(
                "E5",
                f"{field_name} 的模型受控值（{detail.get('canonical')}）与用户原话（{detail.get('text')}）不一致，"
                "已按“未说明”处理，建议下一轮向用户确认。",
                "info",
            )

    # ---------- 硬约束：先短路 ----------
    if risk_level == "high":
        hit("H1", "成本风险为 high，超出可承受范围。", "reject")
        return "reject", basis, 0.9

    if ratio is not None and ratio <= LOW_COST_RATIO and risk_level == "low" and not related_risk and not fields.get("price_is_unit"):
        hit(
            "H2",
            f"该商品仅占剩余预算 {_percent(ratio)}（≤{_percent(LOW_COST_RATIO)}）且成本风险 low，"
            "属于小额低风险消费，无需进入冷静期。",
            "buy",
        )
        return "buy", basis, 0.9

    if fields.get("price_is_unit"):
        # 单价不能代表总价：小额短路与“低风险放行”都不适用，避免把 5元/斤 当成 5 元总价。
        hit("E2", "当前金额是单价，总价未知，小额放行规则不适用。", "info")

    # ---------- 决策表 ----------
    if risk_level == "medium":
        hit("R1", "成本风险为 medium，预算压力需要先观察。", "delay")
        return "delay", basis, 0.8

    if is_impulse_trigger(trigger) and (ratio is None or ratio >= IMPULSE_TRIGGER_RATIO_FLOOR):
        hit("R1", f"触发原因为{_trigger_label(trigger)}，属于冲动型触发。", "delay")
        return "delay", basis, 0.8

    if is_impulse_trigger(trigger):
        # 小额冲动消费只提醒：几十块的促销/种草不值得强制 3 天冷静期。
        hit(
            "E4",
            f"触发原因为{_trigger_label(trigger)}（冲动型），但仅占预算 {_percent(ratio)}，"
            f"低于{IMPULSE_TRIGGER_RATIO_FLOOR:.0%}的否决线，仅作提醒。",
            "info",
        )

    if related_risk and (ratio is None or ratio >= RISK_EVIDENCE_RATIO_FLOOR):
        hit("R1", "相关历史证据中出现闲置/后悔/预算类风险信号。", "delay")
        return "delay", basis, 0.8

    if related_risk:
        # 历史教训只是"参考"：金额占预算很小时不足以单独改变结论（避免把 6% 的日常刚需判成暂缓）。
        hit(
            "E3",
            f"参考到相关历史风险证据，但该商品仅占预算 {_percent(ratio)}，"
            f"低于{RISK_EVIDENCE_RATIO_FLOOR:.0%}的单独否决线，不改变结论。",
            "info",
        )

    if alternatives["has"] and alternatives.get("covers_core_need") is True:
        hit("R2", "已有替代品明确可以覆盖核心需求，无需重复购买。", "alternative")
        return "alternative", basis, 0.8

    if risk_level is not None and is_high_frequency(frequency) and (score is None or score >= SCORE_BUY_FLOOR):
        detail = f"使用频率为{_frequency_label(frequency)}"
        detail += f"，综合评分 {score} 达到放行线（≥{SCORE_BUY_FLOOR}）。" if score is not None else "，属于高频使用。"
        hit("R3", detail, "buy")
        return "buy", basis, 0.7

    if alternatives["has"]:
        hit("R4", "提到已有替代品，但无法确认是否覆盖核心需求，建议先比较替代方案。", "alternative")
        return "alternative", basis, 0.65

    # 成本不构成压力、评分也不低于放行线，且前面没有任何风险规则命中 -> 可以考虑购买。
    # 这条覆盖“低价小商品/信息不全但无风险”的场景：不再因为“没说每天用”就一律暂缓。
    if risk_level == "low" and score is not None and score >= SCORE_BUY_FLOOR and not fields.get("price_is_unit"):
        hit(
            "R5",
            f"成本风险 low 且综合评分 {score} 不低于放行线（≥{SCORE_BUY_FLOOR}），"
            "未触发任何风险规则，按可承受的消费处理。",
            "buy",
        )
        return "buy", basis, 0.6

    if risk_level is None:
        reason = "成本工具不可用，无法确认预算承受度"
    elif score is None:
        reason = "决策评分不可用，缺少放行依据"
    elif frequency != FREQ_UNKNOWN:
        reason = "使用频率不高且缺少其他放行依据"
    else:
        reason = "关键信息不足"
    hit("R6", f"{reason}，按保守口径进入冷静期复核。", "delay")
    return "delay", basis, 0.5


def _input_snapshot(
    fields: dict[str, Any],
    cost_result: ToolResult | None,
    score_result: ToolResult | None,
    rag_evidence: list[RagEvidence],
) -> dict[str, Any]:
    """记录本次判决真正吃到的输入（归一化后的字段 + 工具关键指标 + 证据条数）。"""
    def _pick(name: str) -> Any:
        value = fields.get(name)
        return value if value not in (None, "") else None

    return {
        "product_name": _pick("product_name"),
        "price": _pick("price"),
        "monthly_budget_left": _pick("monthly_budget_left"),
        "frequency": canonical_frequency(fields),
        "trigger": canonical_trigger(fields),
        "alternatives": normalize_alternatives(
            fields.get("owned_alternatives"), fields.get("alternative_covers_need")
        ),
        "cost_ratio": _cost_ratio(fields, cost_result),
        "cost_risk": cost_result.risk_level if cost_result and cost_result.status == "success" else None,
        "price_basis": (cost_result.metrics or {}).get("price_basis") if cost_result else None,
        "quantity": fields.get("quantity"),
        "score": _score_value(score_result),
        "evidence_count": len(rag_evidence),
    }


def _cost_ratio(fields: dict[str, Any], cost_result: ToolResult | None) -> float | None:
    """优先用原始金额现算占比。

    工具返回的 `budget_ratio` 只保留两位小数（54/4000=1.35% 会报成 0.01），
    直接拿它和 1% 阈值比较会让"小额短路"误判，所以这里先用精确值计算，
    只有字段缺失时才回落到工具指标。
    """
    try:
        price = float(fields.get("price"))
        budget = float(fields.get("monthly_budget_left"))
    except (TypeError, ValueError):
        price = budget = None
    if price is not None and budget is not None and budget > 0:
        if fields.get("price_is_unit") and fields.get("quantity") not in (None, ""):
            try:
                price = price * float(fields["quantity"])
            except (TypeError, ValueError):
                pass
        return price / budget

    if cost_result and cost_result.status == "success":
        raw = (cost_result.metrics or {}).get("budget_ratio")
        try:
            if raw is not None:
                return float(raw)
        except (TypeError, ValueError):
            pass
    if budget == 0:
        return 1.0
    return None


def _score_value(score_result: ToolResult | None) -> int | None:
    if not score_result or score_result.status != "success":
        return None
    raw = (score_result.metrics or {}).get("score")
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _percent(ratio: float) -> str:
    return f"{round(ratio * 100, 2)}%"


def _frequency_label(value: str) -> str:
    return {
        "daily": "每天",
        "weekly_3plus": "每周三次以上",
        "weekly_1_2": "每周一两次",
        "monthly": "每月",
        "occasional": "偶尔",
        "unknown": "未说明",
    }.get(value, value)


def _trigger_label(value: str) -> str:
    return {
        "need": "刚需",
        "promotion": "促销",
        "recommendation": "他人推荐/种草",
        "emotion": "情绪驱动",
        "unknown": "未说明",
    }.get(value, value)


def _confidence(rag_evidence: list[RagEvidence], cost_result: ToolResult | None) -> float:
    """证据可用度（不是结论正确率）：有命中证据、成本工具可用时更高。"""
    confidence = 0.72
    if rag_evidence:
        confidence += 0.08
    else:
        confidence -= 0.12
    if cost_result and cost_result.status == "success":
        confidence += 0.05
    elif cost_result:
        confidence -= 0.1
    return round(max(0.3, min(confidence, 0.9)), 2)


def _summary(final_decision: str, product: str, rag_evidence: list[RagEvidence]) -> str:
    labels = {
        "buy": "可以考虑购买",
        "delay": "建议暂缓购买 3 天后复盘",
        "reject": "当前不建议购买",
        "alternative": "建议先寻找替代方案",
    }
    suffix = "" if rag_evidence else " 未找到相关历史证据，本次判断主要基于当前输入和工具结果。"
    return f"本案对{product}的辅助建议是：{labels[final_decision]}。{suffix}"


def _next_actions(
    final_decision: str,
    rag_evidence: list[RagEvidence],
    cost_result: ToolResult | None,
    cooling_result: ToolResult | None,
) -> list[str]:
    actions: list[str] = []
    if final_decision in {"delay", "alternative"}:
        actions.append("加入观察清单，3 天后复盘真实需求。")
        actions.append("比较已有替代品或低价替代方案能否满足核心用途。")
    if final_decision == "buy":
        actions.append("购买前再次确认不会影响本月必要支出。")
    if final_decision == "reject":
        actions.append("记录本次放弃原因，避免被同类促销反复触发。")
    if not rag_evidence:
        actions.append("未找到相关历史证据，建议后续补充购买复盘记录。")
    if cost_result and cost_result.status == "failed":
        actions.append("预算工具不可用，建议手动核对本月剩余预算。")
    if cooling_result and cooling_result.status == "success":
        actions.append("冷静期提醒已创建，可按期复盘。")
    if cooling_result and cooling_result.status == "failed":
        actions.append("提醒创建失败，建议手动设置 3 天后复盘。")
    return actions


def _judge_arguments(
    final_decision: str,
    rag_evidence: list[RagEvidence],
    cost_result: ToolResult | None,
    decision_basis: list[dict[str, str]] | None = None,
) -> list[str]:
    arguments = [f"最终建议为 {final_decision}。"]
    for item in decision_basis or []:
        if item.get("effect") != "info":
            arguments.append(f"[{item['rule']}] {item['detail']}")
    if cost_result:
        arguments.append(cost_result.summary)
    if rag_evidence:
        arguments.append(f"引用 {len(rag_evidence)} 条真实返回的 RAG 历史证据。")
    else:
        arguments.append("未找到相关历史证据，没有编造历史记录。")
    return arguments
