from __future__ import annotations

import json
from typing import Any

from backend.app.services import llm_client


def sample_payload() -> dict[str, Any]:
    return {
        "collected_fields": {
            "product_name": "降噪耳机",
            "purpose": "学习",
            "expected_usage_frequency": "每天",
            "owned_alternatives": "普通耳机",
            "trigger_reason": "刚需",
        },
        "rag_evidence": [],
        "tool_results": [],
    }


def test_no_deepseek_api_key_uses_mock(monkeypatch: Any) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    client = llm_client.get_llm_client()
    response = client.complete_json("pro_agent", sample_payload())

    assert isinstance(client, llm_client.MockLLMClient)
    assert response["summary"]
    assert isinstance(response["arguments"], list)
    assert isinstance(response["confidence"], float)


def test_get_llm_client_uses_deepseek_when_key_exists(monkeypatch: Any) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

    client = llm_client.get_llm_client()

    assert isinstance(client, llm_client.DeepSeekLLMClient)
    assert client.model == "deepseek-v4-pro"
    assert client.base_url == "https://api.deepseek.com"


def test_api_exception_falls_back_to_mock(monkeypatch: Any) -> None:
    client = llm_client.DeepSeekLLMClient(api_key="test-key")

    def raise_error(task: str, payload: dict[str, Any]) -> str:
        raise RuntimeError("network down")

    monkeypatch.setattr(client, "_request_completion", raise_error)

    response = client.complete_json("con_agent", sample_payload())

    assert response["summary"].startswith("降噪耳机")
    assert isinstance(response["arguments"], list)
    assert response["confidence"] == 0.78


def test_api_timeout_falls_back_to_mock(monkeypatch: Any) -> None:
    client = llm_client.DeepSeekLLMClient(api_key="test-key")

    def raise_timeout(task: str, payload: dict[str, Any]) -> str:
        raise TimeoutError("request timed out")

    monkeypatch.setattr(client, "_request_completion", raise_timeout)

    response = client.complete_json("pro_agent", sample_payload())

    assert "降噪耳机" in response["summary"]
    assert response["confidence"] == 0.7


def test_non_json_response_falls_back_to_mock(monkeypatch: Any) -> None:
    client = llm_client.DeepSeekLLMClient(api_key="test-key")
    monkeypatch.setattr(client, "_request_completion", lambda task, payload: "not json")

    response = client.complete_json("pro_agent", sample_payload())

    assert "降噪耳机" in response["summary"]
    assert response["confidence"] == 0.7


def test_missing_summary_falls_back_to_mock(monkeypatch: Any) -> None:
    client = llm_client.DeepSeekLLMClient(api_key="test-key")
    raw = json.dumps({"arguments": ["理由"], "confidence": 0.6}, ensure_ascii=False)
    monkeypatch.setattr(client, "_request_completion", lambda task, payload: raw)

    response = client.complete_json("pro_agent", sample_payload())

    assert "降噪耳机" in response["summary"]
    assert response["confidence"] == 0.7


def test_missing_arguments_falls_back_to_mock(monkeypatch: Any) -> None:
    client = llm_client.DeepSeekLLMClient(api_key="test-key")
    raw = json.dumps({"summary": "摘要", "confidence": 0.6}, ensure_ascii=False)
    monkeypatch.setattr(client, "_request_completion", lambda task, payload: raw)

    response = client.complete_json("con_agent", sample_payload())

    assert response["confidence"] == 0.78
    assert isinstance(response["arguments"], list)


def test_missing_confidence_falls_back_to_mock(monkeypatch: Any) -> None:
    client = llm_client.DeepSeekLLMClient(api_key="test-key")
    raw = json.dumps({"summary": "摘要", "arguments": ["理由"]}, ensure_ascii=False)
    monkeypatch.setattr(client, "_request_completion", lambda task, payload: raw)

    response = client.complete_json("pro_agent", sample_payload())

    assert response["confidence"] == 0.7


