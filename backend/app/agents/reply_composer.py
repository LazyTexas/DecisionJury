"""信息收集阶段的回复编排：把“字段状态”翻译成自然对话文案。

设计目标（见 docs/02_SPEC.md §5.1.2）：

    每轮回复 = 承接(ack) + 只问一个问题(question) + 快捷选项(chips) + 是否可结束(can_stop)

为什么要有这个模块：模型只负责“把话变成字段”，**怎么说话必须是确定性的本地规则**——
否则一旦模型降级，文案会漂移；“一次只问一个”“跳过后不再重复问”“最多两轮可选追问”
这些对话策略也需要可测试、可回归。

本模块不依赖任何 Agent/服务，属于叶子模块，供 input_parser 与 routers/chat 复用。
"""

from __future__ import annotations

import re
from typing import Any

# ==================== 字段文案 ====================

FIELD_LABELS = {
    "product_name": "商品",
    "price": "价格",
    "purpose": "用途",
    "monthly_budget_left": "剩余预算",
    "owned_alternatives": "已有替代品",
    "expected_usage_frequency": "使用频率",
    "trigger_reason": "购买原因",
}

# 核心三字段之外的"增强字段"：可以可选补充，但不阻塞出判决书。
# （下沉到这里是为了让 input_parser 与 reply_composer 共用同一份定义，避免两处漂移。）
ENHANCED_FIELDS = ("purpose", "owned_alternatives", "expected_usage_frequency", "trigger_reason")

# 阻塞式追问（核心字段还缺）：口语化，不带“为了进入购物法庭分析”这类系统口吻。
MISSING_FIELD_QUESTIONS = {
    "product_name": "你想买的是什么？",
    "price": "这个大概多少钱？",
    "monthly_budget_left": "本月还剩多少可支配预算？",
    "purpose": "主要拿来做什么用？",
    "owned_alternatives": "你手上已经有能替代它的东西吗？",
    "expected_usage_frequency": "大概多久会用一次？",
    "trigger_reason": "这次想买它的直接原因是什么？比如刚需、促销、被种草。",
}

# 可选追问（核心信息已齐）：同样只问一个，但明确是“可选”。
OPTIONAL_QUESTION_PREFIX = "想更准的话，再补一句："

# 每个字段的快捷选项：降低输入成本，同时给出结构化取值。
QUESTION_CHIPS: dict[str, list[str]] = {
    "purpose": ["工作/学习用", "家用", "娱乐", "说不清"],
    "owned_alternatives": ["没有", "有一个类似的"],
    "expected_usage_frequency": ["每天", "每周几次", "偶尔"],
    "trigger_reason": ["刚需/旧的坏了", "促销或种草", "一时冲动"],
    "monthly_budget_left": ["3000 元左右", "1000 元左右", "不太确定"],
    "product_name": [],
    "price": ["还没查价", "大概这个范围"],
}

# 用户明确跳过时用的占位值：被 _is_missing 视为“已说明”，避免反复追问。
SKIPPED_VALUE = "未说明"

SKIP_SIGNALS = (
    "不知道", "不清楚", "不确定", "说不好", "没想过", "暂时没想过",
    "跳过", "不回答", "不想说", "随便", "你看着办", "无所谓",
)

# 核心信息齐了之后的结束邀请：给用户出口，而不是把对话停在系统提问上。
STOP_INVITE = "核心信息够了，随时可以出判决书；也可以再补一两句让它更准。"
# 收集收尾的结束语（只在"这一轮起不再追问"的那一次出现，不重复刷）
CLOSING_MESSAGE = "信息收集就到这里。想补充随时说，准备好了就点「启动辩论分析」，我给你出判决书。"
# 结束语已经给过、用户继续说又没有新信息时的短回应（避免落回"信息仍在收集中"这种误导兜底）
READY_NUDGE = "收到，信息已经够了，随时可以出判决书。"


def build_welcome(product_name: str | None = None) -> str:
    """建案后的欢迎语：先打招呼、说清接下来做什么，再进入信息收集。"""
    subject = f"「{product_name}」这笔决策" if product_name else "这个决策"
    return (
        f"你好，我是你的购物决策参谋。接下来我会问几个问题，把{subject}的关键信息理清楚，"
        "然后开庭给你一份判决书；中途想直接出结论，随时说“直接分析”。"
    )


