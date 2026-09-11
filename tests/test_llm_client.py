from __future__ import annotations

import json
from typing import Any

import pytest

from backend.app.services import llm_client


def sample_payload() -> dict[str, Any]:
    return {
        "collected_fields": {
            "product_name": "降噪耳机",
            "purpose": "学习",
            "expected_usage_frequency": "每天",
            "owned_alternatives": "普通耳机",
            "trigger_reason": "刚需",
        },
        "rag_evidence": [],
        "tool_results": [],
    }


def test_no_deepseek_api_key_uses_mock(monkeypatch: Any) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    client = llm_client.get_llm_client()
    response = client.complete_json("pro_agent", sample_payload())

    assert isinstance(client, llm_client.MockLLMClient)
    assert response["summary"]
    assert isinstance(response["arguments"], list)
    assert isinstance(response["confidence"], float)


def test_get_llm_client_uses_deepseek_when_key_exists(monkeypatch: Any) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

    client = llm_client.get_llm_client()

    assert isinstance(client, llm_client.DeepSeekLLMClient)
    assert client.model == "deepseek-flash"
    assert client.base_url == "https://api.deepseek.com"


def test_api_exception_falls_back_to_mock(monkeypatch: Any) -> None:
    client = llm_client.DeepSeekLLMClient(api_key="test-key")

    def raise_error(task: str, payload: dict[str, Any]) -> str:
        raise RuntimeError("network down")

    monkeypatch.setattr(client, "_request_completion", raise_error)

    response = client.complete_json("con_agent", sample_payload())

    assert response["summary"].startswith("降噪耳机")
    assert isinstance(response["arguments"], list)
    assert response["confidence"] == 0.78


def test_api_timeout_falls_back_to_mock(monkeypatch: Any) -> None:
    client = llm_client.DeepSeekLLMClient(api_key="test-key")

    def raise_timeout(task: str, payload: dict[str, Any]) -> str:
        raise TimeoutError("request timed out")

    monkeypatch.setattr(client, "_request_completion", raise_timeout)

    response = client.complete_json("pro_agent", sample_payload())

    assert "降噪耳机" in response["summary"]
    assert response["confidence"] == 0.7


def test_non_json_response_falls_back_to_mock(monkeypatch: Any) -> None:
    client = llm_client.DeepSeekLLMClient(api_key="test-key")
    monkeypatch.setattr(client, "_request_completion", lambda task, payload: "not json")

    response = client.complete_json("pro_agent", sample_payload())

    assert "降噪耳机" in response["summary"]
    assert response["confidence"] == 0.7


def test_missing_summary_falls_back_to_mock(monkeypatch: Any) -> None:
    client = llm_client.DeepSeekLLMClient(api_key="test-key")
    raw = json.dumps({"arguments": ["理由"], "confidence": 0.6}, ensure_ascii=False)
    monkeypatch.setattr(client, "_request_completion", lambda task, payload: raw)

    response = client.complete_json("pro_agent", sample_payload())

    assert "降噪耳机" in response["summary"]
    assert response["confidence"] == 0.7


def test_missing_arguments_falls_back_to_mock(monkeypatch: Any) -> None:
    client = llm_client.DeepSeekLLMClient(api_key="test-key")
    raw = json.dumps({"summary": "摘要", "confidence": 0.6}, ensure_ascii=False)
    monkeypatch.setattr(client, "_request_completion", lambda task, payload: raw)

    response = client.complete_json("con_agent", sample_payload())

    assert response["confidence"] == 0.78
    assert isinstance(response["arguments"], list)


def test_missing_confidence_falls_back_to_mock(monkeypatch: Any) -> None:
    client = llm_client.DeepSeekLLMClient(api_key="test-key")
    raw = json.dumps({"summary": "摘要", "arguments": ["理由"]}, ensure_ascii=False)
    monkeypatch.setattr(client, "_request_completion", lambda task, payload: raw)

    response = client.complete_json("pro_agent", sample_payload())

    assert response["confidence"] == 0.7


