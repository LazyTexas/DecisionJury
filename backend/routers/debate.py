# backend/routers/debate.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import Case
from backend.schemas import ApiResponse, CaseStatus
from backend.app.orchestrator.adapter import run_case_decision_flow

router = APIRouter(prefix="/api", tags=["debate"])

@router.post("/cases/{case_id}/debate", response_model=ApiResponse)
def start_debate(case_id: str, db: Session = Depends(get_db)):
    # 1. 查询案件
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        return ApiResponse(success=False, data=None, message="CASE_NOT_FOUND")

    # 2. 检查状态
    if case.status == CaseStatus.REJECTED:
        return ApiResponse(success=False, data=None, message="HIGH_RISK_DECISION")

    if case.status != CaseStatus.READY_FOR_DEBATE:
        return ApiResponse(success=False, data=None, message="MISSING_FIELDS")

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
            },
            message="debate completed"
        )

    # 7. 其他失败情况
    return ApiResponse(
        success=False,
        data=None,
        message=result.get("message", "DEBATE_FAILED")
    )