def test_arguments_not_list_falls_back_to_mock(monkeypatch: Any) -> None:
    client = llm_client.DeepSeekLLMClient(api_key="test-key")
    raw = json.dumps({"summary": "摘要", "arguments": "理由", "confidence": 0.6}, ensure_ascii=False)
    monkeypatch.setattr(client, "_request_completion", lambda task, payload: raw)

    response = client.complete_json("con_agent", sample_payload())

    assert isinstance(response["arguments"], list)
    assert response["confidence"] == 0.78


def test_invalid_confidence_falls_back_to_mock(monkeypatch: Any) -> None:
    client = llm_client.DeepSeekLLMClient(api_key="test-key")
    raw = json.dumps({"summary": "摘要", "arguments": ["理由"], "confidence": "bad"}, ensure_ascii=False)
    monkeypatch.setattr(client, "_request_completion", lambda task, payload: raw)

    response = client.complete_json("pro_agent", sample_payload())

    assert response["confidence"] == 0.7


def test_valid_json_response_is_parsed(monkeypatch: Any) -> None:
    client = llm_client.DeepSeekLLMClient(api_key="test-key")
    raw = json.dumps(
        {
            "summary": "这是 DeepSeek 返回的结构化摘要。",
            "arguments": ["理由一", "理由二"],
            "confidence": "0.82",
        },
        ensure_ascii=False,
    )
    monkeypatch.setattr(client, "_request_completion", lambda task, payload: raw)

    response = client.complete_json("pro_agent", sample_payload())

    assert response == {
        "summary": "这是 DeepSeek 返回的结构化摘要。",
        "arguments": ["理由一", "理由二"],
        "confidence": 0.82,
    }


def test_request_body_uses_fixed_deepseek_v4_pro_model(monkeypatch: Any) -> None:
    captured: dict[str, Any] = {}

    class FakeResponse:
        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, *args: Any) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps(
                {
                    "choices": [
                        {
                            "message": {
                                "content": "{\"summary\":\"ok\",\"arguments\":[\"a\"],\"confidence\":0.5}"
                            }
                        }
                    ]
                }
            ).encode("utf-8")

    def fake_urlopen(request: Any, timeout: int) -> FakeResponse:
        captured["timeout"] = timeout
        captured["body"] = json.loads(request.data.decode("utf-8"))
        captured["authorization"] = request.headers["Authorization"]
        return FakeResponse()

    monkeypatch.setattr(llm_client, "urlopen", fake_urlopen)

    client = llm_client.DeepSeekLLMClient(api_key="test-key")
    raw = client._request_completion("pro_agent", sample_payload())

    assert json.loads(raw) == {"summary": "ok", "arguments": ["a"], "confidence": 0.5}
    assert captured["body"]["model"] == "deepseek-v4-pro"
    assert captured["timeout"] == 5
    assert captured["authorization"] == "Bearer test-key"


def test_prompt_contains_output_constraints() -> None:
    prompt = llm_client._build_system_prompt("pro_agent")

    assert "只输出一个 JSON 对象" in prompt
    assert "不能输出 Markdown 代码块" in prompt
    assert "输出必须使用简体中文" in prompt
    assert "如果 RAG 证据为空，不得编造历史证据" in prompt


def test_user_prompt_keeps_rag_and_failed_tool_details() -> None:
    payload = sample_payload()
    payload["rag_evidence"] = [
        {
            "id": "history_001",
            "title": "历史闲置记录",
            "content": "用户曾购买同类电子产品后闲置。",
            "tags": ["idle", "regret"],
        }
    ]
    payload["tool_results"] = [
        {
            "tool_name": "cooling_reminder",
            "status": "failed",
            "summary": "冷静期提醒创建失败。",
            "risk_level": None,
            "metrics": {},
            "error": "REMINDER_CREATE_FAILED",
        }
    ]

    prompt = llm_client._build_user_prompt("con_agent", payload)
    prompt_data = json.loads(prompt)

    assert prompt_data["rag_evidence"][0]["content"] == "用户曾购买同类电子产品后闲置。"
    assert prompt_data["tool_results"][0]["status"] == "failed"
    assert prompt_data["tool_results"][0]["error"] == "REMINDER_CREATE_FAILED"
