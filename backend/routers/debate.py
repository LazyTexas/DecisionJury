# backend/routers/debate.py
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import Optional
from backend.app.agents.user_facing import _deep_sanitize, public_report, public_steps
from backend.database import SessionLocal, get_db
from backend.models import Case, Trace, Reminder, User
from backend.schemas import ApiResponse, CaseStatus, DebateRequest
from backend.app.orchestrator.adapter import run_case_decision_flow
from datetime import datetime
import copy
import json
import queue
import threading
import uuid
# JWT 身份（保留 dev 的认证接线）：Token 优先，其次回退请求体里的 user_id
from backend.security import get_current_user_optional

router = APIRouter(prefix="/api", tags=["debate"])

@router.post("/cases/{case_id}/debate", response_model=ApiResponse)
def start_debate(
    case_id: str,
    req: DebateRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    effective_user_id = current_user.id if current_user else req.user_id
    if not effective_user_id:
        return ApiResponse(success=False, data=None, message="MISSING_USER_ID")
    # 1. 查询案件
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        return ApiResponse(success=False, data=None, message="CASE_NOT_FOUND")

    # 校验归属
    if effective_user_id != case.user_id:
        return ApiResponse(success=False, data=None, message="FORBIDDEN")
    
    return _run_debate_core(db, case, case_id)


def _run_debate_core(db: Session, case: Case, case_id: str, progress=None) -> ApiResponse:
    """执行辩论并落库；/debate 与 /debate/stream 共用这一段，便于 SSE 推送进度。"""
    # 2. 检查状态
    if case.status == CaseStatus.REJECTED:
        # 从 collected_fields 获取拒绝原因
        collected = case.collected_fields or {}
        reject_reason = collected.get("reject_reason", "该决策超出系统支持范围。")
        return ApiResponse(
            success=False,
            data={
                "case_status": CaseStatus.REJECTED,
                "is_high_risk": True,
                "reject_reason": reject_reason,
            },
            message="HIGH_RISK_DECISION"
        )

    if case.status != CaseStatus.READY_FOR_DEBATE:
        # 从 collected_fields 获取缓存的 next_question
        collected = case.collected_fields or {}
        next_question = collected.get("next_question")
        if not next_question:
            next_question = "请继续补充以下信息" if case.missing_fields else None
        return ApiResponse(
            success=False,
            data={
                "case_status": case.status,
                "missing_fields": case.missing_fields or [],
                "next_question": next_question,
            },
            message="MISSING_FIELDS"
        )
    
    # 3. 更新状态为 debating
    case.status = CaseStatus.DEBATING
    db.commit()

    # 4. 调用 C 模块
    result = run_case_decision_flow(
        case_id=case.id,
        user_id=case.user_id,
        case_type=case.case_type,
        description=case.description,
        collected_fields=case.collected_fields or {},
        progress=progress,
    )

    # 5. 根据结果更新案件状态
    if result.get("message") == "MISSING_FIELDS":
        case.status = CaseStatus.COLLECTING
        db.commit()
        return ApiResponse(
            success=False,
            data={
                "case_status": CaseStatus.COLLECTING,
                "missing_fields": case.missing_fields,
                "next_question": result.get("reason"),
            },
            message="MISSING_FIELDS"
        )

    if result.get("message") == "HIGH_RISK_DECISION":
        case.status = CaseStatus.REJECTED
        db.commit()
        return ApiResponse(success=False, data=None, message="HIGH_RISK_DECISION")

    if result.get("success"):
        # 6. 更新案件状态
        case.status = CaseStatus.COMPLETED
        if result.get("report", {}).get("final_decision"):
            case.final_decision = result["report"]["final_decision"]
        if result.get("report", {}).get("report_id"):
            case.report_id = result["report"]["report_id"]

        # ===== 保存完整辩论结果（存清洗后的副本，避免任何读取路径泄漏内部术语） =====
        clean_result = copy.deepcopy(result)
        clean_result["report"] = _deep_sanitize(public_report(clean_result.get("report", {})))
        clean_result["steps"] = _deep_sanitize(public_steps(clean_result.get("steps", [])))
        for _key in ("debate_events", "rag_evidence"):
            clean_result[_key] = _deep_sanitize(clean_result.get(_key, []))
        case.debate_result = clean_result
        
        # 7. 保存 trace
        trace_data = result.get("trace", [])
        for step in trace_data:
            trace = Trace(
                id=f"trace_{uuid.uuid4().hex[:8]}",
                case_id=case_id,
                step=step.get("step", 0),
                type=step.get("type", "agent"),
                name=step.get("name", "unknown"),
                input_summary=step.get("input_summary", ""),
                output_summary=step.get("output_summary", ""),
                duration_ms=step.get("duration_ms"),
                status=step.get("status", "completed"),
                error=step.get("error"),
            )
            db.add(trace)

        # 保存 Reminder
        tool_results = result.get("tool_results", [])
        for tool in tool_results:
            if tool.get("tool_name") == "cooling_reminder" and tool.get("status") == "success":
                metrics = tool.get("metrics", {})
                # 从 metrics 中提取字段
                reminder = Reminder(
                    id=metrics.get("reminder_id", f"reminder_{uuid.uuid4().hex[:8]}"),
                    user_id=case.user_id,
                    case_id=case.id,
                    title=metrics.get("title", case.title),        # C 的 PR #86 已加
                    reason=metrics.get("reason", ""),              # C 的 PR #86 已加
                    due_at=datetime.fromisoformat(metrics.get("due_at")) if metrics.get("due_at") else None,
                    status="waiting"
                )
                db.add(reminder)
                break  # 只有一个 cooling_reminder

        db.commit()
        # ===== 保存 trace 结束 =====

        return ApiResponse(
            success=True,
            data=_deep_sanitize({
                "case_id": case_id,
                "case_status": CaseStatus.COMPLETED,
                "steps": _deep_sanitize(public_steps(result.get("steps", []))),
                "rag_evidence": _deep_sanitize(result.get("rag_evidence", [])),
                "tool_results": _deep_sanitize(public_report({"tool_results": result.get("tool_results", [])})).get("tool_results", []),
                "report": _deep_sanitize(public_report(result.get("report", {}))),
                "debate_events": _deep_sanitize(result.get("debate_events", [])),
                "trace": _deep_sanitize(result.get("trace", [])),
            }),
            message="debate completed"
        )

    # 8. 其他失败情况
    return ApiResponse(
        success=False,
        data=None,
        message=result.get("message", "DEBATE_FAILED")
    )


@router.post("/cases/{case_id}/debate/stream")
def stream_debate(
    case_id: str,
    req: DebateRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """SSE 版辩论：逐阶段推送进度。

    辩论阶段开启思考后单次总耗时约 30 秒，整段等待体验很差。这里把
    "解析 → 检索 → 工具 → 正方 → 反方 → 法官" 的每个阶段实时推给前端，
    前端可以先渲染已完成的正/反方论点，而不是白等 30 秒。
    """
    effective_user_id = current_user.id if current_user else req.user_id
    if not effective_user_id:
        return ApiResponse(success=False, data=None, message="MISSING_USER_ID")
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        return ApiResponse(success=False, data=None, message="CASE_NOT_FOUND")
    if effective_user_id != case.user_id:
        return ApiResponse(success=False, data=None, message="FORBIDDEN")

    def event_stream():
        events: "queue.Queue[dict]" = queue.Queue()

        def worker() -> None:
            session = SessionLocal()
            try:
                fresh = session.query(Case).filter(Case.id == case_id).first()
                response = _run_debate_core(session, fresh, case_id, progress=events.put)
                payload = response.model_dump() if hasattr(response, "model_dump") else response.dict()
                events.put({"stage": "__done__", "response": payload})
            except Exception as exc:  # 任何异常都以事件形式告诉前端，避免连接悬挂
                events.put({"stage": "__error__", "message": f"{type(exc).__name__}: {exc}"})
            finally:
                session.close()

        threading.Thread(target=worker, daemon=True).start()
        while True:
            event = events.get()
            yield f"data: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"
            if event.get("stage") in {"__done__", "__error__"}:
                break

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

@router.get("/cases/{case_id}/trace", response_model=ApiResponse)
def get_trace(case_id: str, db: Session = Depends(get_db)):
    """
    获取 Agent 执行轨迹
    """
    # 1. 检查案件是否存在
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        return ApiResponse(
            success=False,
            data=None,
            message="CASE_NOT_FOUND"
        )

    # 2. 查询 trace
    traces = db.query(Trace).filter(Trace.case_id == case_id).order_by(Trace.step).all()

    # 3. 组装返回数据
    return ApiResponse(
        success=True,
        data=_deep_sanitize({
            "case_id": case_id,
            "trace": [
                {
                    "trace_id": t.id,
                    "step": t.step,
                    "type": t.type,
                    "name": t.name,
                    "input_summary": t.input_summary,
                    "output_summary": t.output_summary,
                    "duration_ms": t.duration_ms,
                    "status": t.status,
                    "error": t.error,
                    "created_at": t.created_at.isoformat() if t.created_at else None,
                }
                for t in traces
            ]
        }),
        message=""
    )