# backend/routers/cases.py
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
import uuid
from backend.database import get_db
from backend.models import Case, Message, Reminder, History
from backend.schemas import CreateCaseRequest, CreateCaseResponse, ApiResponse, CaseStatus, CaseSummary, DecisionReportResponse, CreateFeedbackRequest, UpdateCaseRequest
from backend.app.agents.input_parser import parse_input
from backend.app.schemas.decision import to_dict

router = APIRouter(prefix="/api", tags=["cases"])

# ========== 创建案件 ==========
@router.post("/cases", response_model=ApiResponse)
def create_case(req: CreateCaseRequest, db: Session = Depends(get_db)):
    # 生成 case_id
    case_id = f"case_{uuid.uuid4().hex[:8]}"

    # ===== 新增：从 description 中提取字段 =====
    try:
        parser_result = parse_input(
            raw_input=req.description,
            existing_collected_fields={},
        )
        parser_dict = to_dict(parser_result)
        initial_collected = parser_dict.get("extracted_fields", {})
        initial_missing = parser_dict.get("missing_fields", [])
        initial_status = parser_dict.get("case_status", CaseStatus.COLLECTING)
    except Exception as e:
        print(f"[WARN] create_case parse_input 调用失败: {e}")
        initial_collected = {}
        initial_missing = ["product_name", "price", "purpose", "monthly_budget_left", "owned_alternatives", "expected_usage_frequency", "trigger_reason"]
        initial_status = CaseStatus.COLLECTING

    # 确保 description 保留
    if "description" not in initial_collected:
        initial_collected["description"] = req.description

    # 创建案件
    case = Case(
        id=case_id,
        user_id=req.user_id,
        case_type=req.case_type,
        title=req.title,
        description=req.description,
        status=initial_status,
        collected_fields=initial_collected,
        missing_fields=initial_missing,
    )
    db.add(case)
    db.commit()
    db.refresh(case)

    # 生成追问
    next_question = None
    if initial_missing:
        # 优先使用 parse_input 返回的 next_question
        next_question = parser_dict.get("next_question") if 'parser_dict' in locals() else None
        if not next_question:
            # 后备追问
            if "monthly_budget_left" in initial_missing:
                next_question = "你本月预算还剩多少？"
            elif "owned_alternatives" in initial_missing:
                next_question = "是否已经有类似的替代品？"
            else:
                next_question = f"还需要补充以下信息：{', '.join(initial_missing)}"

    return ApiResponse(
        success=True,
        data={
            "case_id": case_id,
            "case_status": case.status,
            "collected_fields": initial_collected,
            "missing_fields": initial_missing,
            "next_question": next_question,
        },
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
    从 debate_result 中读取 C 模块生成的真实报告。
    """
    # 1. 查询案件
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        return ApiResponse(success=False, data=None, message="CASE_NOT_FOUND")

    # 2. 检查是否有辩论结果
    if not case.debate_result:
        return ApiResponse(success=False, data=None, message="REPORT_NOT_FOUND")

    # 3. 从 debate_result 中提取 report
    report_data = case.debate_result.get("report", {})
    if not report_data:
        return ApiResponse(success=False, data=None, message="REPORT_NOT_FOUND")

    return ApiResponse(
        success=True,
        data=report_data,
        message=""
    )

# ... 其他路由 ...

@router.patch("/cases/{case_id}", response_model=ApiResponse)
def update_case(
    case_id: str,
    req: UpdateCaseRequest,
    db: Session = Depends(get_db)
):
    """
    部分更新案件信息。
    只有传入的字段才会更新，未传入的字段保持不变。
    """
    # 1. 查询案件
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        return ApiResponse(
            success=False,
            data=None,
            message="CASE_NOT_FOUND"
        )

    # 2. 更新基础字段
    if req.title is not None:
        case.title = req.title

    if req.description is not None:
        case.description = req.description

    if req.user_id is not None:
        case.user_id = req.user_id

    # 3. 更新 collected_fields（合并更新，不覆盖）
    if req.collected_fields is not None:
        # 获取现有字段
        current = case.collected_fields or {}
        # 合并更新
        current.update(req.collected_fields)
        case.collected_fields = current

        # 4. 重新计算 missing_fields
        # 购物决策所需字段（与 chat.py 保持一致）
        shopping_required = [
            "product_name",
            "price",
            "purpose",
            "monthly_budget_left",
            "owned_alternatives",
            "expected_usage_frequency",
            "trigger_reason"
        ]

        if case.case_type == "shopping":
            required_fields = shopping_required
        else:
            required_fields = []

        still_missing = [
            f for f in required_fields
            if f not in case.collected_fields or case.collected_fields.get(f) in [None, ""]
        ]
        case.missing_fields = still_missing

        # 5. 更新状态
        if still_missing:
            case.status = CaseStatus.COLLECTING
        else:
            # 如果当前状态是 COLLECTING 且已无缺失字段，转为 READY_FOR_DEBATE
            if case.status == CaseStatus.COLLECTING:
                case.status = CaseStatus.READY_FOR_DEBATE

    # 6. 提交更新
    db.commit()
    db.refresh(case)

    # 7. 返回更新后的案件（与 GET /cases/{case_id} 格式一致）
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
        message="case updated"
    )

@router.post("/cases/{case_id}/feedback", response_model=ApiResponse)
def create_feedback(
    case_id: str,
    req: CreateFeedbackRequest,
    db: Session = Depends(get_db)
):
    """
    决策复盘接口
    用户对已完成决策进行复盘，反馈实际行为和满意度
    """
    # 1. 查询案件
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        return ApiResponse(success=False, data=None, message="CASE_NOT_FOUND")

    # 2. 检查案件是否已完成
    if case.status != CaseStatus.COMPLETED:
        return ApiResponse(
            success=False,
            data=None,
            message="CASE_NOT_COMPLETED"
        )

    # 3. 根据 satisfaction 映射 result
    # >= 4 → worth, <= 2 → regret, 3 → neutral
    if req.satisfaction >= 4:
        result = "worth"
    elif req.satisfaction <= 2:
        result = "regret"
    else:
        result = "neutral"

    # 4. 创建历史记录
    history = History(
        id=f"history_{uuid.uuid4().hex[:8]}",
        user_id=req.user_id,
        case_type=case.case_type,
        summary=f"用户复盘：{case.title}，实际行为：{req.actual_action}，满意度：{req.satisfaction}★",
        result=result,
        tags=[],
        title=case.title,
        case_id=case.id,
        report_id=case.report_id,
        context=req.review or "",
        final_decision=case.final_decision,
    )
    db.add(history)

    # 5. 更新观察清单状态（如果有）
    reminder = db.query(Reminder).filter(
        Reminder.case_id == case_id,
        Reminder.status == "waiting"
    ).first()
    if reminder:
        reminder.status = "reviewed"

    db.commit()

    return ApiResponse(
        success=True,
        data={
            "saved_to_history": True,
            "history_id": history.id,
        },
        message=""
    )