SKIP_ACK = "行，这项先跳过。"
SKIP_REJECTED_QUESTION = "这项还是得有个大概的数，给个范围也行："
CONFLICT_QUESTION = "这两个金额我有点分不清：哪个是商品价格，哪个是本月预算？"


def natural_question(field: str) -> str:
    return MISSING_FIELD_QUESTIONS.get(field, f"能再说说{FIELD_LABELS.get(field, field)}吗？")


def optional_question(field: str) -> str:
    return OPTIONAL_QUESTION_PREFIX + natural_question(field)


def question_chips(field: str | None) -> list[str]:
    if not field:
        return []
    return list(QUESTION_CHIPS.get(field, []))


def is_skip_signal(text: str) -> bool:
    """用户是否在明确跳过当前问题（“不知道/跳过/随便”等）。"""
    cleaned = (text or "").strip()
    if not cleaned:
        return False
    if any(signal in cleaned for signal in SKIP_SIGNALS):
        return True
    # 口语变体：“不太确定 / 不太清楚 / 不怎么确定”
    return re.search(r"不(太|很|怎么|太怎么)?(确定|清楚|知道|了解)", cleaned) is not None


# ==================== 承接句（ack） ====================

def render_value(field: str, value: Any) -> str:
    """把一个字段渲染成人话片段，用于承接句回显。"""
    if isinstance(value, float) and value.is_integer():
        text = str(int(value))          # 30.0 -> 30，避免“价格 30.0 元”
    else:
        text = str(value).strip()
    if field == "price":
        return f"价格 {text} 元"
    if field == "monthly_budget_left":
        return f"预算还剩 {text} 元"
    if field == "product_name":
        return f"商品是{text}"
    if field == "owned_alternatives":
        if text == SKIPPED_VALUE:
            return "已有替代品：先跳过"
        return "没有替代品" if text in {"无", "没有"} else f"已有：{text}"
    return f"{FIELD_LABELS.get(field, field)}：{text}"


def build_ack(this_turn_fields: dict[str, Any], merged: dict[str, Any]) -> str:
    """本轮新识别/纠正的字段 -> 一句承接。没有新信息时返回空串。"""
    parts: list[str] = []
    for field in ("product_name", "price", "monthly_budget_left", "purpose",
                  "owned_alternatives", "expected_usage_frequency", "trigger_reason"):
        if field in this_turn_fields:
            parts.append(render_value(field, this_turn_fields[field]))
    if not parts:
        return ""
    return "记下了：" + "、".join(parts) + "。"


# ==================== 回复计划 ====================

# 需要澄清的字段 → 一次一个的二选一问句与快捷选项（不猜，去问）。
CLARIFY_QUESTIONS: dict[str, str] = {
    "expected_usage_frequency": "确认一下：是每天都用，还是每周几次？",
    "trigger_reason": "想确认下：主要是旧的坏了/确实需要，还是看到促销或被别人推荐？",
    "owned_alternatives": "你手上那个还能正常用吗？",
    "price": "价格我拿不准：你说的这个是单价，还是总共花的钱？",
    "monthly_budget_left": "预算我再确认下：本月还剩多少可自由支配的钱？",
}

CLARIFY_CHIPS: dict[str, list[str]] = {
    "expected_usage_frequency": ["每天都用", "每周几次"],
    "trigger_reason": ["旧的坏了/确实需要", "促销或被推荐"],
    "owned_alternatives": ["还能用", "不能用了"],
    "price": ["单价", "总共的钱"],
    "monthly_budget_left": ["3000 元左右", "1000 元左右"],
}

CLARIFY_FIELDS = tuple(CLARIFY_QUESTIONS)


