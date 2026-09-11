# tests/test_user_facing_boundary.py
"""用户视图边界（T07）：文案清洗只作用于"给人读的话"，不得改写机器契约。

背景（真实事故）：边界中间件最初对**所有** JSON 响应做子串替换，于是
`tool_name="decision_score"` → `"决策评分"`、`missing_fields=["monthly_budget_left"]`
→ `["本月剩余预算"]`、`steps[].agent="pro_agent"` → `"正方"`、
`input_snapshot["使用频率"]="daily"` → `"每天"`、`/api/tools/*` 调试接口契约被改写，
一次性打挂 10 个用例。

本文件把边界规则固化为断言：
1. 整体是标识符/受控取值的字符串一律不改写（是 API 契约，前端 constants.ts 自己映射）；
2. 契约字段（tool_name / metrics / used_tool_names）保留，只**新增**展示名（tool_label / used_tool_labels）；
3. 调试面（/api/tools/*）原样返回，边界中间件不得介入；
4. 用户面的文案仍然清洗（内部字段名/工具名不得出现在判决书等文案里）；
5. 新增路由必须在 user_facing 模块里显式归类（用户面或调试面），漏归类直接失败。
"""

from __future__ import annotations

import re

import pytest

from backend.app.agents.user_facing import (
    RAW_SURFACE_PREFIXES,
    USER_FACING_PREFIXES,
    _deep_sanitize,
    has_internal_terms,
    is_classified_path,
    is_identifier_value,
    is_user_facing_path,
    public_report,
    public_steps,
    sanitize_user_text,
)

IDENTIFIER_ONLY = (
    "daily", "weekly_3plus", "weekly_1_2", "monthly", "occasional",
    "need", "promotion", "recommendation", "emotion",
    "low", "medium", "high",
    "unit_price_x_quantity", "unit_price", "total_price",
    "pro_agent", "con_agent", "judge_agent", "input_parser",
    "cost_analyzer", "decision_score", "cooling_reminder",
    "monthly_budget_left", "owned_alternatives", "frequency_canonical",
)


@pytest.mark.parametrize("value", IDENTIFIER_ONLY)
def test_identifier_values_are_never_rewritten(value: str) -> None:
    """受控取值/标识符是契约：`daily` 不能变成 `每天`，`pro_agent` 不能变成 `正方`。"""
    assert sanitize_user_text(value) == value
    assert is_identifier_value(value) is True


def test_prose_is_still_humanized() -> None:
    """用户面文案里的内部词仍然要换成人话（否则判决书又变工程文档）。"""
    prose = "系统调用 cost_analyzer 与 decision_score 后给出了结论。"
    cleaned = sanitize_user_text(prose, force=True)
    assert "cost_analyzer" not in cleaned and "decision_score" not in cleaned
    assert "成本分析" in cleaned and "决策评分" in cleaned
    assert has_internal_terms(cleaned) is False


def test_controlled_word_inside_identifier_is_not_mangled() -> None:
    """`covers_core_need` 里的 need 不得被当成受控取值翻译（曾翻成"确实需要"）。"""
    assert sanitize_user_text("字段 covers_core_need 为真") == "字段 covers_core_need 为真"
    assert sanitize_user_text("字段 covers_core_need 为真", force=True) == "字段 covers_core_need 为真"


def test_force_flag_cleans_identifier_only_string() -> None:
    """明确是文案的字段：即使整串是纯 ASCII 也要清洗，避免工具名单独成句漏给用户。"""
    assert sanitize_user_text("cost_analyzer") == "cost_analyzer"
    assert sanitize_user_text("cost_analyzer", force=True) == "成本分析"


def test_deep_sanitize_cleans_prose_values_and_keeps_machine_values() -> None:
    """递归清洗：文案键强制清洗，标识类取值原样保留，契约键名不改。"""
    payload = {
        "final_decision": "buy",
        "risk_level": "high",
        "missing_fields": ["monthly_budget_left"],
        "input_snapshot": {"使用频率": "daily"},
        "steps": [{"agent": "pro_agent", "used_tool_names": ["cost_analyzer"],
                   "summary": "cost_analyzer 认为可行"}],
    }
    cleaned = _deep_sanitize(payload)
    assert cleaned["final_decision"] == "buy"
    assert cleaned["risk_level"] == "high"
    assert cleaned["missing_fields"] == ["monthly_budget_left"]
    assert cleaned["input_snapshot"] == {"使用频率": "daily"}
    assert cleaned["steps"][0]["agent"] == "pro_agent"
    assert cleaned["steps"][0]["used_tool_names"] == ["cost_analyzer"]
    assert "cost_analyzer" not in cleaned["steps"][0]["summary"]