def test_arguments_not_list_falls_back_to_mock(monkeypatch: Any) -> None:
    client = llm_client.DeepSeekLLMClient(api_key="test-key")
    raw = json.dumps({"summary": "摘要", "arguments": "理由", "confidence": 0.6}, ensure_ascii=False)
    monkeypatch.setattr(client, "_request_completion", lambda task, payload: raw)

    response = client.complete_json("con_agent", sample_payload())

    assert isinstance(response["arguments"], list)
    assert response["confidence"] == 0.78


def test_invalid_confidence_falls_back_to_mock(monkeypatch: Any) -> None:
    client = llm_client.DeepSeekLLMClient(api_key="test-key")
    raw = json.dumps({"summary": "摘要", "arguments": ["理由"], "confidence": "bad"}, ensure_ascii=False)
    monkeypatch.setattr(client, "_request_completion", lambda task, payload: raw)

    response = client.complete_json("pro_agent", sample_payload())

    assert response["confidence"] == 0.7


def test_valid_json_response_is_parsed(monkeypatch: Any) -> None:
    client = llm_client.DeepSeekLLMClient(api_key="test-key")
    raw = json.dumps(
        {
            "summary": "这是 DeepSeek 返回的结构化摘要。",
            "arguments": ["理由一", "理由二"],
            "confidence": "0.82",
        },
        ensure_ascii=False,
    )
    monkeypatch.setattr(client, "_request_completion", lambda task, payload: raw)

    response = client.complete_json("pro_agent", sample_payload())

    assert response == {
        "summary": "这是 DeepSeek 返回的结构化摘要。",
        "arguments": ["理由一", "理由二"],
        "confidence": 0.82,
    }


def test_request_body_uses_fixed_deepseek_v4_flash_model(monkeypatch: Any) -> None:
    captured: dict[str, Any] = {}

    class FakeResponse:
        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, *args: Any) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps(
                {
                    "choices": [
                        {
                            "message": {
                                "content": "{\"summary\":\"ok\",\"arguments\":[\"a\"],\"confidence\":0.5}"
                            }
                        }
                    ]
                }
            ).encode("utf-8")

    def fake_urlopen(request: Any, timeout: int) -> FakeResponse:
        captured["timeout"] = timeout
        captured["body"] = json.loads(request.data.decode("utf-8"))
        captured["authorization"] = request.headers["Authorization"]
        return FakeResponse()

    monkeypatch.setattr(llm_client, "urlopen", fake_urlopen)

    client = llm_client.DeepSeekLLMClient(api_key="test-key")
    raw = client._request_completion("pro_agent", sample_payload())

    assert json.loads(raw) == {"summary": "ok", "arguments": ["a"], "confidence": 0.5}
    assert captured["body"]["model"] == "deepseek-flash"
    assert captured["timeout"] == 120          # pro_agent 属辩论阶段，开启思考后超时放宽
    assert captured["authorization"] == "Bearer test-key"


def test_prompt_contains_output_constraints() -> None:
    prompt = llm_client._build_system_prompt("pro_agent")

    assert "只输出一个 JSON 对象" in prompt
    assert "不能输出 Markdown 代码块" in prompt
    assert "输出必须使用简体中文" in prompt
    assert "如果 RAG 证据为空，不得编造历史证据" in prompt


def test_judge_prompt_keeps_fixed_decision_and_debate_context() -> None:
    system_prompt = llm_client._build_system_prompt("judge_agent")
    user_prompt = llm_client._build_user_prompt(
        "judge_agent",
        {
            **sample_payload(),
            "final_decision": "delay",
            "pro_agent_result": {"summary": "支持购买", "arguments": ["用途明确"]},
            "con_agent_result": {"summary": "建议谨慎", "arguments": ["预算压力"]},
        },
    )
    prompt_data = json.loads(user_prompt)

    assert "只能解释该结果" in system_prompt
    assert prompt_data["final_decision"] == "delay"
    assert prompt_data["pro_agent_result"]["summary"] == "支持购买"
    assert prompt_data["con_agent_result"]["summary"] == "建议谨慎"