def build_reply_plan(
    *,
    this_turn_fields: dict[str, Any],
    merged_fields: dict[str, Any],
    missing_fields: list[str],
    is_complete: bool,
    next_question_key: str | None,
    next_question: str | None,
    conflicts: list[dict[str, Any]] | None = None,
    skipped_field: str | None = None,
    skip_rejected_field: str | None = None,
    optional_asked: int = 0,
    max_optional_questions: int = 2,
    dialogue: dict[str, Any] | None = None,
    last_question: str | None = None,
    corrections: dict[str, Any] | None = None,
    previous_fields: dict[str, Any] | None = None,
    user_text: str = "",
    clarify_field: str | None = None,
    asked_fields: list[str] | None = None,
    include_welcome: bool = False,
    closing_sent: bool = False,
) -> dict[str, Any]:
    """生成结构化回复计划；`reply` 字段是可直接返回给用户的成品文案。"""
    ack = build_ack(this_turn_fields, merged_fields)
    # 纠正回显：本地路径也要说清“改成了什么”，不能只在模型文案路径生效。
    contradiction_note = build_contradiction_note(corrections or {}, previous_fields or {})
    if contradiction_note:
        ack = (contradiction_note + " " + ack).strip()
    if skipped_field:
        ack = (ack + " " + SKIP_ACK).strip()

    question = next_question
    chips = question_chips(next_question_key)
    optional = bool(is_complete and next_question_key in FIELD_LABELS)
    tone = "collecting"
    can_stop = bool(is_complete)

    if conflicts:
        question, chips, tone, optional = CONFLICT_QUESTION, [], "conflict", False
    elif clarify_field and clarify_field in CLARIFY_QUESTIONS:
        # 澄清优先于普通追问：值不可信时不猜，直接二选一确认（每字段最多一次、全局最多两轮）。
        question = CLARIFY_QUESTIONS[clarify_field]
        chips = list(CLARIFY_CHIPS.get(clarify_field, []))
        tone, optional = "clarifying", False
    elif skip_rejected_field:
        # 核心字段不允许跳过：换个说法再问一次，并允许给范围
        question = SKIP_REJECTED_QUESTION + natural_question(skip_rejected_field)
        chips = question_chips(skip_rejected_field)
        tone, optional = "collecting", False
    elif is_complete:
        tone = "ready"
        if optional and optional_asked >= max_optional_questions:
            # 熔断：可选追问最多两轮，之后只给结束邀请，不再纠缠
            question, chips, optional = None, [], False

    # 按目标字段判重（用户要求 1）：同一字段只问一次——用户答不上来就换下一个缺失字段，
    # 绝不再换个说法重复问同一件事。
    # 真实事故：建案那轮问了「想更准的话，再补一句：你手上已经有能替代它的东西吗？」，
    # 下一轮又问「你手上已经有能替代它的东西吗？」（前缀不同、字面不同 → 旧的复读防护看不见）。
    # 适用范围（用户要求 2）：**增强字段永远判重**（信息没齐时也一样）；
    # 核心字段（product_name/price/monthly_budget_left）在信息未齐时不判重——它们问不到就出不了
    # 判决书，必须继续问，否则收集会静默卡死。澄清/冲突/跳过重申也不参与判重（各有自己的上限）。
    already_asked = {f for f in (asked_fields or []) if isinstance(f, str)}
    target_is_enhanced = next_question_key in ENHANCED_FIELDS
    if question and (target_is_enhanced or is_complete) and not clarify_field and not conflicts and not skip_rejected_field:
        if next_question_key in already_asked:
            candidates = [f for f in missing_fields if f in FIELD_LABELS and f not in already_asked]
            if not is_complete:
                # 信息还没齐：优先补核心字段，核心字段都没缺才继续问没问过的增强字段
                core = [f for f in candidates if f not in ENHANCED_FIELDS]
                candidates = core or candidates
            replacement_field = candidates[0] if candidates else None
            if replacement_field:
                next_question_key = replacement_field
                question = (
                    optional_question(replacement_field) if is_complete
                    else natural_question(replacement_field)
                )
                chips = question_chips(replacement_field)
                optional = is_complete
            elif is_complete:
                # 可选字段都问过一遍了：不再提问，直接给结束邀请
                question, chips, optional = None, [], False
            # is_complete=False 且没有可换的字段：保留原问句（核心字段必须问到）

    # 复读防护（本地路径同样生效）：与上一轮完全相同的问题 → 换成另一个缺失字段的问题。
    # 注意：**目标字段必须跟着文案一起换**。旧实现只换文案不换 `next_question_key`，
    # 于是又造出一个"显示在问预算、记账却记成价格"的双来源（真实复现，与旧字段那个事故同类）。
    if question and last_question and _normalize_for_compare(question) == _normalize_for_compare(last_question):
        replacement: tuple[str, str] | None = None
        for field in missing_fields:
            if field not in FIELD_LABELS:
                continue
            candidate = optional_question(field) if (is_complete and field in ENHANCED_FIELDS) else natural_question(field)
            if _normalize_for_compare(candidate) != _normalize_for_compare(last_question):
                replacement = (field, candidate)
                break
        if replacement:
            next_question_key, question = replacement
            chips = question_chips(next_question_key)
            optional = bool(is_complete and next_question_key in ENHANCED_FIELDS)
        else:
            question, chips, optional = None, [], False

    # 收尾结束语（用户要求 3）：这一轮起不再追问、且案件已经可以出判决书时给一次；
    # `closing_sent` 由调用方按案件状态传入，避免用户每多说一句就重复刷同一句结束语。
    # （放在问题定稿之后算：上面的判重/复读防护也可能把问题去掉）
    closing_text = CLOSING_MESSAGE if (is_complete and not question and not closing_sent) else None

    if question:
        reply = (ack + " " + question).strip()
    elif is_complete:
        tail = closing_text or (READY_NUDGE if not ack else "")
        reply = (ack + (" " + tail if tail else "")).strip()
    else:
        reply = (ack + " 我在听，继续说说？").strip()

    # 本轮"允许模型发问"的目标集合（修复 1 的闸门）：
    # 只有系统确实还缺、且能承载答案的字段才允许被问；信息已齐或熔断已到时集合为空，
    # 模型再自创问题也不会被采纳（真实事故：字段全齐后模型仍连续 6 轮追问
    # "轻便还是力度""几天内到手"这类字段表以外的维度，答案落库即弃、下一轮再换说法问）。
    if tone == "clarifying" and clarify_field:
        askable_targets = {clarify_field}
    elif tone == "conflict":
        askable_targets = set()
    elif skip_rejected_field:
        askable_targets = {skip_rejected_field}
    elif question:
        askable_targets = {f for f in missing_fields if f in FIELD_LABELS}
        # 增强字段问过就不再允许（信息没齐也一样）；核心字段在信息未齐时仍可再问
        askable_targets -= {f for f in already_asked if f in ENHANCED_FIELDS}
        if is_complete:
            askable_targets -= already_asked
    else:
        askable_targets = set()

    # 这一轮实际问的是哪个字段（供"已问过"记账；澄清/歧义场景不是普通字段追问）
    if tone == "clarifying" and clarify_field in CLARIFY_QUESTIONS:
        asked_field = clarify_field
    elif tone == "conflict":
        asked_field = None
    elif skip_rejected_field:
        asked_field = skip_rejected_field
    elif question:
        asked_field = next_question_key
    else:
        asked_field = None

    # 收尾结束语（用户要求 3）：这一轮起不再追问、且案件已经可以出判决书时给一次；
    # `closing_sent` 由调用方按案件状态传入，避免用户每多说一句就重复刷同一句结束语。
    closing_text = CLOSING_MESSAGE if (is_complete and not question and not closing_sent) else None

    plan = {
        "ack": ack,
        "question": question,
        "chips": chips,
        "can_stop": can_stop,
        "optional": optional,
        "tone": tone,
        "clarifying": bool(clarify_field and clarify_field in CLARIFY_QUESTIONS),
        "clarify_field": clarify_field if clarify_field in CLARIFY_QUESTIONS else None,
        "reply": reply,
        "welcome": build_welcome(merged_fields.get("product_name")) if include_welcome else "",
        "closing": bool(closing_text),
        "closing_text": closing_text,
        "ask_field": asked_field,
        # 熔断计数口径（修复 2）：信息已齐之后，只要这一轮还在发问（澄清/冲突除外）就计数，
        # 不区分问题来自本地模板还是模型——否则模型的自由追问完全绕过"可选追问最多两轮"。
        "counts_toward_optional": bool(is_complete and question and tone not in {"clarifying", "conflict"}),
        "progress": {
            "known": [FIELD_LABELS.get(f, f) for f in FIELD_LABELS if f in merged_fields and merged_fields.get(f)],
            "missing": [FIELD_LABELS.get(f, f) for f in missing_fields],
        },
        "_missing_fields": list(missing_fields),
        # 必须是 list（要进 JSON 响应）；调用方内部会转成 set 做成员判断
        "_askable_targets": sorted(askable_targets),
    }
    return _apply_model_dialogue(
        plan,
        dialogue=dialogue,
        last_question=last_question,
        corrections=corrections or {},
        previous_fields=previous_fields or {},
        user_text=user_text,
    )


