from __future__ import annotations

import json
import math
import os
from typing import Any
from urllib.request import Request, urlopen


DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-v4-flash"
DEEPSEEK_TIMEOUT_SECONDS = 30


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
        model: str = DEEPSEEK_MODEL,
        timeout_seconds: int | None = None,
        fallback_client: MockLLMClient | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
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
        if task == "input_parser":
            # 字段抽取不需要深度推理，降低思考强度以缩短常规收集请求延迟。
            request_body["reasoning_effort"] = "low"
        request = Request(
            url=f"{self.base_url}/chat/completions",
            data=json.dumps(request_body, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        with urlopen(request, timeout=self.timeout_seconds) as response:
            response_data = json.loads(response.read().decode("utf-8"))

        return response_data["choices"][0]["message"]["content"]


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
            "如果字段缺失，请生成一句简短自然的 next_question，最多询问 2 到 3 个关键字段。\n"
            "返回字段应包含 case_type、is_supported、is_high_risk、reject_reason、extracted_fields、"
            "correction_fields、next_question、confidence；若遗漏 is_supported，应用会根据其他字段推导。"
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
    optional_keys = {"is_supported"}
    if set(value) - (required_keys | optional_keys) or required_keys - set(value):
        raise ValueError("parser result keys are incomplete or unknown")

    allowed_keys = {
        "case_type",
        "is_supported",
        "is_high_risk",
        "reject_reason",
        "extracted_fields",
        "correction_fields",
        "next_question",
        "confidence",
    }
    if set(value) - allowed_keys:
        raise ValueError("parser result contains unknown keys")

    if not isinstance(value["extracted_fields"], dict) or not isinstance(value["correction_fields"], dict):
        raise ValueError("parser fields must be objects")

    # 校验阶段在副本上做金额类型转换，避免调用方复用原始模型响应时遭遇隐式修改。
    extracted = dict(value["extracted_fields"])
    corrections = dict(value["correction_fields"])
    if set(extracted) - PARSER_FIELDS or set(corrections) - PARSER_FIELDS:
        raise ValueError("parser result contains unknown fields")

    for field_name in ("price", "monthly_budget_left"):
        for fields in (extracted, corrections):
            if field_name in fields and fields[field_name] is not None:
                if isinstance(fields[field_name], bool):
                    raise ValueError(f"{field_name} must not be boolean")
                try:
                    numeric_value = float(fields[field_name])
                except (TypeError, ValueError) as exc:
                    raise ValueError(f"{field_name} must be numeric") from exc
                if not math.isfinite(numeric_value) or numeric_value < 0:
                    raise ValueError(f"{field_name} must be finite and non-negative")
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

    try:
        confidence = float(value["confidence"])
    except (TypeError, ValueError) as exc:
        raise ValueError("parser confidence is not numeric") from exc
    if not math.isfinite(confidence) or not 0 <= confidence <= 1:
        raise ValueError("parser confidence must be finite and between 0 and 1")

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
    }
