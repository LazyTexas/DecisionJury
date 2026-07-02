from __future__ import annotations

import os
from typing import Any


class MockLLMClient:
    """Deterministic mock LLM used when no real provider is configured."""

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


def get_llm_client() -> MockLLMClient:
    # Reserved for future real provider selection. No API key is required for MVP demo.
    _ = os.getenv("OPENAI_API_KEY")
    return MockLLMClient()
