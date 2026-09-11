# backend/routers/chat.py
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
import uuid
from backend.database import get_db
from backend.models import Case, Message
from backend.schemas import SendMessageRequest, ApiResponse, CaseStatus
from backend.app.agents.user_facing import public_fields
from backend.app.agents.input_parser import parse_input
from backend.app.schemas.decision import to_dict
from backend.schemas import SHOPPING_REQUIRED_FIELDS
from sqlalchemy.orm import attributes

router = APIRouter(prefix="/api", tags=["chat"])

@router.post("/cases/{case_id}/messages", response_model=ApiResponse)
def send_message(
    case_id: str,
    req: SendMessageRequest,
    db: Session = Depends(get_db)
):
    # 1. 查询案件
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        return ApiResponse(success=False, data=None, message="CASE_NOT_FOUND")

    # 2. 保存用户消息
    user_msg = Message(
        id=f"msg_{uuid.uuid4().hex[:8]}",
        case_id=case_id,
        role="user",
        content=req.message,
        message_type="text"
    )
    db.add(user_msg)

    # 3. 调用 input_parser（带上最近几轮对话，让模型能承接上下文、不复读）
    try:
        recent = (
            db.query(Message)
            .filter(Message.case_id == case_id)
            .order_by(Message.created_at.desc())
            .limit(6)
            .all()
        )
        recent_turns = [f"{m.role}: {m.content}" for m in reversed(recent)]
        result = parse_input(
            raw_input=req.message,
            existing_collected_fields=case.collected_fields or {},
            recent_turns=recent_turns,
        )
        result_dict = to_dict(result)
        print(f"[DEBUG] parse_input 返回: {result_dict.get('extracted_fields', {})}")
    except Exception as e:
        print(f"[WARN] input_parser 调用失败: {e}")
        return ApiResponse(
            success=False,
            data=None,
            message="PARSE_ERROR"
        )

    # 4. 检查高风险
    if result_dict.get("is_high_risk"):
        reject_reason = result_dict.get("reject_reason", "该决策超出系统支持范围。")
        # 更新案件状态为 REJECTED
        case.status = CaseStatus.REJECTED
        # 保存拒绝原因到 collected_fields
        collected = case.collected_fields or {}
        collected["is_high_risk"] = True
        collected["reject_reason"] = reject_reason
        case.collected_fields = collected
        case.missing_fields = []
        db.commit()

        return ApiResponse(
            success=True,
            data={
                "reply": reject_reason,
                "case_status": CaseStatus.REJECTED,
                "collected_fields": public_fields(collected),
                "missing_fields": [],
                "is_high_risk": True,
                "reject_reason": reject_reason,
            },
            message=""
        )
    

    # 5. 使用 C 模块的 merged_fields
    safe_fields = result_dict.get("merged_fields", {})
    case.collected_fields = safe_fields

    # 6. 获取缺失字段（只赋值一次）
    missing_fields = result_dict.get("missing_fields", [])
    case.missing_fields = missing_fields

    # 7. 接入 is_complete 判断状态
    is_complete = result_dict.get("is_complete", False)

    if is_complete or not missing_fields:
        case.status = CaseStatus.READY_FOR_DEBATE
    else:
        case.status = CaseStatus.COLLECTING

    # 8. 接入 conflicts
    conflicts = result_dict.get("conflicts", [])
    if conflicts:
        safe_fields["_conflicts"] = conflicts
        case.collected_fields = safe_fields

    # 9. 接入 next_question_key
    next_question_key = result_dict.get("next_question_key")
    if next_question_key:
        safe_fields["_current_question_key"] = next_question_key
        case.collected_fields = safe_fields

    # 10. 接入 parser_used
    parser_used = result_dict.get("parser_used", "")
    if parser_used:
        safe_fields["_parser_used"] = parser_used
        case.collected_fields = safe_fields

    # 11. 根据状态生成回复
    next_question = result_dict.get("next_question")
    # C 的回复计划优先：承接句 + 一个问题 + 快捷选项，B 不再自己拼追问文案。
    reply_plan = result_dict.get("reply_plan") or {}
    planned_reply = reply_plan.get("reply")
    if planned_reply:
        reply = planned_reply
    elif case.status == CaseStatus.READY_FOR_DEBATE:
        # 核心信息已齐：把 C 的“可选补充”追问接上，避免只剩一句泛泛的“可以分析”。
        reply = "信息已补充完整，可以进入正反方分析。"
        if next_question:
            reply += f" {next_question}"
    else:
        # 优先使用 C 的 next_question
        if next_question:
            reply = next_question
        else:
            # 如果有冲突，生成冲突确认追问
            if conflicts:
                reply = "检测到金额信息存在歧义，请确认：这笔金额是商品价格，还是本月剩余预算？"
            else:
                reply = "信息仍在收集中，请继续补充相关细节。"

    # 12. 保存助手消息
    assistant_msg = Message(
        id=f"msg_{uuid.uuid4().hex[:8]}",
        case_id=case_id,
        role="assistant",
        content=reply,
        message_type="text"
    )
    db.add(assistant_msg)

    # 13. 强制标记字段已修改（解决 SQLAlchemy JSON 字段追踪问题）
    try:
        attributes.flag_modified(case, 'collected_fields')
        attributes.flag_modified(case, 'missing_fields')
    except Exception as e:
        print(f"[WARN] flag_modified 失败: {e}")

    # 14. 提交事务
    db.commit()
    print(f"[DEBUG] COMMIT 成功，case_id={case_id}")

    return ApiResponse(
        success=True,
        data={
            "reply": reply,
            "case_status": case.status,
            "collected_fields": public_fields(safe_fields),
            "missing_fields": case.missing_fields,
            "is_high_risk": False,
            "reject_reason": None,
            # 结构化回复计划：前端据此渲染快捷选项与“可以结束了”的提示。
            "reply_plan": reply_plan,
        },
        message=""
    )

@router.get("/cases/{case_id}/messages", response_model=ApiResponse)
def get_messages(
    case_id: str,
    user_id: str = Query(..., description="用户 ID"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    db: Session = Depends(get_db)
):
    # 1. 查询案件是否存在
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        return ApiResponse(success=False, data=None, message="CASE_NOT_FOUND")

    # 2. 权限校验
    if case.user_id != user_id:
        return ApiResponse(success=False, data=None, message="FORBIDDEN")

    # 3. 分页查询消息
    query = db.query(Message).filter(Message.case_id == case_id)
    total = query.count()
    items = query.order_by(Message.created_at.asc()) \
                 .offset((page - 1) * page_size) \
                 .limit(page_size) \
                 .all()

    # 4. 组装返回
    return ApiResponse(
        success=True,
        data={
            "items": [
                {
                    "id": m.id,
                    "session_id": m.case_id,
                    "role": m.role,
                    "type": m.message_type,
                    "content": m.content,
                    "created_at": m.created_at.isoformat() if m.created_at else None,
                }
                for m in items
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
        },
        message=""
    )