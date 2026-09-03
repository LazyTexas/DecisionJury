# -*- coding: utf-8 -*-
"""
RAG 标准版规则评估脚本（可复现）。

覆盖指标：
  检索侧（Retrieval）：
    - context_precision@k：检索到的结果里相关占比
    - context_recall@k   ：相关知识库里的相关记录被找回的比例
    - mrr                ：第一个相关结果排名的倒数均值
    - ndcg@k             ：归一化折损累计增益（二值相关）
  生成侧（Generation，仅在 --live 下计算，需要后端+C+RAG 服务）：
    - faithfulness        ：判决书文本词项落在检索证据文本中的比例（越贴近证据越高）
    - answer_relevancy    ：判决书文本覆盖标准答案要点（answer_points）的比例
    - latency_ms          ：本次 debate 的 trace 总耗时

用法：
  # 只跑检索指标（离线、可复现，不需要后端）
  uv run python rag/evaluate_rag_standard.py --out data/rag_std_retrieval.json

  # 连后端+RAG 一起跑，额外输出生成侧指标
  uv run python rag/evaluate_rag_standard.py --live --out data/rag_std_full.json
"""

import json
import math
import os
import sys
import urllib.request
import uuid
from typing import Any

import jieba

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(BASE_DIR, ".."))
sys.path.insert(0, BASE_DIR)

os.environ.setdefault("RAG_LIVE_RECORDS", "0")

from data_loader import load_history_data  # noqa: E402
from retriever import RagRequest, rag_search  # noqa: E402

BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")
TOP_K = 5

# ---------------------------------------------------------------------------
# 标准评估用例（questions + 相关关键词 + 标准回答要点）
# ---------------------------------------------------------------------------
GROUND_TRUTH = [
    {
        "query": "想买降噪耳机",
        "case_type": "shopping",
        "relevance_keywords": ["耳机"],
        "answer_points": ["耳机", "降噪", "预算", "暂缓", "delay"],
        "description": "想买1299元无线降噪耳机 用于学习需要安静 我本月预算还剩3000元 我已有普通耳机 预计每天使用 原因是刚需",
    },
    {
        "query": "想买学习用品",
        "case_type": "shopping",
        "relevance_keywords": ["学习", "台灯", "平板", "文具", "翻译", "打印"],
        "answer_points": ["学习", "台灯", "平板", "预算", "值得", "buy"],
        "description": "想买499元学习平板 用于学习记笔记 我本月预算还剩2000元 我已有纸质笔记本 预计每天使用 原因是学习需要",
    },
    {
        "query": "参加社团活动",
        "case_type": "time",
        "relevance_keywords": ["社团"],
        "answer_points": ["社团", "活动", "延期", "拒绝", "reject"],
        "description": None,
    },
    {
        "query": "参加技术分享",
        "case_type": "time",
        "relevance_keywords": ["技术", "分享"],
        "answer_points": ["技术", "分享", "值得", "accept"],
        "description": None,
    },
]


# ---------------------------------------------------------------------------
# 纯函数：指标计算（便于单测）
# ---------------------------------------------------------------------------
def _terms(text: str) -> set[str]:
    return {t for t in jieba.lcut_for_search(text) if len(t.strip()) > 1}


def precision_at_k(retrieved_ids: list[str], relevant_ids: set[str], k: int = TOP_K) -> float:
    if not retrieved_ids:
        return 0.0
    hit = sum(1 for rid in retrieved_ids[:k] if rid in relevant_ids)
    return hit / len(retrieved_ids[:k])


def recall_at_k(retrieved_ids: list[str], relevant_ids: set[str], k: int = TOP_K) -> float:
    if not relevant_ids:
        return 0.0
    hit = sum(1 for rid in retrieved_ids[:k] if rid in relevant_ids)
    return hit / len(relevant_ids)


def mrr(retrieved_ids: list[str], relevant_ids: set[str], k: int = TOP_K) -> float:
    for rank, rid in enumerate(retrieved_ids[:k], start=1):
        if rid in relevant_ids:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(retrieved_ids: list[str], relevant_ids: set[str], k: int = TOP_K) -> float:
    gains = [1.0 if rid in relevant_ids else 0.0 for rid in retrieved_ids[:k]]
    dcg = sum(gain / math.log2(i + 2) for i, gain in enumerate(gains))
    total_rel = min(k, len(relevant_ids))
    idcg = sum(1.0 / math.log2(i + 2) for i in range(total_rel))
    return dcg / idcg if idcg > 0 else 0.0


def faithfulness_score(report_text: str, evidence_text: str) -> float:
    report_terms = _terms(report_text)
    if not report_terms:
        return 0.0
    evidence_terms = _terms(evidence_text)
    return len(report_terms & evidence_terms) / len(report_terms)


def answer_relevancy_score(report_text: str, answer_points: list[str]) -> float:
    if not answer_points:
        return 0.0
    hit = sum(1 for point in answer_points if point in report_text)
    return hit / len(answer_points)


def _run_in_process_search(ct: str, query: str, k: int) -> list[dict[str, Any]]:
    req = RagRequest(user_id="eval_user", case_id="eval_case", case_type=ct, query=query, top_k=k)
    res = asyncio_run(rag_search(req))
    return res.get("data", {}).get("results", [])