def test_judge_prompt_document_uses_rag_evidence_placeholder() -> None:
    from pathlib import Path

    prompt_path = Path(__file__).parents[1] / "backend" / "app" / "prompts" / "judge_agent.md"
    prompt = prompt_path.read_text(encoding="utf-8")

    assert "{{rag_evidence}}" in prompt
    assert "{{rag_results}}" not in prompt


def test_user_prompt_keeps_rag_and_failed_tool_details() -> None:
    payload = sample_payload()
    payload["rag_evidence"] = [
        {
            "id": "history_001",
            "title": "历史闲置记录",
            "content": "用户曾购买同类电子产品后闲置。",
            "tags": ["idle", "regret"],
        }
    ]
    payload["tool_results"] = [
        {
            "tool_name": "cooling_reminder",
            "status": "failed",
            "summary": "冷静期提醒创建失败。",
            "risk_level": None,
            "metrics": {},
            "error": "REMINDER_CREATE_FAILED",
        }
    ]

    prompt = llm_client._build_user_prompt("con_agent", payload)
    prompt_data = json.loads(prompt)

    assert prompt_data["rag_evidence"][0]["content"] == "用户曾购买同类电子产品后闲置。"
    assert prompt_data["tool_results"][0]["status"] == "failed"
    assert prompt_data["tool_results"][0]["error"] == "REMINDER_CREATE_FAILED"


def test_parser_result_is_validated() -> None:
    raw = json.dumps(
        {
            "case_type": "shopping",
            "is_supported": True,
            "is_high_risk": False,
            "reject_reason": None,
            "extracted_fields": {"price": "999"},
            "correction_fields": {},
            "next_question": "还剩多少预算？",
            "confidence": 0.9,
        },
        ensure_ascii=False,
    )
    result = llm_client._validate_parser_result(json.loads(raw))

    assert result["extracted_fields"]["price"] == 999.0
    assert result["next_question"] == "还剩多少预算？"


def test_parser_result_rejects_unknown_field() -> None:
    value = {
        "case_type": "shopping",
        "is_high_risk": False,
        "extracted_fields": {"unknown": "value"},
        "correction_fields": {},
        "confidence": 0.9,
    }

    try:
        llm_client._validate_parser_result(value)
    except ValueError:
        pass
    else:
        raise AssertionError("unknown parser field should fail validation")


def test_parser_result_requires_all_top_level_fields() -> None:
    value = {
        "case_type": "shopping",
        "is_supported": True,
        "is_high_risk": False,
        "reject_reason": None,
        "extracted_fields": {},
        "correction_fields": {},
        "next_question": None,
    }

    try:
        llm_client._validate_parser_result(value)
    except ValueError:
        pass
    else:
        raise AssertionError("missing confidence should fail validation")


def test_parser_result_derives_missing_is_supported() -> None:
    value = {
        "case_type": "shopping",
        "is_high_risk": False,
        "reject_reason": None,
        "extracted_fields": {},
        "correction_fields": {},
        "next_question": None,
        "confidence": 0.9,
    }

    result = llm_client._validate_parser_result(value)

    assert result["is_supported"] is True


def test_parser_result_rejects_inconsistent_supported_case_type() -> None:
    value = {
        "case_type": None,
        "is_supported": True,
        "is_high_risk": False,
        "reject_reason": None,
        "extracted_fields": {},
        "correction_fields": {},
        "next_question": None,
        "confidence": 0.9,
    }

    try:
        llm_client._validate_parser_result(value)
    except ValueError:
        pass
    else:
        raise AssertionError("supported parser result must require shopping case_type")