# ==================== 模型对话文案 + 本地护栏 ====================

# 这些措辞是"系统口吻"，一旦出现就丢弃模型文案、改用本地模板。
SYSTEM_TONE_BLACKLIST = (
    "为了进入", "购物法庭", "可以让判断更准", "请补充", "字段", "信息仍在收集中",
    "已记录", "系统检测", "参数", "槽位",
)


def _clean_model_text(text: Any, limit: int) -> str:
    if not isinstance(text, str):
        return ""
    cleaned = text.strip().replace("\n", " ")
    if not cleaned or any(bad in cleaned for bad in SYSTEM_TONE_BLACKLIST):
        return ""
    return cleaned[:limit]


def _first_question_only(text: str) -> str:
    """只保留第一个问句，避免模型一次问两三个问题。"""
    if "？" not in text:
        return text
    head, _, _ = text.partition("？")
    return (head + "？").strip()


def _normalize_for_compare(text: str) -> str:
    """复读比较用的规范化：忽略空白/标点，以及句首的衔接词。

    真实复现（猫粮案）：上一轮问"这次是想给自家猫囤着吃，还是喂流浪猫呀？"，
    下一轮模型加了口语衔接词又问"**那**这次是想给自家猫囤着吃，还是喂流浪猫呀？"，
    逐字符比较判不出复读，于是同一句话连着问了两遍。衔接词不改变问题内容，这里统一剥掉。
    """
    normalized = "".join(ch for ch in (text or "") if ch not in " \t，。！？~、,.")
    for filler in _LEADING_FILLERS:
        if normalized.startswith(filler):
            return normalized[len(filler):]
    return normalized


