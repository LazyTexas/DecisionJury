from __future__ import annotations

import json
import os
from typing import Any
from urllib.request import Request, urlopen

from backend.app.schemas.decision import RagEvidence


DEFAULT_RAG_SEARCH_URL = "http://127.0.0.1:8001/api/rag/search"
RAG_TIMEOUT_SECONDS = 3


class RagAdapterError(RuntimeError):
    """RAG 服务调用或响应契约不符合预期时的 C 侧统一异常。"""


def search_rag_evidence(
    user_id: str,
    case_id: str,
    case_type: str,
    query: str,
    top_k: int = 3,
    search_url: str | None = None,
    timeout_seconds: int = RAG_TIMEOUT_SECONDS,
    raise_on_error: bool = False,
) -> list[RagEvidence]:
    """调用 D 模块 RAG 服务，并转换为 C 模块稳定使用的 RagEvidence 列表。"""

    try:
        return _search_rag_evidence_or_raise(
            user_id=user_id,
            case_id=case_id,
            case_type=case_type,
            query=query,
            top_k=top_k,
            search_url=search_url,
            timeout_seconds=timeout_seconds,
        )
    except Exception as exc:
        if raise_on_error:
            raise RagAdapterError(f"RAG search failed: {exc}") from exc

        # 默认模式用于脚本、单测或其他非编排调用：RAG 只是证据来源之一，
        # 失败时返回空数组可以保证调用方不用额外写异常兜底，也不会编造历史证据。
        return []


def _search_rag_evidence_or_raise(
    user_id: str,
    case_id: str,
    case_type: str,
    query: str,
    top_k: int,
    search_url: str | None,
    timeout_seconds: int,
) -> list[RagEvidence]:
    # RAG 属于外部服务，URL 允许用环境变量覆盖，方便本地联调和部署环境切换。
    # 调用方不需要知道 HTTP 细节，只拿到 docs/04_API.md 约定的 RagEvidence[]。
    url = search_url or os.getenv("RAG_SEARCH_URL", DEFAULT_RAG_SEARCH_URL)
    request_body = {
        "user_id": user_id,
        "case_id": case_id,
        "case_type": case_type,
        "query": query,
        "top_k": top_k,
    }
    request = Request(
        url=url,
        data=json.dumps(request_body, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urlopen(request, timeout=timeout_seconds) as response:
        response_data = json.loads(response.read().decode("utf-8"))

    if not isinstance(response_data, dict):
        raise RagAdapterError("RAG response must be a JSON object")

    if response_data.get("success") is not True:
        message = response_data.get("message") or "RAG_ERROR"
        raise RagAdapterError(str(message))

    data = response_data.get("data")
    if not isinstance(data, dict):
        raise RagAdapterError("RAG response missing data object")

    results = data.get("results")
    if not isinstance(results, list):
        raise RagAdapterError("RAG response data.results must be a list")

    # success=true + results=[] 是 D 模块明确表达“查了但没有命中”，不是服务失败。
    # 这种情况需要让 trace 记录 completed，法官再说明没有历史证据，不能混成 RAG_ERROR。
    return [_to_rag_evidence(item) for item in results]


def _to_rag_evidence(item: Any) -> RagEvidence:
    if not isinstance(item, dict):
        raise ValueError("RAG result item must be an object")

    tags = item["tags"]
    if not isinstance(tags, list) or not all(isinstance(tag, str) for tag in tags):
        raise ValueError("RAG result tags must be a string list")

    return RagEvidence(
        id=_required_str(item, "id"),
        title=_required_str(item, "title"),
        content=_required_str(item, "content"),
        score=float(item["score"]),
        source=_required_str(item, "source"),
        case_type=_required_str(item, "case_type"),
        tags=tags,
        created_at=_optional_str(item, "created_at"),
    )


def _required_str(item: dict[str, Any], key: str) -> str:
    value = item[key]
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"RAG result missing required field: {key}")
    return value


def _optional_str(item: dict[str, Any], key: str) -> str | None:
    value = item[key]
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"RAG result field must be string or null: {key}")
    return value