def test_parser_result_rejects_non_object_fields() -> None:
    base = {
        "case_type": "shopping",
        "is_supported": True,
        "is_high_risk": False,
        "reject_reason": None,
        "extracted_fields": {},
        "correction_fields": {},
        "next_question": None,
        "confidence": 0.9,
    }

    for invalid in (
        {**base, "extracted_fields": []},
        {**base, "extracted_fields": "not an object"},
        {**base, "correction_fields": []},
    ):
        try:
            llm_client._validate_parser_result(invalid)
        except ValueError:
            continue
        raise AssertionError("non-object parser fields should fail validation")


def test_timeout_can_be_configured(monkeypatch: Any) -> None:
    monkeypatch.setenv("DEEPSEEK_TIMEOUT_SECONDS", "45")

    client = llm_client.DeepSeekLLMClient(api_key="test-key")

    assert client.timeout_seconds == 45


def test_input_parser_request_disables_thinking(monkeypatch: Any) -> None:
    """收集阶段必须关闭思考模式（官方文档：思考默认开启，会拖慢延迟并吃掉输出额度）。"""
    client = llm_client.DeepSeekLLMClient(api_key="test-key")
    captured: dict[str, Any] = {}

    class FakeResponse:
        def read(self) -> bytes:
            return b'{"choices":[{"message":{"content":"{}"}}]}'

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

    def fake_urlopen(request, timeout):
        captured["body"] = json.loads(request.data.decode("utf-8"))
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(llm_client, "urlopen", fake_urlopen)

    client._request_completion("input_parser", {"current_message": "价格是2500元"})

    assert captured["body"]["thinking"] == {"type": "disabled"}
    assert "reasoning_effort" not in captured["body"]
    assert captured["timeout"] == 30


def test_debate_request_uses_max_reasoning_effort(monkeypatch: Any) -> None:
    """辩论/判决阶段开启思考并给足输出额度（思维链 token 计入 max_tokens）。"""
    client = llm_client.DeepSeekLLMClient(api_key="test-key")
    captured: dict[str, Any] = {}

    class FakeResponse:
        def read(self) -> bytes:
            return b'{"choices":[{"message":{"content":"{}"}}]}'

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

    def fake_urlopen(request, timeout):
        captured["body"] = json.loads(request.data.decode("utf-8"))
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(llm_client, "urlopen", fake_urlopen)

    client._request_completion("judge_agent", {"collected_fields": {}})

    assert captured["body"]["reasoning_effort"] == "max"
    assert captured["body"]["max_tokens"] >= 4096
    assert captured["timeout"] == 120


def test_parser_result_drops_invalid_amounts_instead_of_failing_turn() -> None:
    """单个金额非法时只丢弃该字段（字段级降级），不再让整轮解析作废。"""
    base = {
        "case_type": "shopping",
        "is_supported": True,
        "is_high_risk": False,
        "reject_reason": None,
        "extracted_fields": {},
        "correction_fields": {},
        "next_question": None,
        "confidence": 0.9,
    }

    for invalid in (
        {**base, "extracted_fields": {"price": "面议"}},
        {**base, "extracted_fields": {"price": -1}},
        {**base, "extracted_fields": {"price": True}},
    ):
        result = llm_client._validate_parser_result(invalid)
        assert "price" not in result["extracted_fields"]


def test_parser_result_rejects_invalid_confidence() -> None:
    value = {
        "case_type": "shopping",
        "is_supported": True,
        "is_high_risk": False,
        "reject_reason": None,
        "extracted_fields": {"price": 100},
        "correction_fields": {},
        "next_question": None,
        "confidence": 2,
    }
    try:
        llm_client._validate_parser_result(value)
    except ValueError:
        return
    raise AssertionError("out-of-range confidence should fail validation")


def test_parser_validation_does_not_mutate_input() -> None:
    value = {
        "case_type": "shopping",
        "is_supported": True,
        "is_high_risk": False,
        "reject_reason": None,
        "extracted_fields": {"price": "999"},
        "correction_fields": {},
        "next_question": None,
        "confidence": 0.9,
    }

    result = llm_client._validate_parser_result(value)

    assert value["extracted_fields"]["price"] == "999"
    assert result["extracted_fields"]["price"] == 999.0