# 顺序敏感："那么" 必须排在 "那" 前面
_LEADING_FILLERS = ("那么", "那", "然后", "所以", "另外", "还有", "嗯", "再就是")


def render_value_bare(field: str, value: Any) -> str:
    """只渲染值本身（不带字段名），用于"已改成…"这类句子，避免出现"价格已改成 价格 500 元"。"""
    if isinstance(value, float) and value.is_integer():
        text = str(int(value))
    else:
        text = str(value).strip()
    if field in {"price", "monthly_budget_left"}:
        return f"{text} 元"
    return text


def build_contradiction_note(new_fields: dict[str, Any], previous_fields: dict[str, Any]) -> str:
    """用户改了之前说过的信息时，明确告诉他改成什么。"""
    changes = []
    for field, new_value in new_fields.items():
        old_value = previous_fields.get(field)
        if old_value in (None, "", SKIPPED_VALUE) or new_value in (None, ""):
            continue
        if str(old_value) != str(new_value):
            changes.append(f"{FIELD_LABELS.get(field, field)}已改成 {render_value_bare(field, new_value)}")
    if not changes:
        return ""
    return "；".join(changes) + "。"


# 用户明确要求"别问了，直接分析"的信号（模型 intent=stop 且命中这些词才自动开审，防止误判）。
STOP_SIGNALS = (
    "直接分析", "直接出", "别问了", "不用问了", "够了", "可以了", "开始分析", "开审",
    "就这样", "差不多了", "出判决", "就这些",
)


def is_stop_signal(text: str) -> bool:
    cleaned = (text or "").strip()
    return bool(cleaned) and any(signal in cleaned for signal in STOP_SIGNALS)