def test_public_report_keeps_contract_fields_and_adds_label() -> None:
    """report.tool_results：tool_name / metrics 是 docs/04_API.md §5.5 契约，必须保留。"""
    report = {
        "tool_results": [
            {"tool_name": "cost_analyzer", "status": "success", "summary": "占预算 60%。",
             "risk_level": "medium", "metrics": {"budget_ratio": 0.6}, "error": None},
        ],
        "debate_events": [
            {"event_id": "e1", "content": "正方发言", "tool_results": [{"tool_name": "cost_analyzer"}]},
        ],
    }
    out = public_report(report)
    tool = out["tool_results"][0]
    assert tool["tool_name"] == "cost_analyzer"          # 前端 VerdictPage/TraceLogView 依赖
    assert tool["metrics"] == {"budget_ratio": 0.6}      # §5.5 契约字段
    assert tool["tool_label"] == "成本分析"               # 新增展示名
    assert "tool_results" not in out["debate_events"][0]  # 事件级重复载荷仍剥掉


def test_public_steps_keeps_used_tool_names_and_adds_labels() -> None:
    """steps：`used_tool_names` 是 docs/04_API.md §5.3 契约字段，不得被改名替换。"""
    steps = [{"agent": "judge_agent", "used_tool_names": ["cost_analyzer", "cooling_reminder"],
              "summary": "综合 cost_analyzer 结论", "arguments": ["decision_score 偏高"]}]
    out = public_steps(steps)[0]
    assert out["used_tool_names"] == ["cost_analyzer", "cooling_reminder"]
    assert out["used_tool_labels"] == ["成本分析", "冷静期提醒"]
    assert "cost_analyzer" not in out["summary"]
    assert "decision_score" not in out["arguments"][0]


def test_tools_endpoints_bypass_the_boundary(client) -> None:
    """调试面原样返回：工具接口的调用方要拿 tool_name/metrics 做联调与断言。"""
    resp = client.post("/api/tools/cost-analyzer",
                       json={"case_type": "shopping", "price": 1200, "monthly_budget_left": 2000})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["tool_name"] == "cost_analyzer"
    assert data["metrics"]["budget_ratio"] == 0.6

    resp = client.post("/api/tools/decision-score", json={"case_type": "medical"})
    assert resp.status_code == 200
    assert resp.json()["data"]["tool_name"] == "decision_score"


def test_case_creation_keeps_machine_field_keys(client) -> None:
    """用户面接口：清洗只动文案，机器键（前端据此渲染追问/表单）必须原样保留。"""
    resp = client.post("/api/cases", json={
        "user_id": "u001",
        "case_type": "shopping",
        "title": "买耳机",
        "description": "想买个降噪耳机",
    })
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "monthly_budget_left" in data["missing_fields"]
    for field in data["missing_fields"]:
        assert re.match(r"^[a-z][a-z0-9_]*$", field), f"missing_fields 应是机器键: {field!r}"

    plan = data.get("reply_plan")
    if isinstance(plan, dict):  # 契约字段存在时必须仍是可读文案
        assert plan.get("_missing_fields") in (None, data["missing_fields"])
        assert has_internal_terms(plan.get("reply", "")) is False


def test_user_facing_and_raw_surface_prefixes_are_disjoint() -> None:
    """两个前缀集合必须互斥，否则同一路径会同时被清洗与放行。"""
    for user_prefix in USER_FACING_PREFIXES:
        assert is_user_facing_path(user_prefix) is True
        assert is_user_facing_path(f"{user_prefix}/child/1") is True
        assert user_prefix not in RAW_SURFACE_PREFIXES
    # 调试面绝不能被判定为用户面
    assert is_user_facing_path("/api/tools/cost-analyzer") is False
    assert is_user_facing_path("/auth/login") is False
    assert is_user_facing_path("/api/health") is False
    # 段匹配：前缀相近但不是子路径的不得误命中
    assert is_user_facing_path("/api/casesfoo") is False


def test_every_route_is_explicitly_classified() -> None:
    """新增路由必须归类：漏归类会让它悄悄走出（或走进）清洗边界。"""
    from backend.main import app

    unclassified = []
    for route in app.routes:
        path = getattr(route, "path", None)
        if not path:
            continue
        if not is_classified_path(path):
            unclassified.append(path)
    assert not unclassified, (
        "以下路由未在 backend/app/agents/user_facing.py 归类"
        f"（USER_FACING_PREFIXES 或 RAW_SURFACE_PREFIXES）：{sorted(set(unclassified))}"
    )
