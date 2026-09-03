# -*- coding: utf-8 -*-
"""
RAG 检索评测脚本。

作用：
  用 docs/05_TestPlan.md §5.1 的标准查询，对 D 模块 RAG（BM25 /api/rag/search）
  跑出可复现的评测指标，作为答辩/联调证据：

  - top_k 命中数量
  - 是否全部命中目标 case_type（类型隔离）
  - 是否命中预期关键词（期望召回）
  - 最高分/平均分
  - 是否把证据送入法官上下文（由 C 侧在端到端验证中确认）

用法：
  # 默认离线（RAG_LIVE_RECORDS=0），只对静态 500 条数据评测，保证可复现
  uv run python rag/evaluate_rag.py

  # 也可以带实时联动一起评测（需要 B 后端 8000 可用）
  RAG_LIVE_RECORDS=1 uv run python rag/evaluate_rag.py

产出：
  - 控制台打印评测表格
  - 可选：--out data/rag_eval_result.json 写入结构化结果
"""

import asyncio
import json
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(BASE_DIR, ".."))
sys.path.insert(0, BASE_DIR)

# 默认离线评测，避免依赖后端；如需实时联动用环境变量开启。
os.environ.setdefault("RAG_LIVE_RECORDS", "0")

from retriever import RagRequest, rag_search  # noqa: E402


# 标准评测用例（来自 docs/05_TestPlan.md §5.1）
QUERY_CASES = [
    {
        "case_type": "shopping",
        "query": "想买降噪耳机",
        "expected_keywords": ["耳机", "电子", "数码"],
        "top_k": 5,
    },
    {
        "case_type": "shopping",
        "query": "想买学习用品",
        "expected_keywords": ["学习", "台灯", "平板", "学习办公"],
        "top_k": 5,
    },
    {
        "case_type": "time",
        "query": "参加社团活动",
        "expected_keywords": ["社团", "活动", "社交"],
        "top_k": 5,
    },
    {
        "case_type": "time",
        "query": "参加技术分享",
        "expected_keywords": ["技术", "分享", "技能"],
        "top_k": 5,
    },
]


def _run_search(case_type: str, query: str, top_k: int) -> list[dict]:
    req = RagRequest(
        user_id="eval_user",
        case_id="eval_case",
        case_type=case_type,
        query=query,
        top_k=top_k,
    )
    res = asyncio.run(rag_search(req))
    return res.get("data", {}).get("results", [])


def _expected_hit(results: list[dict], keywords: list[str]) -> bool:
    for item in results:
        text = " ".join(
            [
                str(item.get("title", "")),
                str(item.get("content", "")),
                " ".join(item.get("tags", []) or []),
            ]
        )
        if any(kw in text for kw in keywords):
            return True
    return False


def evaluate() -> dict:
    rows = []
    for case in QUERY_CASES:
        results = _run_search(case["case_type"], case["query"], case["top_k"])
        scores = [float(r.get("score", 0)) for r in results]
        rows.append(
            {
                "query": case["query"],
                "case_type": case["case_type"],
                "top_k": case["top_k"],
                "hits": len(results),
                "type_ok": all(r.get("case_type") == case["case_type"] for r in results),
                "expected_hit": _expected_hit(results, case["expected_keywords"]),
                "max_score": round(max(scores), 4) if scores else 0,
                "avg_score": round(sum(scores) / len(scores), 4) if scores else 0,
                "top_titles": [r.get("title", "") for r in results[:3]],
            }
        )
    return {"mode": "offline" if os.environ.get("RAG_LIVE_RECORDS", "0") == "0" else "live", "results": rows}


def _print_table(eval_data: dict) -> None:
    print(f"\n=== RAG 评测（mode={eval_data['mode']}） ===")
    print(f"{'query':<14}{'type':<10}{'top_k':<6}{'hits':<6}{'type_ok':<8}{'expected_hit':<14}{'max_score':<12}")
    for r in eval_data["results"]:
        print(
            f"{r['query']:<14}{r['case_type']:<10}{r['top_k']:<6}{r['hits']:<6}"
            f"{str(r['type_ok']):<8}{str(r['expected_hit']):<14}{r['max_score']:<12}"
        )
    print("\nTop 命中标题：")
    for r in eval_data["results"]:
        print(f"  [{r['query']}] -> {r['top_titles']}")


def main() -> None:
    eval_data = evaluate()
    _print_table(eval_data)

    out = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else None
    if out:
        with open(out, "w", encoding="utf-8") as f:
            json.dump(eval_data, f, ensure_ascii=False, indent=2)
        print(f"\n已写入 {out}")


if __name__ == "__main__":
    main()
