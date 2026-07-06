from __future__ import annotations

import json
import math
import os
from typing import Any
from urllib.request import Request, urlopen


DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-v4-pro"
DEEPSEEK_TIMEOUT_SECONDS = 5


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


class DeepSeekLLMClient:
    """DeepSeek 真实 LLM 客户端，对外保持 complete_json 调用方式不变。"""

    def __init__(
        self,
        api_key: str,
        base_url: str = DEEPSEEK_BASE_URL,
        model: str = DEEPSEEK_MODEL,
        timeout_seconds: int = DEEPSEEK_TIMEOUT_SECONDS,
        fallback_client: MockLLMClient | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds
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


def _build_system_prompt(task: str) -> str:
    # pro/con 的角色不同，但输出契约完全一致，便于 AgentStep 继续复用。
    role_text = {
        "pro_agent": "你是购物法庭的正方 Agent，只分析支持购买的理由，不做最终裁决。",
        "con_agent": "你是购物法庭的反方 Agent，只分析风险、成本和替代方案，不做最终裁决。",
    }.get(task, "你是 DecisionJury 的辅助分析 Agent。")

    return (
        f"{role_text}\n"
        "你必须只输出一个 JSON 对象，不能输出 Markdown 代码块，不能输出额外解释。\n"
        "输出必须使用简体中文。\n"
        "JSON 字段只能包含 summary、arguments、confidence。\n"
        "summary 必须是字符串。\n"
        "arguments 必须是字符串数组。\n"
        "confidence 必须是 0 到 1 之间的数字。\n"
        "如果 RAG 证据为空，不得编造历史证据。\n"
        "如果 MCP 工具结果包含失败项，必须在分析中说明不确定性。"
    )


def _build_user_prompt(task: str, payload: dict[str, Any]) -> str:
    # 将结构化上下文直接交给模型，减少提示词中写死演示案例的风险。
    prompt_payload = {
        "task": task,
        "case_info": payload.get("collected_fields", {}),
        "rag_evidence": payload.get("rag_evidence", []),
        "tool_results": payload.get("tool_results", []),
        "required_output": {
            "summary": "string",
            "arguments": ["string"],
            "confidence": "number",
        },
    }
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
