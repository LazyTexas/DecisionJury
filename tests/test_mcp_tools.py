# tests/test_mcp_tools.py
"""E 模块 MCP 契约层测试：工具定义 + call_tool 分发 + 调用日志。"""

from mcp_tools.mcp import get_tool_definitions, call_tool
from mcp_tools.logger import logger
from typing import Any


def setup_function() -> None:
    """每个用例前清空日志，避免互相干扰。"""
    logger.clear()


def test_tool_definitions_contain_tools() -> None:
    """声明 cost_analyzer / cooling_reminder / decision_score 三个工具。"""
    defs = get_tool_definitions()
    names = {d["name"] for d in defs}
    assert "cost_analyzer" in names
    assert "cooling_reminder" in names
    assert "decision_score" in names


def test_cost_analyzer_shopping_success() -> None:
    """购物成本分析成功返回 ToolResult 结构。"""
    result = call_tool(
        "cost_analyzer",
        {"case_type": "shopping", "price": 1200, "monthly_budget_left": 2000},
    )
    assert result["tool_name"] == "cost_analyzer"
    assert result["status"] == "success"
    assert result["risk_level"] == "medium"
    assert result["metrics"]["budget_ratio"] == 0.6
    assert result["metrics"]["budget_left_after_purchase"] == 800


def test_cost_analyzer_time_success() -> None:
    """时间成本分析成功返回 risk_level。"""
    result = call_tool(
        "cost_analyzer",
        {"case_type": "time", "hours_required": 16, "free_hours_this_week": 20, "urgent_tasks": 2},
    )
    assert result["tool_name"] == "cost_analyzer"
    assert result["status"] == "success"
    assert result["risk_level"] == "high"


def test_cost_analyzer_missing_case_type() -> None:
    """缺少 case_type 返回 failed / UNSUPPORTED_CASE_TYPE。"""
    result = call_tool("cost_analyzer", {"price": 100, "monthly_budget_left": 2000})
    assert result["status"] == "failed"
    assert result["error"] == "UNSUPPORTED_CASE_TYPE"


def test_cost_analyzer_missing_shopping_args() -> None:
    """shopping 缺预算返回 failed / MISSING_ARGS。"""
    result = call_tool("cost_analyzer", {"case_type": "shopping", "price": 100})
    assert result["status"] == "failed"
    assert result["error"] == "MISSING_ARGS"


def test_cooling_reminder_success() -> None:
    """冷静期提醒成功返回 reminder_id。"""
    result = call_tool(
        "cooling_reminder",
        {
            "user_id": "u001",
            "case_id": "case_001",
            "title": "冷静期复盘",
            "cooling_days": 3,
            "watch_items": ["是否仍需要"],
        },
    )
    assert result["tool_name"] == "cooling_reminder"
    assert result["status"] == "success"
    assert result["metrics"]["reminder_id"].startswith("r_")
    assert result["metrics"]["watch_items"] == ["是否仍需要"]


def test_cooling_reminder_missing_args() -> None:
    """缺少 user_id 返回 failed。"""
    result = call_tool("cooling_reminder", {"case_id": "case_001", "title": "test"})
    assert result["status"] == "failed"
    assert result["error"] == "MISSING_ARGS"


def test_decision_score_success() -> None:
    """决策评分成功返回 score 与 risk_level。"""
    result = call_tool(
        "decision_score",
        {
            "case_type": "shopping",
            "cost_risk_level": "low",
            "history_risk": 0.2,
            "usage_value": 0.9,
            "impulse_trigger": False,
        },
    )
    assert result["tool_name"] == "decision_score"
    assert result["status"] == "success"
    assert result["risk_level"] == "low"
    assert result["metrics"]["score"] == 90


def test_decision_score_invalid_case_type() -> None:
    """非法 case_type 返回 failed / UNSUPPORTED_CASE_TYPE。"""
    result = call_tool("decision_score", {"case_type": "medical"})
    assert result["status"] == "failed"
    assert result["error"] == "UNSUPPORTED_CASE_TYPE"


def test_decision_score_impulse_string_false() -> None:
    """字符串 "false" 应解析为 False，不扣分。"""
    result = call_tool("decision_score", {"case_type": "shopping", "impulse_trigger": "false"})
    assert result["status"] == "success"
    assert result["metrics"]["score"] == 50


def test_decision_score_impulse_string_true() -> None:
    """字符串 "true" 应解析为 True，扣 10 分。"""
    result = call_tool("decision_score", {"case_type": "shopping", "impulse_trigger": "true"})
    assert result["status"] == "success"
    assert result["metrics"]["score"] == 40


def test_decision_score_impulse_invalid() -> None:
    """非法字符串应返回 failed / INVALID_ARGS，而不是被强转成 True。"""
    result = call_tool("decision_score", {"case_type": "shopping", "impulse_trigger": "abc"})
    assert result["status"] == "failed"
    assert result["error"] == "INVALID_ARGS"


def test_unknown_tool_failed() -> None:
    """未知工具名返回 failed / UNKNOWN_TOOL。"""
    result = call_tool("not_exist", {})
    assert result["status"] == "failed"
    assert result["error"] == "UNKNOWN_TOOL"


def test_call_logs_every_call() -> None:
    """成功路径：工具函数写一条日志，call_tool 不重复写（只保留一条）。"""
    call_tool(
        "cost_analyzer",
        {"case_type": "shopping", "price": 300, "monthly_budget_left": 2000},
    )
    logs = logger.get_all()
    cost_logs = [r for r in logs if r["tool_name"] == "cost_analyzer"]
    assert len(cost_logs) == 1, f"期望只有一条日志，实际 {len(cost_logs)} 条"


def test_call_logs_failure_only_once() -> None:
    """失败路径：call_tool 补一条失败日志，且只有一条。"""
    call_tool("decision_score", {"case_type": "shopping", "impulse_trigger": "abc"})
    logs = logger.get_all()
    failed_logs = [
        r for r in logs
        if r["tool_name"] == "decision_score" and r["output"].get("status") == "failed"
    ]
    assert len(failed_logs) == 1
