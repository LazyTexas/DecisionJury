from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from schemas import CreateCaseRequest, CreateCaseResponse

router = APIRouter(prefix="/api", tags=["cases"])

@router.post("/cases", response_model=CreateCaseResponse)
def create_case(req: CreateCaseRequest, db: Session = Depends(get_db)):
    # TODO: 生成 case_id，存入数据库
    return CreateCaseResponse(
        case_id="case_001",
        status="collecting",
        missing_fields=["monthly_budget_left"],
        next_question="你本月预算还剩多少？"
    )

@router.get("/cases/{case_id}")
def get_case(case_id: str, db: Session = Depends(get_db)):
    # TODO: 从数据库查询
    return {
        "success": True,
        "data": {
            "case_id": case_id,
            "title": "是否购买降噪耳机",
            "status": "collecting"
        }
    }