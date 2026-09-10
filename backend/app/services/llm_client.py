from __future__ import annotations

import json
import math
import os
import re
from typing import Any
from urllib.request import Request, urlopen


DEEPSEEK_BASE_URL = "https://api.deepseek.com"
# 官方在售模型名为 deepseek-flash（DeepSeek-V4.1-Flash）；旧名 deepseek-v4-flash 已下线，
# 仍可调用但会被路由到 V4.1-Flash。这里允许用环境变量覆盖，避免硬编码过时模型名。
DEFAULT_DEEPSEEK_MODEL = "deepseek-flash"
DEEPSEEK_MODEL = DEFAULT_DEEPSEEK_MODEL
DEEPSEEK_TIMEOUT_SECONDS = 30

# 任务分组（依据官方《思考模式》文档：思考模式默认开启，且思维链 token 计入输出额度）：
#   - 收集阶段（字段抽取 + 对话文案）：关思考，实测同一请求 3.96s -> 1.52s，且 JSON 稳定；
#   - 辩论/判决阶段：开启思考并给足输出额度，保证论证质量。
COLLECTION_TASKS = {"input_parser"}
DEBATE_TASKS = {"pro_agent", "con_agent", "judge_agent"}
VALID_REASONING_EFFORTS = {"minimal", "low", "medium", "high", "xhigh", "max", "ultra"}
DEFAULT_DEBATE_EFFORT = "max"
DEFAULT_DEBATE_TIMEOUT_SECONDS = 120
DEFAULT_DEBATE_MAX_TOKENS = 8192