def test_parser_validation_accepts_optional_c_metadata() -> None:
    value = {
        "case_type": "shopping",
        "is_supported": True,
        "is_high_risk": False,
        "reject_reason": None,
        "extracted_fields": {"price": 2500},
        "correction_fields": {},
        "next_question": "请补充预算。",
        "confidence": 0.9,
        "field_meta": {"price": {"status": "confirmed"}},
        "conflicts": [],
        "next_question_key": "monthly_budget_left",
        "is_complete": False,
        "termination_reason": "missing_required_fields",
        "parser_used": "deepseek",
    }
    result = llm_client._validate_parser_result(value)
    assert result["field_meta"]["price"]["status"] == "confirmed"
    assert result["next_question_key"] == "monthly_budget_left"


# ==================== T08：真实 API 降级必须可观测，不得冒充模型观点 ====================

def _raising_client(monkeypatch: Any) -> tuple[Any, dict[str, int]]:
    """返回一个"真实 API 永远失败"的 DeepSeek 客户端，并记录请求次数。"""
    client = llm_client.DeepSeekLLMClient(api_key="test-key")
    calls = {"n": 0}

    def boom(task: str, payload: dict[str, Any]) -> str:
        calls["n"] += 1
        raise RuntimeError("network down")

    monkeypatch.setattr(client, "_request_completion", boom)
    return client, calls


def test_degraded_response_is_marked_and_retried_once(monkeypatch: Any) -> None:
    """失败先重试一次，仍失败则返回兜底内容 + 降级标记（不能再"静默"）。"""
    client, calls = _raising_client(monkeypatch)
    response = client.complete_json("pro_agent", sample_payload())
    assert calls["n"] == 2
    assert response[llm_client.DEGRADED_REASON_KEY].startswith("RuntimeError: network down")
    assert response["arguments"]           # 兜底内容仍返回，离线路径不变


def test_degraded_debate_agents_do_not_disguise_mock_as_arguments(monkeypatch: Any) -> None:
    """真实 API 失败时，正方/反方不得把 mock 模板当成模型论点（真实事故：判决书里出现模板句）。"""
    from backend.app.agents import con_agent, pro_agent

    client, _ = _raising_client(monkeypatch)
    monkeypatch.setattr(pro_agent, "get_llm_client", lambda: client)
    monkeypatch.setattr(con_agent, "get_llm_client", lambda: client)

    pro = pro_agent.run_pro_agent("case_x", {"product_name": "耳机"}, [], [])
    con = con_agent.run_con_agent("case_x", {"product_name": "耳机"}, [], [])

    for step in (pro, con):
        assert step.status == "failed"
        assert step.error is not None and step.error.startswith("llm_degraded:")
        assert step.arguments == []                       # 不拿模板句填空
        assert "未能生成" in step.summary


def test_judge_uses_local_fallback_when_model_degraded(monkeypatch: Any) -> None:
    """法官说明在降级时走本地兜底，绝不能把 mock 文案写成判决理由。"""
    from backend.app.agents import judge_agent
    from backend.app.schemas.decision import AgentStep

    client, _ = _raising_client(monkeypatch)
    monkeypatch.setattr(judge_agent, "get_llm_client", lambda: client)

    step = AgentStep(agent="pro_agent", status="completed", summary="支持", confidence=0.7, arguments=["a"])
    out = judge_agent._generate_judge_explanation(
        final_decision="delay",
        collected_fields={"product_name": "耳机"},
        pro_step=step,
        con_step=step,
        rag_evidence=[],
        tool_results=[],
        fallback_summary="本地兜底说明",
        fallback_arguments=["本地兜底论点"],
    )
    assert out["summary"] == "本地兜底说明"
    assert out["arguments"] == ["本地兜底论点"]


