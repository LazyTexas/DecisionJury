# -*- coding: utf-8 -*-
"""
端到端联调验证脚本（角色 D 的 P0-1）。

前提：已启动
  - B 后端：http://127.0.0.1:8000  （uvicorn backend.main:app）
  - D RAG： http://127.0.0.1:8001  （uvicorn retriever:app）

流程：
  1. 通过 B 创建购物案件（描述含完整字段 → ready_for_debate）。
  2. POST /api/cases/{id}/debate 触发 C 模块。
  3. 校验返回：status、rag_evidence、trace 里 rag_search 状态、report.final_decision。
  4. 额外直接打一个 RAG 无命中查询，验证“返回空数组、不编造”。

用法：
  uv run python rag/e2e_verify.py
"""

import json
import os
import sys
import urllib.request
import uuid

# Windows GBK 控制台无法打印 emoji，统一成 UTF-8 输出。
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass

BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")
RAG_URL = os.getenv("RAG_URL", "http://127.0.0.1:8001")
USER_ID = os.getenv("E2E_USER_ID", "e2e_user")


def http_post_json(url: str, body: dict | None = None) -> dict:
    data = json.dumps(body or {}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def http_get_json(url: str) -> dict:
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> None:
    # 1. 创建购物案件（描述含全量字段 → ready_for_debate）
    description = (
        "想买1299元无线降噪耳机 用于学习需要安静 "
        "我本月预算还剩3000元 我已有普通耳机 预计每天使用 原因是刚需"
    )
    create_resp = http_post_json(
        f"{BACKEND_URL}/api/cases",
        {
            "user_id": USER_ID,
            "case_type": "shopping",
            "title": "是否购买无线降噪耳机",
            "description": description,
        },
    )
    case_id = create_resp["data"]["case_id"]
    print(f"[1] 创建案件: {case_id}  状态={create_resp['data']['case_status']}")
    assert create_resp["data"]["case_status"] == "ready_for_debate", "案件未进入 ready_for_debate"

    # 2. 触发辩论
    debate_resp = http_post_json(f"{BACKEND_URL}/api/cases/{case_id}/debate", {"user_id": USER_ID})
    debate_data = debate_resp.get("data", {})
    print(f"[2] 辩论结果 success={debate_resp.get('success')}  message={debate_resp.get('message')}")
    assert debate_resp.get("success") is True, "辩论失败"

    rag_evidence = debate_data.get("rag_evidence", [])
    steps = debate_data.get("steps", [])
    report = debate_data.get("report", {})
    print(f"[3] rag_evidence 数量={len(rag_evidence)}")
    for ev in rag_evidence:
        print(f"      - {ev.get('id')} | {ev.get('title')} | score={ev.get('score')}")
    print(f"[4] report.final_decision={report.get('final_decision')}  confidence={report.get('confidence')}")
    print(f"     report.rag_evidence 引用数={len(report.get('rag_evidence', []))}")
    print(f"[5] Agent steps: {[s.get('agent') for s in steps]}")

    assert len(rag_evidence) > 0, "RAG 未返回任何证据，C-D 联调未命中"
    assert any(s.get("agent") == "judge_agent" for s in steps), "缺少法官 Agent 步骤"

    # 3. 查 trace，确认 rag_search completed
    trace_resp = http_get_json(f"{BACKEND_URL}/api/cases/{case_id}/trace")
    traces = trace_resp.get("data", {}).get("trace", [])
    rag_traces = [t for t in traces if t.get("name") in ("rag_search",)]
    print(f"[6] trace 中 rag_search 条目数={len(rag_traces)}")
    for t in rag_traces:
        print(f"      name={t.get('name')} status={t.get('status')} output={t.get('output_summary')}")

    rag_ok = any(t.get("status") == "completed" for t in rag_traces)
    assert rag_ok, "trace 未记录 rag_search completed"

    # 4. 直接打一个无命中查询，验证防幻觉（返回空数组）
    nohit_resp = http_post_json(
        f"{RAG_URL}/api/rag/search",
        {
            "user_id": USER_ID,
            "case_id": case_id,
            "case_type": "shopping",
            "query": "挖掘机 航空母舰",
            "top_k": 3,
        },
    )
    nohit_count = len(nohit_resp.get("data", {}).get("results", []))
    print(f"[7] 无命中查询返回结果数={nohit_count}（应=0）")
    assert nohit_count == 0, "无命中查询竟返回了数据，违反不编造原则"

    print("\n[OK] P0-1 端到端联调验证通过：C-D RAG 链路命中、trace completed、无命中返回空。")


if __name__ == "__main__":
    main()
