from __future__ import annotations

from typing import Any

from backend.app.orchestrator.decision_flow import run_decision_flow
from backend.app.schemas.decision import to_dict


SHOPPING_FINAL_DECISIONS = {"buy", "delay", "reject", "alternative"}
EXPECTED_AGENT_ORDER = ["input_parser", "pro_agent", "con_agent", "judge_agent"]
EXPECTED_TRACE_NAMES = [
    "input_parser",
    "rag_search",
    "cost_analyzer",
    "pro_agent",
    "con_agent",
    "judge_agent",
]


class FakeLLMClient:
    def complete_json(self, task: str, payload: dict[str, Any]) -> dict[str, Any]:
        if task == "pro_agent":
            return {
                "summary": "The product has a clear study use case.",
                "arguments": [
                    "The user described a concrete study need.",
                    "Expected usage is frequent enough to consider the value.",
                ],
                "confidence": 0.72,
            }
        if task == "con_agent":
            return {
                "summary": "The purchase still has budget and alternative risks.",
                "arguments": [
                    "The user already has an alternative item.",
                    "The price takes a visible share of the remaining budget.",
                ],
                "confidence": 0.8,
            }
        raise AssertionError(f"Unexpected LLM task: {task}")


def fake_llm_client() -> FakeLLMClient:
    return FakeLLMClient()


def complete_shopping_fields() -> dict[str, Any]:
    return {
        "product_name": "study headphones",
        "price": 1299,
        "purpose": "study focus",
        "monthly_budget_left": 2000,
        "owned_alternatives": "basic earbuds",
        "expected_usage_frequency": "daily",
        "trigger_reason": "study need",
    }


def run_complete_shopping_case() -> dict[str, Any]:
    return to_dict(
        run_decision_flow(
            raw_input="complete shopping case",
            user_id="u001",
            case_id="case_test_shopping",
            existing_collected_fields=complete_shopping_fields(),
        )
    )


def test_normal_shopping_case_completes_debate(monkeypatch: Any) -> None:
    monkeypatch.setattr("backend.app.agents.pro_agent.get_llm_client", fake_llm_client)
    monkeypatch.setattr("backend.app.agents.con_agent.get_llm_client", fake_llm_client)

    result = run_complete_shopping_case()

    assert result["success"] is True
    assert result["case_status"] == "completed"


def test_steps_contain_agents_in_required_order(monkeypatch: Any) -> None:
    monkeypatch.setattr("backend.app.agents.pro_agent.get_llm_client", fake_llm_client)
    monkeypatch.setattr("backend.app.agents.con_agent.get_llm_client", fake_llm_client)

    result = run_complete_shopping_case()

    assert [step["agent"] for step in result["steps"]] == EXPECTED_AGENT_ORDER


def test_debate_output_contains_required_sections(monkeypatch: Any) -> None:
    monkeypatch.setattr("backend.app.agents.pro_agent.get_llm_client", fake_llm_client)
    monkeypatch.setattr("backend.app.agents.con_agent.get_llm_client", fake_llm_client)

    result = run_complete_shopping_case()

    for key in ["rag_evidence", "tool_results", "report", "trace"]:
        assert key in result
    assert isinstance(result["rag_evidence"], list)
    assert isinstance(result["tool_results"], list)
    assert isinstance(result["report"], dict)
    assert isinstance(result["trace"], list)


def test_report_final_decision_is_valid_shopping_decision(monkeypatch: Any) -> None:
    monkeypatch.setattr("backend.app.agents.pro_agent.get_llm_client", fake_llm_client)
    monkeypatch.setattr("backend.app.agents.con_agent.get_llm_client", fake_llm_client)

    result = run_complete_shopping_case()

    assert result["report"]["final_decision"] in SHOPPING_FINAL_DECISIONS


def test_high_risk_input_is_rejected_before_debate(monkeypatch: Any) -> None:
    monkeypatch.setattr("backend.app.agents.pro_agent.get_llm_client", fake_llm_client)
    monkeypatch.setattr("backend.app.agents.con_agent.get_llm_client", fake_llm_client)

    result = to_dict(
        run_decision_flow(
            raw_input="\u6211\u8981\u4e0d\u8981\u5403\u8fd9\u4e2a\u836f",
            user_id="u001",
            case_id="case_high_risk",
        )
    )

    assert result["success"] is False
    assert result["message"] == "HIGH_RISK_DECISION"
    assert result["case_status"] == "rejected"
    assert [step["agent"] for step in result["steps"]] == ["input_parser"]
    assert [item["name"] for item in result["trace"]] == ["input_parser"]
    assert result["rag_evidence"] == []
    assert result["tool_results"] == []
    assert result["report"] is None
    assert result["reason"]


def test_missing_fields_return_next_question_or_reason(monkeypatch: Any) -> None:
    monkeypatch.setattr("backend.app.agents.pro_agent.get_llm_client", fake_llm_client)
    monkeypatch.setattr("backend.app.agents.con_agent.get_llm_client", fake_llm_client)

    result = to_dict(
        run_decision_flow(
            raw_input="shopping case missing required fields",
            user_id="u001",
            case_id="case_missing_fields",
        )
    )

    assert result["success"] is False
    assert result["message"] == "MISSING_FIELDS"
    assert result["case_status"] == "collecting"
    assert result["reason"]
    assert [step["agent"] for step in result["steps"]] == ["input_parser"]
    assert result["rag_evidence"] == []
    assert result["tool_results"] == []
    assert result["report"] is None


def test_empty_rag_returns_empty_evidence_without_fabrication(monkeypatch: Any) -> None:
    monkeypatch.setattr("backend.app.agents.pro_agent.get_llm_client", fake_llm_client)
    monkeypatch.setattr("backend.app.agents.con_agent.get_llm_client", fake_llm_client)
    monkeypatch.setattr("backend.app.orchestrator.decision_flow.search_mock_rag", lambda *args, **kwargs: [])

    result = run_complete_shopping_case()

    assert result["success"] is True
    assert result["rag_evidence"] == []
    assert result["report"]["rag_evidence"] == []


def test_trace_records_required_steps(monkeypatch: Any) -> None:
    monkeypatch.setattr("backend.app.agents.pro_agent.get_llm_client", fake_llm_client)
    monkeypatch.setattr("backend.app.agents.con_agent.get_llm_client", fake_llm_client)

    result = run_complete_shopping_case()
    trace_names = [item["name"] for item in result["trace"]]

    for name in EXPECTED_TRACE_NAMES:
        assert name in trace_names
    assert trace_names.index("input_parser") < trace_names.index("rag_search")
    assert trace_names.index("rag_search") < trace_names.index("cost_analyzer")
    assert trace_names.index("cost_analyzer") < trace_names.index("pro_agent")
    assert trace_names.index("pro_agent") < trace_names.index("con_agent")
    assert trace_names.index("con_agent") < trace_names.index("judge_agent")


def test_tool_results_include_cost_analyzer(monkeypatch: Any) -> None:
    monkeypatch.setattr("backend.app.agents.pro_agent.get_llm_client", fake_llm_client)
    monkeypatch.setattr("backend.app.agents.con_agent.get_llm_client", fake_llm_client)

    result = run_complete_shopping_case()

    assert any(item["tool_name"] == "cost_analyzer" for item in result["tool_results"])
