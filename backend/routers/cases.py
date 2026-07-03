# backend/routers/cases.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
import uuid
from ..database import get_db
from ..models import Case
from ..schemas import CreateCaseRequest, CreateCaseResponse, ApiResponse, CaseStatus

router = APIRouter(prefix="/api", tags=["cases"])

@router.post("/cases", response_model=ApiResponse)
def create_case(req: CreateCaseRequest, db: Session = Depends(get_db)):
    # 生成 case_id
    case_id = f"case_{uuid.uuid4().hex[:8]}"

    # 判断缺失字段
    missing_fields = []
    collected_fields = {}

    # 提取基本信息
    if req.description:
        collected_fields["description"] = req.description

    # 简单的缺失字段判断（MVP 阶段）
    if "budget" not in req.description.lower():
        missing_fields.append("monthly_budget_left")
    if "替代" not in req.description and "已有" not in req.description:
        missing_fields.append("owned_alternatives")

    status = CaseStatus.COLLECTING if missing_fields else CaseStatus.READY_FOR_DEBATE

    # 创建案件
    case = Case(
        id=case_id,
        user_id=req.user_id,
        case_type=req.case_type,
        title=req.title,
        description=req.description,
        status=status,
        collected_fields=collected_fields,
        missing_fields=missing_fields,
    )
    db.add(case)
    db.commit()
    db.refresh(case)

    next_question = None
    if missing_fields:
        if "monthly_budget_left" in missing_fields:
            next_question = "你本月预算还剩多少？"
        elif "owned_alternatives" in missing_fields:
            next_question = "是否已经有类似的替代品？"

    return ApiResponse(
        success=True,
        data=CreateCaseResponse(
            case_id=case_id,
            case_status=status,
            collected_fields=collected_fields,
            missing_fields=missing_fields,
            next_question=next_question,
        ).model_dump(),
        message="case created"
    )

@router.get("/cases/{case_id}", response_model=ApiResponse)
def get_case(case_id: str, db: Session = Depends(get_db)):
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        return ApiResponse(success=False, data=None, message="CASE_NOT_FOUND")

    return ApiResponse(
        success=True,
        data={
            "case_id": case.id,
            "user_id": case.user_id,
            "case_type": case.case_type,
            "title": case.title,
            "description": case.description,
            "case_status": case.status,
            "collected_fields": case.collected_fields or {},
            "missing_fields": case.missing_fields or [],
            "final_decision": case.final_decision,
            "report_id": case.report_id,
            "created_at": case.created_at.isoformat() if case.created_at else None,
            "updated_at": case.updated_at.isoformat() if case.updated_at else None,
        },
        message=""
    )