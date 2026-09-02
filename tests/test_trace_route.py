# tests/test_trace_router.py
"""
测试 trace 路由（GET /api/cases/{case_id}/trace）
"""

from backend.models import Trace, Case
from backend.schemas import CaseStatus


def test_get_trace_success(client, db_session):
    """查询执行轨迹成功"""
    case = Case(
        id="case_trace",
        user_id="u001",
        case_type="shopping",
        title="买耳机",
        description="想买降噪耳机",
        status=CaseStatus.COMPLETED,
        collected_fields={},
        missing_fields=[]
    )
    db_session.add(case)

    trace1 = Trace(
        id="trace_001",
        case_id="case_trace",
        step=1,
        type="agent",
        name="input_parser",
        input_summary="用户输入",
        output_summary="识别为shopping",
        duration_ms=100,
        status="completed",
        error=None
    )
    trace2 = Trace(
        id="trace_002",
        case_id="case_trace",
        step=2,
        type="rag_search",
        name="rag_search",
        input_summary="查询关键词",
        output_summary="返回3条结果",
        duration_ms=500,
        status="completed",
        error=None
    )
    db_session.add(trace1)
    db_session.add(trace2)
    db_session.commit()

    response = client.get("/api/cases/case_trace/trace")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["case_id"] == "case_trace"
    assert len(data["data"]["trace"]) == 2
    assert data["data"]["trace"][0]["step"] == 1
    assert data["data"]["trace"][0]["name"] == "input_parser"
    assert data["data"]["trace"][1]["step"] == 2
    assert data["data"]["trace"][1]["name"] == "rag_search"


def test_get_trace_sorted_by_step(client, db_session):
    """trace 按 step 升序排列"""
    case = Case(
        id="case_trace_sort",
        user_id="u001",
        case_type="shopping",
        title="买耳机",
        description="想买降噪耳机",
        status=CaseStatus.COMPLETED,
        collected_fields={},
        missing_fields=[]
    )
    db_session.add(case)

    trace1 = Trace(
        id="trace_step1",
        case_id="case_trace_sort",
        step=1,
        type="agent",
        name="input_parser",
        input_summary="",
        output_summary="",
        duration_ms=0,
        status="completed",
        error=None
    )
    trace2 = Trace(
        id="trace_step3",
        case_id="case_trace_sort",
        step=3,
        type="agent",
        name="judge_agent",
        input_summary="",
        output_summary="",
        duration_ms=0,
        status="completed",
        error=None
    )
    trace3 = Trace(
        id="trace_step2",
        case_id="case_trace_sort",
        step=2,
        type="rag_search",
        name="rag_search",
        input_summary="",
        output_summary="",
        duration_ms=0,
        status="completed",
        error=None
    )
    db_session.add(trace1)
    db_session.add(trace2)
    db_session.add(trace3)
    db_session.commit()

    response = client.get("/api/cases/case_trace_sort/trace")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    steps = [t["step"] for t in data["data"]["trace"]]
    assert steps == [1, 2, 3]


def test_get_trace_case_not_found(client):
    """案件不存在返回 CASE_NOT_FOUND"""
    response = client.get("/api/cases/case_not_exist/trace")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert data["message"] == "CASE_NOT_FOUND"


def test_get_trace_empty_for_no_traces(client, db_session):
    """案件存在但无 trace 数据时返回空列表"""
    case = Case(
        id="case_no_trace",
        user_id="u001",
        case_type="shopping",
        title="买耳机",
        description="想买降噪耳机",
        status=CaseStatus.COLLECTING,
        collected_fields={},
        missing_fields=[]
    )
    db_session.add(case)
    db_session.commit()

    response = client.get("/api/cases/case_no_trace/trace")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["case_id"] == "case_no_trace"
    assert data["data"]["trace"] == []


def test_get_trace_fields_complete(client, db_session):
    """每条 trace 包含所有必要字段"""
    case = Case(
        id="case_fields",
        user_id="u001",
        case_type="shopping",
        title="买耳机",
        description="想买降噪耳机",
        status=CaseStatus.COMPLETED,
        collected_fields={},
        missing_fields=[]
    )
    db_session.add(case)

    trace = Trace(
        id="trace_fields",
        case_id="case_fields",
        step=1,
        type="agent",
        name="input_parser",
        input_summary="输入摘要",
        output_summary="输出摘要",
        duration_ms=123,
        status="completed",
        error=None
    )
    db_session.add(trace)
    db_session.commit()

    response = client.get("/api/cases/case_fields/trace")

    assert response.status_code == 200
    data = response.json()
    trace_data = data["data"]["trace"][0]
    required_fields = ["trace_id", "step", "type", "name", "input_summary", "output_summary", "duration_ms", "status", "error", "created_at"]
    for field in required_fields:
        assert field in trace_data
    assert trace_data["duration_ms"] == 123