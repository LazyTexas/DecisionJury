from __future__ import annotations

from backend.app.schemas.decision import RagEvidence


SHOPPING_HISTORY = [
    RagEvidence(
        id="history_001",
        title="历史闲置记录",
        content="用户曾购买机械键盘 399 元，实际使用频率较低，复盘认为偏冲动消费。",
        score=0.88,
        source="decision_history",
        case_type="shopping",
        tags=["electronics", "idle", "regret"],
        created_at="2026-06-05T12:00:00+08:00",
    ),
    RagEvidence(
        id="history_002",
        title="学习用品值得购买记录",
        content="用户曾购买学习台灯 129 元，几乎每天使用，复盘认为对学习效率有帮助。",
        score=0.72,
        source="decision_history",
        case_type="shopping",
        tags=["study", "useful"],
        created_at="2026-06-12T12:00:00+08:00",
    ),
    RagEvidence(
        id="history_003",
        title="预算超支提醒记录",
        content="用户曾在月末购买数码配件后压缩生活费，复盘建议高价电子产品先冷静三天。",
        score=0.8,
        source="decision_history",
        case_type="shopping",
        tags=["electronics", "budget", "cooling"],
        created_at="2026-06-20T12:00:00+08:00",
    ),
]


def search_mock_rag(user_id: str, case_id: str, case_type: str, query: str, top_k: int = 3) -> list[RagEvidence]:
    _ = (user_id, case_id)
    if case_type != "shopping":
        return []

    query_lower = query.lower()
    matched: list[RagEvidence] = []
    for item in SHOPPING_HISTORY:
        haystack = " ".join([item.title, item.content, *item.tags]).lower()
        if any(token in haystack for token in query_lower.split()):
            matched.append(item)

    if not matched and any(keyword in query for keyword in ["耳机", "电子", "数码", "预算", "学习"]):
        matched = SHOPPING_HISTORY[:]

    return matched[:top_k]