# 轻量 async 封装（避免在纯函数路径里引入 asyncio.run 的混乱）
def asyncio_run(coro):
    import asyncio
    return asyncio.run(coro)


def build_relevant_ids(case_type: str, relevance_keywords: list[str]) -> set[str]:
    all_records = load_history_data("eval_user")
    ids = set()
    for r in all_records:
        if r.get("case_type") != case_type:
            continue
        title = str(r.get("title", ""))
        if any(kw in title for kw in relevance_keywords):
            ids.add(str(r.get("id", "")))
    return ids


def evaluate_retrieval(gt: dict[str, Any]) -> dict[str, Any]:
    results = _run_in_process_search(gt["case_type"], gt["query"], TOP_K)
    retrieved_ids = [str(r.get("id", "")) for r in results]
    relevant_ids = build_relevant_ids(gt["case_type"], gt["relevance_keywords"])
    return {
        "query": gt["query"],
        "case_type": gt["case_type"],
        "top_k": TOP_K,
        "retrieved_ids": retrieved_ids,
        "relevant_count": len(relevant_ids),
        "context_precision_at_k": round(precision_at_k(retrieved_ids, relevant_ids), 4),
        "context_recall_at_k": round(recall_at_k(retrieved_ids, relevant_ids), 4),
        "mrr": round(mrr(retrieved_ids, relevant_ids), 4),
        "ndcg_at_k": round(ndcg_at_k(retrieved_ids, relevant_ids), 4),
    }


def _post_json(url: str, body: dict | None = None) -> dict:
    data = json.dumps(body or {}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _get_json(url: str) -> dict:
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def evaluate_generation(gt: dict[str, Any], user_id: str) -> dict[str, Any] | None:
    """跑一次真实购物辩论，计算生成侧指标。time 场景 C 暂不支持 -> 返回 None。"""
    if gt["case_type"] != "shopping" or not gt["description"]:
        return None
    create_resp = _post_json(
        f"{BACKEND_URL}/api/cases",
        {
            "user_id": user_id,
            "case_type": gt["case_type"],
            "title": gt["query"],
            "description": gt["description"],
        },
    )
    case_id = create_resp["data"]["case_id"]
    debate_resp = _post_json(f"{BACKEND_URL}/api/cases/{case_id}/debate", {"user_id": user_id})
    data = debate_resp.get("data", {}) or {}
    report = data.get("report") or {}
    rag_evidence = data.get("rag_evidence", []) or []

    # debate 响应不直接带 trace，需从 /trace 接口取真实执行耗时
    trace_resp = _get_json(f"{BACKEND_URL}/api/cases/{case_id}/trace")
    trace = trace_resp.get("data", {}).get("trace", []) or []

    report_text = " ".join(
        [
            str(report.get("summary", "")),
            str(report.get("case_summary", "")),
            str(report.get("final_decision", "")),
            " ".join(report.get("pro_points", []) or []),
            " ".join(report.get("con_points", []) or []),
            " ".join(report.get("next_actions", []) or []),
        ]
    )
    evidence_text = " ".join(
        [str(e.get("title", "")) + " " + str(e.get("content", "")) for e in rag_evidence]
    )
    latency_ms = sum(int(t.get("duration_ms", 0) or 0) for t in trace)

    return {
        "query": gt["query"],
        "case_type": gt["case_type"],
        "generation_available": True,
        "faithfulness": round(faithfulness_score(report_text, evidence_text), 4),
        "answer_relevancy": round(answer_relevancy_score(report_text, gt["answer_points"]), 4),
        "latency_ms": latency_ms,
        "report_cites_evidence": len((report.get("rag_evidence") or [])) > 0,
    }


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

    live = "--live" in sys.argv
    out = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else None

    report = {"mode": "live" if live else "offline", "retrieval": [], "generation": []}
    for gt in GROUND_TRUTH:
        report["retrieval"].append(evaluate_retrieval(gt))

    if live:
        user_id = f"std_user_{uuid.uuid4().hex[:5]}"
        for gt in GROUND_TRUTH:
            gen = evaluate_generation(gt, user_id)
            if gen is None:
                report["generation"].append(
                    {"query": gt["query"], "case_type": gt["case_type"], "generation_available": False}
                )
            else:
                report["generation"].append(gen)

    print("=== RAG 标准版评估 ===")
    print(f"mode: {report['mode']}")
    print("\n[检索侧]")
    for r in report["retrieval"]:
        print(
            f"  {r['query']:<10} precision@k={r['context_precision_at_k']:<6} "
            f"recall@k={r['context_recall_at_k']:<6} mrr={r['mrr']:<6} ndcg@k={r['ndcg_at_k']}"
        )
    if report["generation"]:
        print("\n[生成侧]")
        for g in report["generation"]:
            if g["generation_available"]:
                print(
                    f"  {g['query']:<10} faithfulness={g['faithfulness']:<6} "
                    f"answer_relevancy={g['answer_relevancy']:<6} latency_ms={g['latency_ms']}"
                )
            else:
                print(f"  {g['query']:<10} generation_available=False（C 暂不支持 time 流程）")

    if out:
        with open(out, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"\n已写入 {out}")


if __name__ == "__main__":
    main()
