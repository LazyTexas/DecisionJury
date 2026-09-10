# backend/routers/debate.py
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from datetime import datetime
import uuid
from typing import Optional
from backend.database import get_db
from backend.models import Case, Trace, Reminder, User
from backend.schemas import ApiResponse, CaseStatus, DebateRequest
from backend.app.orchestrator.adapter import run_case_decision_flow
from backend.security import get_current_user_optional

router = APIRouter(prefix="/api", tags=["debate"])


@router.post("/cases/{case_id}/debate", response_model=ApiResponse)
def start_debate(
    case_id: str,
    req: DebateRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    # ===== 获取有效用户 ID（Token 优先）=====
    effective_user_id = current_user.id if current_user else req.user_id
    if not effective_user_id:
        return ApiResponse(success=False, data=None, message="MISSING_USER_ID")

    # 1. 查询案件
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        return ApiResponse(success=False, data=None, message="CASE_NOT_FOUND")

    # 2. 权限校验
    if effective_user_id != case.user_id:
        return ApiResponse(success=False, data=None, message="FORBIDDEN")

    # 3. 检查状态
    if case.status == CaseStatus.REJECTED:
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
        # ===== 修复：从 `_next_question` 读取（而不是 `next_question`）=====
        collected = case.collected_fields or {}
        next_question = collected.get("_next_question")   # ← 修复
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

    # 4. 更新状态为 debating
    case.status = CaseStatus.DEBATING
    db.commit()

    # 5. 调用 C 模块
    result = run_case_decision_flow(
        case_id=case.id,
        user_id=case.user_id,
        case_type=case.case_type,
        description=case.description,
        collected_fields=case.collected_fields or {},
    )

    # 6. 根据结果更新案件状态
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
        # 7. 更新案件状态
        case.status = CaseStatus.COMPLETED
        if result.get("report", {}).get("final_decision"):
            case.final_decision = result["report"]["final_decision"]
        if result.get("report", {}).get("report_id"):
            case.report_id = result["report"]["report_id"]

        # ===== 保存完整辩论结果 =====
        case.debate_result = result

        # 8. 保存 trace
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

        # 9. 保存 Reminder
        tool_results = result.get("tool_results", [])
        for tool in tool_results:
            if tool.get("tool_name") == "cooling_reminder" and tool.get("status") == "success":
                metrics = tool.get("metrics", {})
                reminder = Reminder(
                    id=metrics.get("reminder_id", f"reminder_{uuid.uuid4().hex[:8]}"),
                    user_id=case.user_id,
                    case_id=case.id,
                    title=metrics.get("title", case.title),
                    reason=metrics.get("reason", ""),
                    due_at=datetime.fromisoformat(metrics.get("due_at")) if metrics.get("due_at") else None,
                    status="waiting"
                )
                db.add(reminder)
                break

        db.commit()

        return ApiResponse(
            success=True,
            data={
                "case_id": case_id,
                "case_status": CaseStatus.COMPLETED,
                "steps": result.get("steps", []),
                "rag_evidence": result.get("rag_evidence", []),
                "tool_results": result.get("tool_results", []),
                "report": result.get("report", {}),
                "debate_events": result.get("debate_events", []),
            },
            message="debate completed"
        )

    # 10. 其他失败情况
    return ApiResponse(
        success=False,
        data=None,
        message=result.get("message", "DEBATE_FAILED")
    )


@router.get("/cases/{case_id}/trace", response_model=ApiResponse)
def get_trace(
    case_id: str,
    user_id: Optional[str] = Query(None, description="用户 ID（可选，有 Token 时忽略）"),
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """
    获取 Agent 执行轨迹
    """
    # ===== 获取有效用户 ID（Token 优先）=====
    effective_user_id = current_user.id if current_user else user_id
    if not effective_user_id:
        return ApiResponse(success=False, data=None, message="MISSING_USER_ID")

    # 1. 检查案件是否存在
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        return ApiResponse(
            success=False,
            data=None,
            message="CASE_NOT_FOUND"
        )

    # 2. 权限校验
    if case.user_id != effective_user_id:
        return ApiResponse(
            success=False,
            data=None,
            message="FORBIDDEN"
        )

    # 3. 查询 trace
    traces = db.query(Trace).filter(Trace.case_id == case_id).order_by(Trace.step).all()

    # 4. 组装返回数据
    return ApiResponse(
        success=True,
        data={
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
        },
        message=""
    )