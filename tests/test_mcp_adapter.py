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
    assert result.error == "user_id and case_id are required"


def test_create_reminder_exception_maps_to_failed_tool_result(monkeypatch: Any) -> None:
    def raise_error(*args: Any, **kwargs: Any) -> dict[str, Any]:
        raise RuntimeError("tool down")

    monkeypatch.setattr("backend.app.services.mcp_adapter.create_reminder", raise_error)

    result = mcp_adapter.create_cooling_reminder(
        user_id="u001",
        case_id="case_001",
        title="cooling review",
    )

    assert result.tool_name == "cooling_reminder"
    assert result.status == "failed"
    assert result.error == "REMINDER_CREATE_FAILED: tool down"
