from __future__ import annotations

from typing import Any

from backend.app.services import mcp_adapter


def test_analyze_shopping_success_maps_to_tool_result() -> None:
    result = mcp_adapter.analyze_shopping_cost(
        case_id="case_001",
        case_type="shopping",
        fields={"price": 1200, "monthly_budget_left": 2000},
    )

    assert result.tool_name == "cost_analyzer"
    assert result.status == "success"
    assert result.risk_level == "medium"
    assert result.metrics["budget_ratio"] == 0.6
    assert result.metrics["budget_left_after_purchase"] == 800
    assert result.summary
    assert result.error is None


def test_create_reminder_success_maps_to_tool_result() -> None:
    result = mcp_adapter.create_cooling_reminder(
        user_id="u001",
        case_id="case_001",
        title="cooling review",
        cooling_days=3,
        reason="budget risk",
        watch_items=["still needed"],
    )

    assert result.tool_name == "cooling_reminder"
    assert result.status == "success"
    assert result.risk_level is None
    assert result.metrics["reminder_id"].startswith("r_")
    assert result.metrics["status"] == "scheduled"
    assert result.metrics["cooling_days"] == 3
    assert result.metrics["watch_items"] == ["still needed"]
    assert result.error is None


def test_create_reminder_error_maps_to_failed_tool_result() -> None:
    result = mcp_adapter.create_cooling_reminder(
        user_id="",
        case_id="case_001",
        title="cooling review",
        cooling_days=3,
        reason="budget risk",
    )

    assert result.tool_name == "cooling_reminder"
    assert result.status == "failed"
    assert result.risk_level is None
    assert result.metrics == {}
    assert result.error == "MISSING_ARGS"


def test_adapter_uses_unified_mcp_entrypoint(monkeypatch: Any) -> None:
    captured: dict[str, Any] = {}

    def fake_call_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        captured["name"] = name
        captured["arguments"] = arguments
        return {
            "tool_name": name,
            "status": "failed",
            "summary": "工具调用失败，主流程继续。",
            "risk_level": None,
            "metrics": {"status": "failed"},
            "error": "TOOL_ERROR: tool down",
        }

    monkeypatch.setattr("backend.app.services.mcp_adapter.call_tool", fake_call_tool)

    result = mcp_adapter.create_cooling_reminder(
        user_id="u001",
        case_id="case_001",
        title="cooling review",
    )

    assert result.tool_name == "cooling_reminder"
    assert result.status == "failed"
    assert result.summary == "冷静期提醒创建失败，建议用户手动设置复盘提醒。"
    assert result.metrics == {"status": "failed"}
    assert result.error == "TOOL_ERROR: tool down"
    assert captured["name"] == "cooling_reminder"
    assert captured["arguments"]["watch_items"] == []


def test_analyze_time_cost_maps_to_tool_result() -> None:
    """time 场景成本工具映射为 ToolResult。"""
    result = mcp_adapter.analyze_time_cost(
        hours_required=16,
        free_hours_this_week=20,
        urgent_tasks=2,
    )

    assert result.tool_name == "cost_analyzer"
    assert result.status == "success"
    assert result.risk_level == "high"
    assert result.metrics["time_ratio"] == 0.8
    assert result.metrics["urgent_tasks"] == 2
    assert result.summary
    assert result.error is None
