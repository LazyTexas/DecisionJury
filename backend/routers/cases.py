# backend/routers/cases.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
import uuid
from ..database import get_db
from ..models import Case
from ..schemas import CreateCaseRequest, CreateCaseResponse, ApiResponse, CaseStatus, CaseSummary, DecisionReportResponse

router = APIRouter(prefix="/api", tags=["cases"])

# ========== 创建案件 ==========
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

# ========== 查询案件详情 ==========
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

# ========== 案件列表 ==========
@router.get("/cases", response_model=ApiResponse)
def list_cases(
    user_id: str = Query(..., description="用户 ID"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页条数"),
    db: Session = Depends(get_db)
):
    """
    获取用户的所有案件，按更新时间倒序排列，支持分页。
    """
    # 构建基础查询
    query = db.query(Case).filter(Case.user_id == user_id)

    # 获取总数
    total = query.count()

    # 分页查询，按 updated_at 倒序
    items = query.order_by(Case.updated_at.desc()) \
                 .offset((page - 1) * page_size) \
                 .limit(page_size) \
                 .all()

    # 组装每个案件的摘要信息
    result_items = []
    for case in items:
        # 统计该案件的消息数量
        msg_count = db.query(Message).filter(Message.case_id == case.id).count()
        result_items.append(
            CaseSummary(
                case_id=case.id,
                title=case.title,
                case_type=case.case_type,
                status=case.status,
                description=case.description,
                updated_at=case.updated_at.isoformat() if case.updated_at else None,
                message_count=msg_count,
                has_report=case.report_id is not None,
            ).model_dump()
        )

    return ApiResponse(
        success=True,
        data={
            "items": result_items,
            "total": total,
            "page": page,
            "page_size": page_size,
        },
        message=""
    )


# ========== 查询判决书 ==========
@router.get("/cases/{case_id}/report", response_model=ApiResponse)
def get_report(case_id: str, db: Session = Depends(get_db)):
    """
    获取案件的判决书。
    如果案件已完成且有 report_id，则返回完整报告；否则返回错误。
    """
    # 查询案件
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        return ApiResponse(success=False, data=None, message="CASE_NOT_FOUND")

    # 检查是否有报告
    if not case.report_id:
        return ApiResponse(success=False, data=None, message="REPORT_NOT_FOUND")

    # 组装报告数据
    # MVP 阶段：报告数据从 case 表的字段生成
    report_data = DecisionReportResponse(
        report_id=case.report_id,
        case_type=case.case_type,
        final_decision=case.final_decision or "unknown",
        confidence=0.75,  # MVP 阶段固定值，后续由 C 模块提供
        summary=f"本案建议{'购买' if case.final_decision == 'buy' else '暂缓' if case.final_decision == 'delay' else '不购买'}",
        case_summary=case.description,
        pro_points=["正方观点待补充"],
        con_points=["反方观点待补充"],
        next_actions=["冷静期后复盘"],
        rag_evidence=[],
        tool_results=[],
        created_at=case.updated_at.isoformat() if case.updated_at else None,
    )

    return ApiResponse(
        success=True,
        data=report_data.model_dump(),
        message=""
    )