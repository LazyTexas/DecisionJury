# backend/routers/cases.py
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
import uuid
from datetime import datetime, timedelta, timezone
from backend.database import get_db
from backend.models import Case, Message, Reminder, History, Trace
from backend.schemas import CreateCaseRequest, CreateCaseResponse, ApiResponse, CaseStatus, CaseSummary, DecisionReportResponse, CreateFeedbackRequest, UpdateCaseRequest, SHOPPING_REQUIRED_FIELDS
from backend.app.agents.user_facing import _deep_sanitize, public_fields, public_report, public_steps
from backend.app.agents.input_parser import parse_input
from backend.app.schemas.decision import to_dict

router = APIRouter(prefix="/api", tags=["cases"])

# ========== 创建案件 ==========
@router.post("/cases", response_model=ApiResponse)
def create_case(req: CreateCaseRequest, db: Session = Depends(get_db)):
    # 生成 case_id
    case_id = f"case_{uuid.uuid4().hex[:8]}"

    # ===== 新增：从 description 中提取字段 =====
    # 防呆：若用户只填了标题而“详细描述”为空，不要交给 LLM 解析空串——
    # DeepSeek 对空输入判定不可靠，可能随机返回 case_type=null / is_supported=false，
    # 导致新建决策被误判为“不支持”而直接 rejected。空描述应视为“还需收集信息”。
    if not (req.description or "").strip():
        if req.title.strip():
            # 把标题作为商品名线索，其余字段留给后续对话收集
            initial_collected = {"product_name": req.title.strip()[:20], "description": req.description}
            initial_missing = ["price", "purpose", "monthly_budget_left", "owned_alternatives", "expected_usage_frequency", "trigger_reason"]
            is_high_risk = False
            reject_reason = ""
            initial_status = CaseStatus.COLLECTING
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
            return ApiResponse(
                success=True,
                data={
                    "case_id": case_id,
                    "case_status": case.status,
                    "collected_fields": public_fields(initial_collected),
                    "missing_fields": initial_missing,
                    "next_question": "这个大概多少钱？",
                    "is_high_risk": False,
                    "reject_reason": None,
                    "reply_plan": {
                        "ack": "",
                        "question": "这个大概多少钱？",
                        "chips": [],
                        "can_stop": False,
                        "optional": False,
                        "tone": "collecting",
                        "reply": "这个大概多少钱？",
                        "progress": {"known": ["商品"], "missing": ["价格", "剩余预算", "用途", "已有替代品", "使用频率", "购买原因"]},
                    },
                },
                message="case created"
            )

    try:
        parser_result = parse_input(
            raw_input=req.description,
            existing_collected_fields={},
            is_first_turn=True,      # 建案这一轮额外产出欢迎语（先欢迎、再收集）
        )
        parser_dict = to_dict(parser_result)
        is_high_risk = parser_dict.get("is_high_risk", False)
        reject_reason = parser_dict.get("reject_reason", "")
        initial_collected = parser_dict.get("merged_fields", {})
        initial_missing = parser_dict.get("missing_fields", [])
        initial_status = parser_dict.get("case_status", CaseStatus.COLLECTING)

        # 获取 C 模块新字段
        is_complete = parser_dict.get("is_complete", False)
        conflicts = parser_dict.get("conflicts", [])
        next_question_key = parser_dict.get("next_question_key")
        termination_reason = parser_dict.get("termination_reason", "")
        parser_used = parser_dict.get("parser_used", "")

        # 防呆：非高风险被误判为 rejected 时降级
        if not is_high_risk and initial_status == CaseStatus.REJECTED:
            initial_status = CaseStatus.COLLECTING
            # 保留已提取的字段，只补充真正缺失的字段
            required_fields = SHOPPING_REQUIRED_FIELDS.copy()
            collected_keys = set(initial_collected.keys())
            initial_missing = [f for f in required_fields if f not in collected_keys]
            initial_collected.pop("is_high_risk", None)
            initial_collected.pop("reject_reason", None)
            reject_reason = ""

        # ===== 高风险 / 完整判断 =====
        if is_high_risk:
            initial_status = CaseStatus.REJECTED
            initial_missing = []
            initial_collected["is_high_risk"] = True
            initial_collected["reject_reason"] = reject_reason
        elif is_complete:
            initial_status = CaseStatus.READY_FOR_DEBATE

        # ===== 接入新字段到 collected_fields =====
        if conflicts:
            initial_collected["_conflicts"] = conflicts
        if next_question_key:
            initial_collected["_current_question_key"] = next_question_key
        if termination_reason:
            initial_collected["_termination_reason"] = termination_reason
        if parser_used:
            initial_collected["_parser_used"] = parser_used

    except Exception as e:
        print(f"[WARN] create_case parse_input 调用失败: {e}")
        initial_collected = {}
        initial_missing = ["product_name", "price", "purpose", "monthly_budget_left", "owned_alternatives", "expected_usage_frequency", "trigger_reason"]
        initial_status = CaseStatus.COLLECTING
        is_high_risk = False
        reject_reason = ""
        parser_dict = {}

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
    if not is_high_risk and initial_missing:
        # 直接使用 C 模块返回的 next_question
        next_question = parser_dict.get("next_question")

    # ===== 建案这一轮的三条消息落库：用户描述 → 欢迎语 → 第一个问题 =====
    # 之前只有前端把首个问题塞进 localStorage，而 GET /messages 以服务端为唯一真相源，
    # 一旦有了服务端消息就会覆盖本地缓存——首个问题和欢迎语会凭空消失。
    # 时间戳用**负偏移**：消息按 created_at 升序返回（后续轮次由 server_default 取当前时间），
    # 正偏移会在用户秒回时把建案消息排到后面去（真实踩到：首问出现在第 1 轮回复之后）。
    reply_plan = parser_dict.get("reply_plan") or {}
    welcome_text = str(reply_plan.get("welcome") or "").strip()
    first_reply = str(reply_plan.get("reply") or next_question or "").strip()
    base_time = datetime.now(timezone.utc).replace(tzinfo=None)
    creation_messages = []
    if (req.description or "").strip():
        creation_messages.append(("user", req.description.strip(), "text"))
    if welcome_text:
        creation_messages.append(("assistant", welcome_text, "text"))
    if first_reply:
        creation_messages.append(("assistant", first_reply, "question"))
    for offset, (role, content, msg_type) in enumerate(creation_messages):
        db.add(
            Message(
                id=f"msg_{uuid.uuid4().hex[:8]}",
                case_id=case_id,
                role=role,
                content=content,
                message_type=msg_type,
                created_at=base_time - timedelta(seconds=len(creation_messages) - offset),
            )
        )
    if creation_messages:
        db.commit()

    return ApiResponse(
        success=True,
        data={
            "case_id": case_id,
            "case_status": case.status,
            "collected_fields": public_fields(initial_collected),
            "missing_fields": initial_missing,
            "next_question": next_question,
            "welcome": welcome_text,
            "is_high_risk": is_high_risk,
            "reject_reason": reject_reason if is_high_risk else None,
            "reply_plan": reply_plan,
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
            "collected_fields": public_fields(case.collected_fields) or {},
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

    # 类型安全：确保 debate_result 是 dict
    if not isinstance(case.debate_result, dict):
        print(f"[WARN] debate_result 格式异常: {type(case.debate_result)}")
        return ApiResponse(success=False, data=None, message="REPORT_DATA_CORRUPTED")
    
    # 3. 从 debate_result 中提取 report 和 debate_events
    # 安全提取 report，确保是 dict
    report_data = _deep_sanitize(public_report(case.debate_result.get("report") or {}))
    if not isinstance(report_data, dict):
        report_data = {}

    # 安全提取 debate_events，确保是 list
    debate_events = _deep_sanitize(case.debate_result.get("debate_events") or [])
    if not isinstance(debate_events, list):
        debate_events = []

    if not report_data:
        return ApiResponse(success=False, data=None, message="REPORT_NOT_FOUND")

    return ApiResponse(
        success=True,
        data={
            **report_data,
            "debate_events": debate_events
        },
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
            "collected_fields": public_fields(case.collected_fields) or {},
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

    # 4. 创建/更新历史记录（同一案件只保留一条复盘记录，重复提交则更新）
    # 保证幂等：避免用户反复点击"提交决策复盘"时反复插入相同案件的历史记录。
    history = db.query(History).filter(
        History.case_id == case.id,
        History.is_deleted == 0,
    ).first()

    if history:
        # 已存在复盘记录 → 更新内容
        history.user_id = req.user_id
        history.case_type = case.case_type
        history.summary = f"用户复盘：{case.title}，实际行为：{req.actual_action}，满意度：{req.satisfaction}★"
        history.result = result
        history.title = case.title
        history.report_id = case.report_id
        history.context = req.review or ""
        history.final_decision = case.final_decision
    else:
        # 尚无复盘记录 → 新建
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

# ========== 删除案件 ==========
@router.delete("/cases/{case_id}", response_model=ApiResponse)
def delete_case(
    case_id: str,
    user_id: str = Query(..., description="用户 ID"),
    db: Session = Depends(get_db)
):
    """
    删除案件。
    - messages/traces/reminders 因外键 CASCADE 自动级联删除
    - histories 记录软删除（is_deleted=1，RAG 仍可检索，case_id/report_id 保留）
    """
    # 1. 查询案件
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        return ApiResponse(
            success=False,
            data=None,
            message="CASE_NOT_FOUND"
        )

    # 2. 权限校验
    if case.user_id != user_id:
        return ApiResponse(
            success=False,
            data=None,
            message="FORBIDDEN"
        )
    
    # 3. 软删除关联的历史记录（保留 case_id 和 report_id，RAG 仍可检索）
    db.query(History).filter(History.case_id == case_id).update({
        "is_deleted": 1,
    })

    # 4. 删除案件（messages/traces/reminders 因外键 CASCADE 自动删除）
    db.delete(case)
    db.commit()

    return ApiResponse(
        success=True,
        data={"deleted": True},
        message=""
    )