class MockLLMClient:
    """无 API Key 或真实 API 不可用时使用的确定性 mock。"""

    def complete_json(self, task: str, payload: dict[str, Any]) -> dict[str, Any]:
        if task == "pro_agent":
            fields = payload["collected_fields"]
            product = fields.get("product_name", "该商品")
            purpose = fields.get("purpose", "当前目标")
            frequency = fields.get("expected_usage_frequency", "有一定频率")
            return {
                "summary": f"{product}与“{purpose}”相关，若使用频率为{frequency}，具备一定购买价值。",
                "arguments": [
                    f"购买目的较明确：{purpose}",
                    f"预期使用频率为{frequency}，可能支撑长期价值",
                    "如果已有替代品不能解决当前问题，新增商品有一定合理性",
                ],
                "confidence": 0.7,
            }
        if task == "con_agent":
            fields = payload["collected_fields"]
            product = fields.get("product_name", "该商品")
            alternatives = fields.get("owned_alternatives", "未说明")
            trigger = fields.get("trigger_reason", "未说明")
            return {
                "summary": f"{product}仍有预算压力、闲置和冲动消费风险，需要谨慎。",
                "arguments": [
                    f"已有替代情况：{alternatives}",
                    f"购买触发因素：{trigger}",
                    "应先确认现有物品是否已经足够覆盖核心需求",
                ],
                "confidence": 0.78,
            }
        return {
            "summary": "mock LLM returned no task-specific content",
            "arguments": [],
            "confidence": 0.5,
        }

    def complete_parser_json(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Mock 客户端不访问网络，input_parser 由本地规则负责 fallback。"""
        raise RuntimeError("input parser LLM is not configured")


class DeepSeekLLMClient:
    """DeepSeek 真实 LLM 客户端，对外保持 complete_json 调用方式不变。"""

    def __init__(
        self,
        api_key: str,
        base_url: str = DEEPSEEK_BASE_URL,
        model: str | None = None,
        timeout_seconds: int | None = None,
        fallback_client: MockLLMClient | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        # 不硬编码模型名：默认读 DEEPSEEK_MODEL，回退官方在售的 deepseek-flash。
        self.model = model or _get_model()
        self.timeout_seconds = timeout_seconds if timeout_seconds is not None else _get_timeout_seconds()
        self.fallback_client = fallback_client or MockLLMClient()

    def complete_json(self, task: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            # complete_json 是 Agent 层唯一入口；这里负责把远程响应压成稳定三字段结构。
            raw_content = self._request_completion(task, payload)
            parsed = json.loads(raw_content)
            return _validate_llm_result(parsed)
        except Exception:
            # 真实 API 的任何失败都不能影响 Agent 主流程，统一回退到 mock。
            return self.fallback_client.complete_json(task, payload)

    def complete_parser_json(self, payload: dict[str, Any]) -> dict[str, Any]:
        """请求并校验 input_parser 专用 JSON；失败交由 parser 回退本地规则。"""
        raw_content = self._request_completion("input_parser", payload)
        parsed = json.loads(raw_content)
        return _validate_parser_result(parsed)

    def _request_completion(self, task: str, payload: dict[str, Any]) -> str:
        # 使用 DeepSeek OpenAI-compatible chat/completions 接口，不额外引入 SDK 依赖。
        request_body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": _build_system_prompt(task)},
                {"role": "user", "content": _build_user_prompt(task, payload)},
            ],
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }
        if task in COLLECTION_TASKS:
            # 收集阶段关闭思考模式：官方文档说明思考默认开启且 effort 默认 high，
            # 关闭后实测延迟 3.96s -> 1.52s，JSON 合法率 4/4；同时 temperature 才真正生效
            # （思考模式不支持 temperature，设置不报错但不生效）。
            request_body["thinking"] = {"type": "disabled"}
        else:
            # 辩论/判决阶段保留思考并给出强度；思维链 token 计入输出额度，因此显式放大 max_tokens。
            request_body["reasoning_effort"] = _get_reasoning_effort(task)
            request_body["max_tokens"] = _get_max_tokens(task)
        request = Request(
            url=f"{self.base_url}/chat/completions",
            data=json.dumps(request_body, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        with urlopen(request, timeout=self._timeout_for(task)) as response:
            response_data = json.loads(response.read().decode("utf-8"))

        return response_data["choices"][0]["message"]["content"]

    def _timeout_for(self, task: str) -> int:
        """收集阶段用常规超时；开启思考的辩论阶段需要更长超时。"""
        if task in DEBATE_TASKS:
            return _get_debate_timeout_seconds()
        return self.timeout_seconds


def get_llm_client() -> MockLLMClient | DeepSeekLLMClient:
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        # 本地演示和 CI 默认没有密钥，必须稳定走 mock。
        return MockLLMClient()
    return DeepSeekLLMClient(api_key=api_key)


def _get_timeout_seconds() -> int:
    """读取真实 API timeout；非法或过小配置回退到 30 秒默认值。"""
    raw_timeout = os.getenv("DEEPSEEK_TIMEOUT_SECONDS")
    if raw_timeout is None:
        return DEEPSEEK_TIMEOUT_SECONDS
    try:
        timeout = int(raw_timeout)
    except ValueError:
        return DEEPSEEK_TIMEOUT_SECONDS
    return timeout if 1 <= timeout <= 120 else DEEPSEEK_TIMEOUT_SECONDS


def _get_model() -> str:
    """模型名可用 DEEPSEEK_MODEL 覆盖；空值回退官方在售的 deepseek-flash。"""
    return (os.getenv("DEEPSEEK_MODEL") or "").strip() or DEFAULT_DEEPSEEK_MODEL


def _get_reasoning_effort(task: str) -> str:
    """辩论/判决阶段的思考强度，默认 max，可被 DEEPSEEK_REASONING_EFFORT 覆盖。"""
    raw = (os.getenv("DEEPSEEK_REASONING_EFFORT") or "").strip().lower()
    if task in DEBATE_TASKS and raw in VALID_REASONING_EFFORTS:
        return raw
    return DEFAULT_DEBATE_EFFORT


def _get_debate_timeout_seconds() -> int:
    """开启思考后单次调用可能超过 30 秒，辩论阶段默认放宽到 120 秒。"""
    raw = os.getenv("DEEPSEEK_DEBATE_TIMEOUT_SECONDS")
    try:
        value = int(raw) if raw is not None else DEFAULT_DEBATE_TIMEOUT_SECONDS
    except ValueError:
        value = DEFAULT_DEBATE_TIMEOUT_SECONDS
    return value if 30 <= value <= 600 else DEFAULT_DEBATE_TIMEOUT_SECONDS


def _get_max_tokens(task: str) -> int:
    """思维链 token 计入输出额度，思考模式下必须给足，避免 JSON 被截断。"""
    raw = os.getenv("DEEPSEEK_MAX_TOKENS")
    try:
        value = int(raw) if raw is not None else DEFAULT_DEBATE_MAX_TOKENS
    except ValueError:
        value = DEFAULT_DEBATE_MAX_TOKENS
    return value if 512 <= value <= 65536 else DEFAULT_DEBATE_MAX_TOKENS


def _build_system_prompt(task: str) -> str:
    # pro/con 的角色不同，但输出契约完全一致，便于 AgentStep 继续复用。
    role_text = {
        "input_parser": "你是 DecisionJury 的购物输入解析 Agent，负责理解用户自然语言并提取已明确表达的信息。",
        "pro_agent": "你是购物法庭的正方 Agent，只分析支持购买的理由，不做最终裁决。",
        "con_agent": "你是购物法庭的反方 Agent，只分析风险、成本和替代方案，不做最终裁决。",
        "judge_agent": "你是购物法庭的法官说明 Agent，负责解释应用规则已经确定的判决结果。",
    }.get(task, "你是 DecisionJury 的辅助分析 Agent。")

    if task == "input_parser":
        return (
            f"{role_text}\n"
            "你必须只输出一个 JSON 对象，不能输出 Markdown 代码块，不能输出额外解释。\n"
            "字段名必须使用英文 snake_case，用户展示文字必须使用简体中文。\n"
            "只要用户表达的是购买或使用某个商品或服务，就将其作为 shopping 案件解析；高风险主题仅作为 is_high_risk 元数据记录，不得因此拒绝或停止解析。\n"
            "允许字段：product_name、price、purpose、monthly_budget_left、owned_alternatives、"
            "expected_usage_frequency、trigger_reason。\n"
            "预算金额和商品价格必须区分；只有明确的纠正表达才允许覆盖已有字段。\n"
            "价格线索包括价格、售价、花、买下来；预算线索包括本月、每月、预算、可支配、余额、还剩。\n"
            "支持元、块、大洋、人民币及中文口语数字；带单位的金额（如“5元一斤”“5元/斤”）也要提取数值。\n"
            "无法判断多个金额归属时保留 conflicts 候选，不要猜测；不确定的字段宁可不填，也不要编造。\n"
            "否定与条件句要按语义处理：用户说“我不是每天用”“暂时不买”“如果降价再考虑”，"
            "不要当成肯定表达填进字段；能确认的写成对应字段，不能确认的留空。\n"
            "若用户提到了已有的同类物品，请额外给出顶层字段 alternative_covers_need："
            "true 表示这个已有物品能覆盖用户的核心需求，false 表示覆盖不了，拿不准就给 null。\n"
            "【受控值优先】以下字段请直接给受控值，不要在中文自由文本里表达：\n"
            "- frequency_canonical：daily / weekly_3plus / weekly_1_2 / monthly / occasional / unknown\n"
            "- trigger_canonical：need / promotion / recommendation / emotion / unknown\n"
            "给出上面两个受控值时，必须同时给出 frequency_evidence / trigger_evidence："
            "**直接引用用户原话里的片段**（如“一周用两三次”“种草很久了”）；"
            "如果找不到可引用的原话片段，就把受控值设为 unknown，不要凭印象给值。\n"
            "【证据契约】另请给出顶层字段 evidence：{字段名: 用户原话片段}，覆盖你本轮填的每个字段。"
            "服务端会逐条核对片段是否真的出现在用户原话里；**核对不通过的字段会被直接丢弃**，"
            "所以引用不出原话的字段请干脆不要填（宁可留空，也不要编造）。\n"
            "- price_basis：unit（给出的是单价，如“5元/斤”）或 total（给出的是总价）\n"
            "- price_unit：单价单位（斤/个/寸/升…），非单价给 null；quantity：数量，未知给 null\n"
            "\n【对话身份】你不是表单机器人，而是一个耐心的购物参谋。用户每一轮都要得到三样东西："
            "你听懂了什么、一句有价值的回应、以及**最多一个问题**。\n"
            "dialogue 对象（必填）：\n"
            "- ack：用你自己的话承接用户刚说的内容，≤30 字，**不要罗列字段名**，不要用“已记录”这类系统口吻。"
            "用户这轮修正了之前的信息时，要明确说“已改成…”。\n"
            "- insight：可选的一句有价值回应（提示风险、给参考、共情），≤40 字；没有就给空字符串。\n"
            "- question：**只问一个问题**，口语化、像朋友聊天；如果是核心信息已齐后的可选补充，"
            "在句尾加“（可选）”；不要复读 last_question 或已知信息。\n"
            "- chips：0~3 个快捷回答选项，仅当这个问题有明确枚举答案时给（例如频率、用途、有没有替代品）。\n"
            "- answer_to_user：用户在这轮反问你时，先用一句话回答，再问你的问题；否则空字符串。\n"
            "- intent：provide_info / correct / ask_back / chitchat / skip / stop 之一"
            "（用户说“不知道/跳过”用 skip；说“够了/直接分析/别问了”用 stop）。\n"
            "\n【使用上下文】必须承接本轮用户的话；不得重复询问 existing_collected_fields 里已有的信息；"
            "最近几轮对话与上一轮的问题在 recent_turns / last_question 中，不要原样重复提问。\n"
            "返回字段应包含 case_type、is_supported、is_high_risk、reject_reason、extracted_fields、"
            "correction_fields、confidence、dialogue；next_question 保留为兼容字段，可与 dialogue.question 相同。"
        )

    return (
        f"{role_text}\n"
        "你必须只输出一个 JSON 对象，不能输出 Markdown 代码块，不能输出额外解释。\n"
        "输出必须使用简体中文。\n"
        "JSON 字段只能包含 summary、arguments、confidence。\n"
        "summary 必须是字符串。\n"
        "arguments 必须是字符串数组。\n"
        "confidence 必须是 0 到 1 之间的数字。\n"
        "如果 RAG 证据为空，不得编造历史证据。\n"
        "如果 MCP 工具结果包含失败项，必须在分析中说明不确定性。\n"
        + (
            "final_decision 由应用规则决定，你只能解释该结果，不能改写或替换它。\n"
            "必须同时参考正方、反方、RAG 和 MCP 结果，不得编造不存在的证据。"
            if task == "judge_agent"
            else ""
        )
    )


def _build_user_prompt(task: str, payload: dict[str, Any]) -> str:
    # 将结构化上下文直接交给模型，减少提示词中写死演示案例的风险。
    prompt_payload = {
        "task": task,
        "current_message": payload.get("current_message", ""),
        "case_info": payload.get("collected_fields", {}),
        "existing_collected_fields": payload.get("existing_collected_fields", payload.get("collected_fields", {})),
        "existing_missing_fields": payload.get("existing_missing_fields", []),
        "rag_evidence": payload.get("rag_evidence", []),
        "tool_results": payload.get("tool_results", []),
        "required_output": (
            {
                "case_type": "shopping or null",
                "is_supported": "boolean",
                "is_high_risk": "boolean",
                "reject_reason": "string or null",
                "extracted_fields": "object with allowed shopping fields only",
                "correction_fields": "object with allowed shopping fields only",
                "next_question": "string or null",
                "alternative_covers_need": "boolean or null（用户已有同类物品时：能否覆盖核心需求；没有提到就给 null）",
                "evidence": "object：{字段名: 用户原话片段}，覆盖本轮填写的每个字段；"
                            "没有原话依据的字段不要填（服务端会核对，不通过就丢弃该字段）",
                "frequency_canonical": "daily|weekly_3plus|weekly_1_2|monthly|occasional|unknown",
                "trigger_canonical": "need|promotion|recommendation|emotion|unknown",
                "frequency_evidence": "string（引用用户原话片段；找不到就给空串）",
                "trigger_evidence": "string（引用用户原话片段；找不到就给空串）",
                "price_basis": "unit 或 total",
                "price_unit": "string or null（单价单位）",
                "quantity": "number or null",
                "dialogue": {
                    "ack": "string，承接用户刚说的话，≤30 字",
                    "insight": "string，可选的一句有价值回应，没有则空串",
                    "question": "string，只问一个问题；可选补充时以（可选）结尾",
                    "chips": ["string，0~3 个快捷选项"],
                    "answer_to_user": "string，用户反问时的简短回答，否则空串",
                    "intent": "provide_info|correct|ask_back|chitchat|skip|stop",
                },
                "confidence": "number from 0 to 1",
            }
            if task == "input_parser"
            else {
                "summary": "string",
                "arguments": ["string"],
                "confidence": "number",
            }
        ),
    }
    if task == "input_parser":
        prompt_payload.update(
            {
                "recent_turns": payload.get("recent_turns", []),
                "last_question": payload.get("last_question"),
                "already_asked_fields": payload.get("already_asked_fields", []),
            }
        )
    if task == "judge_agent":
        prompt_payload.update(
            {
                "final_decision": payload.get("final_decision"),
                "pro_agent_result": payload.get("pro_agent_result", {}),
                "con_agent_result": payload.get("con_agent_result", {}),
            }
        )
    return json.dumps(prompt_payload, ensure_ascii=False, indent=2)


def _validate_llm_result(value: Any) -> dict[str, Any]:
    # 这里集中做强校验，确保 Agent 层永远拿到 summary/arguments/confidence 三个稳定字段。
    if not isinstance(value, dict):
        raise ValueError("LLM result is not an object")

    summary = value.get("summary")
    arguments = value.get("arguments")
    confidence = value.get("confidence")

    if not isinstance(summary, str) or not summary.strip():
        raise ValueError("LLM result missing summary")
    if not isinstance(arguments, list) or not all(isinstance(item, str) for item in arguments):
        raise ValueError("LLM result arguments must be a string list")

    try:
        confidence_number = float(confidence)
    except (TypeError, ValueError) as exc:
        raise ValueError("LLM result confidence is not numeric") from exc

    if not math.isfinite(confidence_number):
        raise ValueError("LLM result confidence is not finite")

    return {
        "summary": summary,
        "arguments": arguments,
        "confidence": max(0.0, min(confidence_number, 1.0)),
    }


PARSER_FIELDS = {
    "product_name",
    "price",
    "purpose",
    "monthly_budget_left",
    "owned_alternatives",
    "expected_usage_frequency",
    "trigger_reason",
}

_CHINESE_DIGITS = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
                   "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
_CHINESE_UNITS = {"十": 10, "百": 100, "千": 1000, "万": 10000, "亿": 100000000}


def _coerce_amount(raw: Any) -> float | None:
    """把模型返回的金额宽松解析成非负数字。

    模型经常返回带单位或口语写法的字符串：`"5元/斤"`、`"约1000元"`、`"¥1299"`、
    `"1,299 元"`、`"一千二"`。旧实现直接 `float()`，任意一种都会抛错并让整轮解析
    作废（静默降级到本地正则）。这里做“宽进”：抽不到数字才返回 None，由调用方
    丢弃该字段而不是丢弃整轮结果。

    注意：`"5元/斤"` 属于单价，这里只保留数值 5，原始写法记录在 `field_meta.raw_text`；
    当前报告与成本工具仍按“该数值”参与占比计算，单价/总价的区分未在本轮实现。
    """
    if isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)):
        value = float(raw)
        return value if math.isfinite(value) and value >= 0 else None
    if not isinstance(raw, str):
        return None

    text = raw.strip()
    if not text:
        return None

    # 阿拉伯数字（兼容 1,299 / 1299.5 / ¥1299 / 5元一斤 / 3000元左右）
    match = re.search(r"\d[\d,]*(?:\.\d+)?", text)
    if match:
        try:
            value = float(match.group(0).replace(",", ""))
        except ValueError:
            return None
        return value if math.isfinite(value) and value >= 0 else None

    # 中文数字（兼容 一千二 / 三千 / 两千五 / 一万）
    chinese = re.sub(r"[^零〇一二两三四五六七八九十百千万亿]", "", text)
    if not chinese:
        return None
    if chinese in _CHINESE_DIGITS:
        return float(_CHINESE_DIGITS[chinese])
    shorthand = re.fullmatch(r"([一二三四五六七八九])千([一二三四五六七八九])", chinese)
    if shorthand:
        return float(_CHINESE_DIGITS[shorthand.group(1)] * 1000 + _CHINESE_DIGITS[shorthand.group(2)] * 100)
    shorthand = re.fullmatch(r"([一二三四五六七八九])百([一二三四五六七八九])", chinese)
    if shorthand:
        return float(_CHINESE_DIGITS[shorthand.group(1)] * 100 + _CHINESE_DIGITS[shorthand.group(2)] * 10)

    total = section = number = 0
    for char in chinese:
        if char in _CHINESE_DIGITS:
            number = _CHINESE_DIGITS[char]
        elif char in _CHINESE_UNITS:
            unit = _CHINESE_UNITS[char]
            if unit >= 10000:
                section = (section + number) * unit
                total += section
                section = 0
            else:
                section += (number or 1) * unit
            number = 0
    value = float(total + section + number)
    return value if math.isfinite(value) and value >= 0 else None


def _sanitize_dialogue(raw: Any) -> dict[str, Any] | None:
    """校验并裁剪模型给出的对话计划；不合法时返回 None，由本地模板接管。"""
    if not isinstance(raw, dict):
        return None

    def _text(key: str, limit: int) -> str:
        value = raw.get(key)
        return value.strip()[:limit] if isinstance(value, str) else ""

    chips = [c.strip()[:12] for c in (raw.get("chips") or []) if isinstance(c, str) and c.strip()][:3]
    intent = raw.get("intent")
    if intent not in DIALOGUE_INTENTS:
        intent = "provide_info"
    return {
        "ack": _text("ack", 60),
        "insight": _text("insight", 80),
        "question": _text("question", 80),
        "chips": chips,
        "answer_to_user": _text("answer_to_user", 80),
        "intent": intent,
    }


DIALOGUE_INTENTS = {"provide_info", "correct", "ask_back", "chitchat", "skip", "stop"}


def _validate_parser_result(value: Any) -> dict[str, Any]:
    """校验模型解析结果，避免未知字段或猜测值进入案件状态。"""
    if not isinstance(value, dict):
        raise ValueError("parser result is not an object")

    required_keys = {
        "case_type",
        "is_high_risk",
        "reject_reason",
        "extracted_fields",
        "correction_fields",
        "next_question",
        "confidence",
    }
    optional_keys = {
        "is_supported",
        "field_meta",
        "conflicts",
        "next_question_key",
        "is_complete",
        "termination_reason",
        "parser_used",
        "dialogue",
        "alternative_covers_need",
        "frequency_canonical",
        "trigger_canonical",
        "frequency_evidence",
        "trigger_evidence",
        "price_basis",
        "price_unit",
        "quantity",
        "evidence",
    }
    # 只要求"必需键齐全"：模型偶尔多带一个键（例如把 answer_to_user 放到顶层）不应该让
    # 整轮解析作废、静默降级到本地正则——那正是"用户说的信息被系统漏掉"的主因之一。
    if required_keys - set(value):
        raise ValueError("parser result misses required keys")

    if not isinstance(value["extracted_fields"], dict) or not isinstance(value["correction_fields"], dict):
        raise ValueError("parser fields must be objects")

    # 校验阶段在副本上做金额类型转换，避免调用方复用原始模型响应时遭遇隐式修改。
    extracted = dict(value["extracted_fields"])
    corrections = dict(value["correction_fields"])
    raw_text_notes: dict[str, str] = {}
    # 未知字段名同样只丢弃该字段，不放弃整轮（字段级降级）。
    dropped_fields = sorted((set(extracted) | set(corrections)) - PARSER_FIELDS)
    for name in dropped_fields:
        extracted.pop(name, None)
        corrections.pop(name, None)

    for field_name in ("price", "monthly_budget_left"):
        for fields in (extracted, corrections):
            if field_name in fields and fields[field_name] is not None:
                original = fields[field_name]
                numeric_value = _coerce_amount(original)
                if numeric_value is None:
                    # 字段级降级：单个金额无法解析时只丢弃该字段，保留本轮其余合法字段。
                    # 旧实现直接 raise，会让整轮模型结果作废并静默回退到本地正则，
                    # 表现为“只解析出预算、商品名和价格丢失”（见 docs/05_TestPlan.md §9.4）。
                    fields.pop(field_name, None)
                    continue
                if isinstance(original, str):
                    # 保留原始写法（如“5元/斤”“约1000元”），便于追溯与后续按单价/总价处理。
                    raw_text_notes[field_name] = original.strip()
                fields[field_name] = numeric_value

    if "is_supported" in value and not isinstance(value["is_supported"], bool):
        raise ValueError("is_supported must be boolean")
    if not isinstance(value["is_high_risk"], bool):
        raise ValueError("is_high_risk must be boolean")
    if value["case_type"] not in {"shopping", None}:
        raise ValueError("unsupported case_type")
    if value.get("is_supported") is True and value["case_type"] != "shopping":
        raise ValueError("supported parser result must have shopping case_type")
    if value["reject_reason"] is not None and not isinstance(value["reject_reason"], str):
        raise ValueError("reject_reason must be a string or null")
    if value["next_question"] is not None and not isinstance(value["next_question"], str):
        raise ValueError("next_question must be a string")
    if "field_meta" in value and not isinstance(value["field_meta"], dict):
        raise ValueError("field_meta must be an object")
    if "conflicts" in value and not isinstance(value["conflicts"], list):
        raise ValueError("conflicts must be a list")
    if "next_question_key" in value and value["next_question_key"] is not None:
        if not isinstance(value["next_question_key"], str):
            raise ValueError("next_question_key must be a string or null")
        if value["next_question_key"] != "price_or_budget" and value["next_question_key"] not in PARSER_FIELDS:
            raise ValueError("unknown next_question_key")
    if "is_complete" in value and not isinstance(value["is_complete"], bool):
        raise ValueError("is_complete must be boolean")
    if "termination_reason" in value and value["termination_reason"] is not None and not isinstance(value["termination_reason"], str):
        raise ValueError("termination_reason must be a string or null")
    if "parser_used" in value and value["parser_used"] is not None and not isinstance(value["parser_used"], str):
        raise ValueError("parser_used must be a string or null")

    try:
        confidence = float(value["confidence"])
    except (TypeError, ValueError) as exc:
        raise ValueError("parser confidence is not numeric") from exc
    if not math.isfinite(confidence) or not 0 <= confidence <= 1:
        raise ValueError("parser confidence must be finite and between 0 and 1")

    # 把宽松解析保留的原始写法合并进 field_meta（不改动调用方传入的 dict）。
    field_meta_out = dict(value.get("field_meta") or {})
    for field_name, raw_text in raw_text_notes.items():
        entry = dict(field_meta_out.get(field_name) or {})
        entry.setdefault("raw_text", raw_text)
        field_meta_out[field_name] = entry
    for name in dropped_fields:
        entry = dict(field_meta_out.get(name) or {})
        entry["dropped"] = "unknown_field"
        field_meta_out[name] = entry

    return {
        "case_type": value["case_type"],
        # supported 范围由结构化 case_type 和高风险判断确定，避免模型漏填可推导字段导致整次 fallback。
        "is_supported": value.get("is_supported", value["case_type"] == "shopping"),
        "is_high_risk": value["is_high_risk"],
        "reject_reason": value["reject_reason"],
        "extracted_fields": extracted,
        "correction_fields": corrections,
        "next_question": value["next_question"],
        "confidence": confidence,
        "field_meta": field_meta_out,
        "conflicts": list(value.get("conflicts") or []),
        "next_question_key": value.get("next_question_key"),
        "is_complete": value.get("is_complete"),
        "termination_reason": value.get("termination_reason"),
        "parser_used": value.get("parser_used"),
        "dialogue": _sanitize_dialogue(value.get("dialogue")),
        "alternative_covers_need": _as_optional_bool(value.get("alternative_covers_need")),
        "frequency_canonical": _as_controlled(value.get("frequency_canonical"), CONTROLLED_FREQUENCY),
        "trigger_canonical": _as_controlled(value.get("trigger_canonical"), CONTROLLED_TRIGGER),
        "frequency_evidence": _as_optional_text(value.get("frequency_evidence")),
        "trigger_evidence": _as_optional_text(value.get("trigger_evidence")),
        "price_basis": _as_controlled(value.get("price_basis"), {"unit", "total"}),
        "price_unit": _as_optional_text(value.get("price_unit")),
        "quantity": _as_optional_number(value.get("quantity")),
        "evidence": _as_evidence_map(value.get("evidence")),
    }


def _as_evidence_map(raw: Any) -> dict[str, str]:
    """证据映射：{字段名: 用户原话片段}；只接受本项目的字段名与短字符串。"""
    if not isinstance(raw, dict):
        return {}
    evidence: dict[str, str] = {}
    for key, item in raw.items():
        if key not in PARSER_FIELDS or not isinstance(item, str):
            continue
        text = item.strip()[:60]
        if text:
            evidence[key] = text
    return evidence


# 模型直接输出受控值时的白名单；不在表内一律按"未给"处理，由文本归一兜底。
CONTROLLED_FREQUENCY = {"daily", "weekly_3plus", "weekly_1_2", "monthly", "occasional", "unknown"}
CONTROLLED_TRIGGER = {"need", "promotion", "recommendation", "emotion", "unknown"}


def _as_controlled(value: Any, allowed: set[str]) -> str | None:
    return value if isinstance(value, str) and value in allowed else None


def _as_optional_text(value: Any) -> str | None:
    text = value.strip() if isinstance(value, str) else ""
    return text[:8] or None


def _as_optional_number(value: Any) -> float | None:
    if isinstance(value, bool) or value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


def _as_optional_bool(value: Any) -> bool | None:
    """替代品等效判断：只接受 true/false/null，其余一律按“未知”处理。"""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"true", "yes", "是", "能", "可以"}:
            return True
        if text in {"false", "no", "否", "不能", "不可以"}:
            return False
    return None