def _apply_model_dialogue(
    plan: dict[str, Any],
    *,
    dialogue: dict[str, Any] | None,
    last_question: str | None,
    corrections: dict[str, Any],
    previous_fields: dict[str, Any],
    user_text: str = "",
) -> dict[str, Any]:
    """把模型写的对话文案合进计划，并用本地规则兜住五件事：

    1. 只问一个问题（截断多余问句）；
    2. 不复读上一轮的问题（重复就换回本地模板问句）；
    3. 不出现系统口吻（命中黑名单就丢弃该段文案）；
    4. 用户改了信息时明确回显"已改成…"；
    5. **追问不许跑偏**：模型只能问服务端这一轮允许问的字段（`ask_field` 必须落在
       `plan["_askable_targets"]` 里）；没声明目标、或目标已填/不在字段表内、或这一轮
       本来就没有可问的字段（信息已够 / 可选追问熔断已到）→ 一律丢弃模型问题，回落到本地问句。
    """
    if not dialogue:
        return plan

    ack = _clean_model_text(dialogue.get("ack"), 60) or plan["ack"]
    insight = _clean_model_text(dialogue.get("insight"), 80)
    answer_to_user = _clean_model_text(dialogue.get("answer_to_user"), 80)
    model_question = _clean_model_text(dialogue.get("question"), 80)
    model_ask_field = dialogue.get("ask_field")
    model_ask_field = model_ask_field.strip() if isinstance(model_ask_field, str) else ""
    chips = [c for c in (dialogue.get("chips") or []) if isinstance(c, str) and c.strip()][:3]

    askable = set(plan.get("_askable_targets") or set())
    off_target_reason = ""
    accepted_target = ""
    if model_question:
        model_question = _first_question_only(model_question)
        if plan.get("clarifying") or plan.get("tone") == "conflict":
            # 澄清/金额歧义属于"必须问清的事实"，不能被模型的自由提问顶掉。
            model_question = ""
            off_target_reason = "clarify_required"
        elif not askable:
            # 这一轮没有可问的字段（信息已齐且可选字段都问过 / 熔断已到）：不接受任何新问题，
            # 否则就是"凭模型自由发挥继续追问"。
            model_question = ""
            off_target_reason = "no_askable_field"
        elif model_ask_field in askable:
            accepted_target = model_ask_field
        elif not model_ask_field and len(askable) == 1:
            # 放宽（用户要求 2）：模型没声明目标、但这一轮只剩唯一可问字段 → 目标无歧义，采纳它的问法。
            accepted_target = next(iter(askable))
        else:
            # 声明了却指向已填/字段表以外的维度（或未声明但候选多于一个，无法验证）
            model_question = ""
            off_target_reason = f"ask_field_not_allowed:{model_ask_field or '<未声明>'}"
        if last_question and model_question and _normalize_for_compare(model_question) == _normalize_for_compare(last_question):
            model_question = ""      # 复读：丢弃，回落到本地模板问句
            off_target_reason = off_target_reason or "literal_repeat"
    question = model_question or plan["question"]
    if last_question and question and _normalize_for_compare(question) == _normalize_for_compare(last_question):
        # 模型与本地模板都可能复读：统一换成“另一个缺失字段”的问题；真的没有就不问。
        replacement = ""
        for field in (plan.get("_missing_fields") or []):
            candidate = natural_question(field)
            if _normalize_for_compare(candidate) != _normalize_for_compare(last_question):
                replacement = candidate
                break
        question = replacement or None

    parts = [p for p in (ack, insight, answer_to_user, question) if p]
    # 不再追问时补上收尾结束语（模型自己写了收尾语也不能顶掉这句确定性文案）
    closing_text = plan.get("closing_text")
    if closing_text and closing_text not in parts and not question:
        parts.append(closing_text)
    if not parts and plan["can_stop"]:
        parts = [closing_text or STOP_INVITE]

    plan.update({
        "ack": ack,
        "insight": insight,
        "answer_to_user": answer_to_user,
        "question": question,
        "chips": chips or plan["chips"],
        "intent": dialogue.get("intent", "provide_info"),
        "reply": " ".join(parts).strip() or plan["reply"],
        "model_text": bool(model_question or insight or answer_to_user),
        # 追问溯源：这一轮的问题最终来自模型还是本地模板，以及模型是否跑偏（供验收与调试）。
        "question_source": "model" if model_question else ("local" if question else "none"),
        "ask_field": accepted_target if model_question else plan.get("ask_field"),
        "off_target_question": off_target_reason or None,
    })
    # 只有"模型判定 stop"且"用户这句话确实带停止信号"时才自动开审，避免误判打断收集。
    plan["stop_requested"] = bool(
        plan["intent"] == "stop" and is_stop_signal(user_text) and plan["can_stop"]
    )
    return plan