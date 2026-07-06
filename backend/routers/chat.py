# backend/routers/chat.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
import uuid
from backend.database import get_db
from backend.models import Case, Message
from backend.schemas import SendMessageRequest, ApiResponse, CaseStatus

router = APIRouter(prefix="/api", tags=["chat"])

@router.post("/chat", response_model=ApiResponse)
def send_message(req: SendMessageRequest, db: Session = Depends(get_db)):
    # 查询案件
    case = db.query(Case).filter(Case.id == req.case_id).first()
    if not case:
        return ApiResponse(success=False, data=None, message="CASE_NOT_FOUND")

    # 加载现有的 collected_fields / missing_fields
    collected = dict(case.collected_fields or {})
    missing = list(case.missing_fields or [])

    # 保存用户消息
    user_msg = Message(
        id=f"msg_{uuid.uuid4().hex[:8]}",
        case_id=req.case_id,
        role="user",
        content=req.message,
        message_type="text"
    )
    db.add(user_msg)

    # 解析用户消息中的关键信息
    # 移除 description 这类非标准字段
    collected.pop("description", None)

    if "预算" in req.message or "元" in req.message:
        import re
        numbers = re.findall(r'\d+', req.message)
        if numbers:
            collected["monthly_budget_left"] = int(numbers[0])
            if "monthly_budget_left" in missing:
                missing.remove("monthly_budget_left")

    if "已有" in req.message or "替代" in req.message:
        collected["owned_alternatives"] = req.message
        if "owned_alternatives" in missing:
            missing.remove("owned_alternatives")

    # 更新案件
    case.collected_fields = collected
    case.missing_fields = missing

    # 判断是否信息完整
    if not missing:
        case.status = CaseStatus.READY_FOR_DEBATE
        reply = "信息已补充完整，可以进入正反方分析。"
    else:
        case.status = CaseStatus.COLLECTING
        next_question = None
        if "monthly_budget_left" in missing:
            next_question = "你本月预算还剩多少？"
        elif "owned_alternatives" in missing:
            next_question = "是否已经有类似的替代品？"
        reply = f"还需要补充以下信息：{', '.join(missing)}。{next_question if next_question else ''}"

    db.commit()

    # 保存助手消息
    assistant_msg = Message(
        id=f"msg_{uuid.uuid4().hex[:8]}",
        case_id=req.case_id,
        role="assistant",
        content=reply,
        message_type="text"
    )
    db.add(assistant_msg)
    db.commit()

    return ApiResponse(
        success=True,
        data={
            "reply": reply,
            "case_status": case.status,
            "collected_fields": collected,
            "missing_fields": missing,
        },
        message=""
    )
