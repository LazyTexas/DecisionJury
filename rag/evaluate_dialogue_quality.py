# -*- coding: utf-8 -*-
"""
对话质量量化评估脚本（角色 D 的 RAG 验收指标，见 docs/05_TestPlan.md §5.2）。

前提：已启动
  - B 后端：http://127.0.0.1:8000  （uvicorn backend.main:app）
  - D RAG： http://127.0.0.1:8001  （uvicorn retriever:app）

指标：
  1. retrieval_hits          —— 检索命中的历史证据数量（top_k 命中数）
  2. evidence_in_judge_context —— 检索结果是否进入法官上下文（rag_evidence 非空）
  3. report_cites_evidence    —— 判决书是否引用历史证据（report.rag_evidence 非空）
  4. grounded_keyword_hit     —— 判决书文本是否命中证据/主题关键词（回答相关性/接地性代理指标）
  5. token_overlap            —— 判决书文本与证据文本的 jieba 词覆盖数

用法：
  uv run python rag/evaluate_dialogue_quality.py --out data/rag_dialogue_quality_result.json
"""

import json
import os
import sys
import urllib.request
import uuid
from typing import Any

import jieba

BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")
RAG_URL = os.getenv("RAG_URL", "http://127.0.0.1:8001")
USER_ID = os.getenv("EVAL_USER_ID", "dlq_user")


# ---------------------------------------------------------------------------
# 纯函数：指标计算（便于单测）
# ---------------------------------------------------------------------------
def _report_text(report: dict[str, Any] | None) -> str:
    if not report:
        return ""
    parts = [
        str(report.get("summary", "")),
        str(report.get("case_summary", "")),
        str(report.get("final_decision", "")),
        " ".join(report.get("pro_points", []) or []),
        " ".join(report.get("con_points", []) or []),
        " ".join(report.get("next_actions", []) or []),
    ]
    return " ".join(p for p in parts if p)


def _evidence_text(rag_evidence: list[dict[str, Any]]) -> str:
    parts = []
    for ev in rag_evidence or []:
        parts.append(str(ev.get("title", "")))
        parts.append(str(ev.get("content", "")))
        parts.append(" ".join(ev.get("tags", []) or []))
    return " ".join(parts)


def _jieba_terms(text: str) -> set[str]:
    return {t for t in jieba.lcut_for_search(text) if len(t.strip()) > 1}


def compute_metrics(
    debate_success: bool,
    rag_evidence: list[dict[str, Any]],
    report: dict[str, Any] | None,
) -> dict[str, Any]:
    """根据一次完整辩论结果计算 RAG 验收与回答相关性代理指标。"""
    retrieval_hits = len(rag_evidence or [])
    evidence_in_judge_context = retrieval_hits > 0
    report_cites_evidence = bool(report) and len((report or {}).get("rag_evidence", []) or []) > 0

    r_text = _report_text(report)
    ev_text = _evidence_text(rag_evidence)
    r_terms = _jieba_terms(r_text)
    ev_terms = _jieba_terms(ev_text)
    overlap = len(r_terms & ev_terms)
    grounded_keyword_hit = overlap > 0

    return {
        "debate_success": bool(debate_success),
        "retrieval_hits": retrieval_hits,
        "evidence_in_judge_context": evidence_in_judge_context,
        "report_cites_evidence": report_cites_evidence,
        "grounded_keyword_hit": grounded_keyword_hit,
        "token_overlap": overlap,
    }


# ---------------------------------------------------------------------------
# HTTP 辅助
# ---------------------------------------------------------------------------
def _http_post_json(url: str, body: dict | None = None) -> dict:
    data = json.dumps(body or {}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _run_flow() -> tuple[bool, list[dict], dict | None, str]:
    """创建购物案件 → 辩论 → 返回 (success, rag_evidence, report, 查询词)。"""
    user_id = f"{USER_ID}_{uuid.uuid4().hex[:5]}"
    description = (
        "想买1299元无线降噪耳机 用于学习需要安静 "
        "我本月预算还剩3000元 我已有普通耳机 预计每天使用 原因是刚需"
    )
    create_resp = _http_post_json(
        f"{BACKEND_URL}/api/cases",
        {
            "user_id": user_id,
            "case_type": "shopping",
            "title": "是否购买无线降噪耳机",
            "description": description,
        },
    )
    case_id = create_resp["data"]["case_id"]
    debate_resp = _http_post_json(
        f"{BACKEND_URL}/api/cases/{case_id}/debate", {"user_id": user_id}
    )
    data = debate_resp.get("data", {}) or {}
    return (
        bool(debate_resp.get("success")),
        data.get("rag_evidence", []) or [],
        data.get("report"),
        "是否购买无线降噪耳机",
    )


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

    success, rag_evidence, report, query = _run_flow()
    metrics = compute_metrics(success, rag_evidence, report)
    metrics["query"] = query

    print("=== 对话质量量化指标（完整 RAG 验收） ===")
    print(f"  query                    : {query}")
    print(f"  debate_success           : {metrics['debate_success']}")
    print(f"  retrieval_hits           : {metrics['retrieval_hits']}")
    print(f"  evidence_in_judge_context: {metrics['evidence_in_judge_context']}")
    print(f"  report_cites_evidence    : {metrics['report_cites_evidence']}")
    print(f"  grounded_keyword_hit     : {metrics['grounded_keyword_hit']}")
    print(f"  token_overlap            : {metrics['token_overlap']}")

    out = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else None
    if out:
        with open(out, "w", encoding="utf-8") as f:
            json.dump(metrics, f, ensure_ascii=False, indent=2)
        print(f"已写入 {out}")


if __name__ == "__main__":
    main()