def test_historical_description_is_labeled_for_debate_context() -> None:
    """用户最先说的话只作为"历史信息"进入辩论上下文，避免模型拿旧数字构造矛盾。"""
    view = llm_client.debate_context_fields(
        {"product_name": "猫粮", "quantity": 2, "description": "猫粮，一袋80，想买3袋"}
    )
    assert "description" not in view
    labeled = next(k for k in view if k.startswith("原始描述"))
    assert view[labeled] == "猫粮，一袋80，想买3袋"   # 原话仍可用，但明确标注可能已过时
    assert view["quantity"] == 2                     # 结构化字段才是权威值


def test_debate_system_prompt_declares_field_authority() -> None:
    """提示词层再兜一层：数值以结构化字段为准，不得用原始描述里的旧数字构造矛盾。"""
    for task in ("pro_agent", "con_agent", "judge_agent"):
        prompt = llm_client._build_system_prompt(task)
        assert "权威状态" in prompt
        assert "不得用原始描述里的旧数字" in prompt


def test_judge_step_marks_degradation(monkeypatch: Any) -> None:
    """法官说明降级时，steps[].error 必须带上 llm_degraded（运维/验收要能看出这次不是模型写的）。"""
    from backend.app.agents import judge_agent
    from backend.app.schemas.decision import AgentStep, ToolResult

    client, _ = _raising_client(monkeypatch)
    monkeypatch.setattr(judge_agent, "get_llm_client", lambda: client)

    step = AgentStep(agent="pro_agent", status="completed", summary="支持", confidence=0.7, arguments=["a"])
    cost = ToolResult(tool_name="cost_analyzer", status="success", summary="占预算 20%。",
                      risk_level="medium", metrics={"budget_ratio": 0.2, "budget_left_after_purchase": 800})
    judge_step, report = judge_agent.run_judge_agent(
        case_id="case_degraded",
        collected_fields={"product_name": "耳机", "price": 200, "monthly_budget_left": 1000},
        pro_step=step,
        con_step=step,
        rag_evidence=[],
        tool_results=[cost],
    )
    assert judge_step.error is not None and judge_step.error.startswith("llm_degraded:")
    assert report.summary                     # 本地规则说明兜底，判决书段落不为空


def test_parser_prompt_defines_alternative_coverage_by_function() -> None:
    """`covers_core_need` 的判定口径必须写清（否则"还能用但想换新"会被判成覆盖不了，R2 永不生效）。

    真实复验：同一句"旧的没坏，就是想换个新的"，旧提示词下模型给 false（判决 delay），
    补齐口径后稳定给 true（判决 alternative）。这里把口径固定住，防止提示词被改回去。
    """
    prompt = llm_client._build_system_prompt("input_parser")
    assert "【功能上是否还能用】" in prompt
    assert "还能用" in prompt and "没坏" in prompt          # true 侧例子
    assert "坏了" in prompt and "鼓包" in prompt            # false 侧例子
    assert "不要用“用户想换新”当作覆盖不了的理由" in prompt


# ==================== confidence 容错（真实事故：模型写 "0.85（较高）"） ====================

def test_confidence_accepts_messy_but_parseable_forms() -> None:
    for raw, expected in ((0.85, 0.85), ("0.85", 0.85), ("0.85（较高）", 0.85),
                          ("85%", 0.85), ("置信度 0.7 左右", 0.7), (1, 1.0)):
        out = llm_client._validate_llm_result(
            {"summary": "支持", "arguments": ["a"], "confidence": raw}
        )
        assert abs(out["confidence"] - expected) < 1e-9, (raw, out["confidence"])


def test_confidence_still_rejects_unparseable_values() -> None:
    for raw in (True, None, "很高", "", float("nan")):
        with pytest.raises(ValueError):
            llm_client._validate_llm_result({"summary": "支持", "arguments": ["a"], "confidence": raw})
