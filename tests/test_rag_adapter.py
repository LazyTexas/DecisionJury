from __future__ import annotations

import json
from typing import Any

import pytest

from backend.app.services import rag_adapter


class FakeHTTPResponse:
    def __init__(self, payload: dict[str, Any] | None = None, raw_content: bytes | None = None) -> None:
        self.payload = payload
        self.raw_content = raw_content

    def __enter__(self) -> "FakeHTTPResponse":
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        return None

    def read(self) -> bytes:
        if self.raw_content is not None:
            return self.raw_content
        return json.dumps(self.payload, ensure_ascii=False).encode("utf-8")


def fake_urlopen_with_payload(payload: dict[str, Any]):
    def _fake_urlopen(request: Any, timeout: int) -> FakeHTTPResponse:
        # adapter 负责把 C 的调用参数封装成 D 约定的 HTTP POST 请求；
        # 这里顺手校验 timeout，避免后续改动误把主流程拖成慢调用。
        assert timeout <= 3
        assert request.full_url == "http://rag.test/api/rag/search"
        return FakeHTTPResponse(payload)

    return _fake_urlopen


def sample_rag_success_payload() -> dict[str, Any]:
    return {
        "success": True,
        "data": {
            "results": [
                {
                    "id": "history_001",
                    "title": "历史闲置记录",
                    "content": "用户曾购买同类电子产品后闲置。",
                    "score": 0.82,
                    "source": "decision_history",
                    "case_type": "shopping",
                    "tags": ["electronics", "idle"],
                    "created_at": "2026-06-20T12:00:00+08:00",
                }
            ]
        },
        "message": "",
    }


def call_adapter(**kwargs: Any) -> list[Any]:
    return rag_adapter.search_rag_evidence(
        user_id="u001",
        case_id="case_001",
        case_type="shopping",
        query="降噪耳机 学习 电子产品 预算",
        top_k=3,
        search_url="http://rag.test/api/rag/search",
        **kwargs,
    )


def test_rag_http_success_is_converted_to_rag_evidence(monkeypatch: Any) -> None:
    monkeypatch.setattr(rag_adapter, "urlopen", fake_urlopen_with_payload(sample_rag_success_payload()))

    results = call_adapter()

    assert len(results) == 1
    assert results[0].id == "history_001"
    assert results[0].title == "历史闲置记录"
    assert results[0].content == "用户曾购买同类电子产品后闲置。"
    assert results[0].score == 0.82
    assert results[0].source == "decision_history"
    assert results[0].case_type == "shopping"
    assert results[0].tags == ["electronics", "idle"]


def test_rag_success_with_empty_results_returns_empty_list(monkeypatch: Any) -> None:
    payload = {"success": True, "data": {"results": []}, "message": ""}
    monkeypatch.setattr(rag_adapter, "urlopen", fake_urlopen_with_payload(payload))

    assert call_adapter() == []


def test_rag_business_error_returns_empty_list(monkeypatch: Any) -> None:
    payload = {"success": False, "data": {"results": []}, "message": "RAG_ERROR"}
    monkeypatch.setattr(rag_adapter, "urlopen", fake_urlopen_with_payload(payload))

    assert call_adapter() == []


def test_rag_connection_failure_returns_empty_list(monkeypatch: Any) -> None:
    def raise_connection_error(request: Any, timeout: int) -> FakeHTTPResponse:
        raise OSError("rag service unavailable")

    monkeypatch.setattr(rag_adapter, "urlopen", raise_connection_error)

    assert call_adapter() == []


def test_rag_missing_required_field_returns_empty_list(monkeypatch: Any) -> None:
    payload = sample_rag_success_payload()
    del payload["data"]["results"][0]["content"]
    monkeypatch.setattr(rag_adapter, "urlopen", fake_urlopen_with_payload(payload))

    assert call_adapter() == []


def test_default_url_request_method_and_body(monkeypatch: Any) -> None:
    captured: dict[str, Any] = {}

    def fake_urlopen(request: Any, timeout: int) -> FakeHTTPResponse:
        # 默认地址和 POST body 是 C-D 联调契约的一部分，必须由 adapter 统一封装。
        captured["url"] = request.full_url
        captured["method"] = request.get_method()
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return FakeHTTPResponse({"success": True, "data": {"results": []}, "message": ""})

    monkeypatch.delenv("RAG_SEARCH_URL", raising=False)
    monkeypatch.setattr(rag_adapter, "urlopen", fake_urlopen)

    results = rag_adapter.search_rag_evidence(
        user_id="u001",
        case_id="case_001",
        case_type="shopping",
        query="降噪耳机 学习",
        top_k=3,
    )

    assert results == []
    assert captured["url"] == rag_adapter.DEFAULT_RAG_SEARCH_URL
    assert captured["method"] == "POST"
    assert captured["body"] == {
        "user_id": "u001",
        "case_id": "case_001",
        "case_type": "shopping",
        "query": "降噪耳机 学习",
        "top_k": 3,
    }


def test_rag_search_url_env_override(monkeypatch: Any) -> None:
    captured: dict[str, str] = {}

    def fake_urlopen(request: Any, timeout: int) -> FakeHTTPResponse:
        captured["url"] = request.full_url
        return FakeHTTPResponse({"success": True, "data": {"results": []}, "message": ""})

    monkeypatch.setenv("RAG_SEARCH_URL", "http://rag.env/api/rag/search")
    monkeypatch.setattr(rag_adapter, "urlopen", fake_urlopen)

    assert rag_adapter.search_rag_evidence("u001", "case_001", "shopping", "query") == []
    assert captured["url"] == "http://rag.env/api/rag/search"


def test_non_json_response_falls_back_to_empty_list(monkeypatch: Any) -> None:
    monkeypatch.setattr(rag_adapter, "urlopen", lambda request, timeout: FakeHTTPResponse(raw_content=b"not json"))

    assert call_adapter() == []


def test_timeout_exception_falls_back_to_empty_list(monkeypatch: Any) -> None:
    def raise_timeout(request: Any, timeout: int) -> FakeHTTPResponse:
        raise TimeoutError("rag request timeout")

    monkeypatch.setattr(rag_adapter, "urlopen", raise_timeout)

    assert call_adapter() == []


def test_invalid_results_shape_falls_back_to_empty_list(monkeypatch: Any) -> None:
    payload = {"success": True, "data": {"results": {}}, "message": ""}
    monkeypatch.setattr(rag_adapter, "urlopen", fake_urlopen_with_payload(payload))

    assert call_adapter() == []


def test_strict_mode_raises_on_rag_business_error(monkeypatch: Any) -> None:
    payload = {"success": False, "data": {"results": []}, "message": "RAG_ERROR"}
    monkeypatch.setattr(rag_adapter, "urlopen", fake_urlopen_with_payload(payload))

    with pytest.raises(rag_adapter.RagAdapterError):
        call_adapter(raise_on_error=True)
