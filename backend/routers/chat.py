# backend/routers/chat.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
import uuid
from backend.database import get_db
from backend.models import Case, Message
from backend.schemas import SendMessageRequest, ApiResponse, CaseStatus
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

    # 3. 调用 input_parser
    try:
        result = parse_input(
            raw_input=req.message,
            existing_collected_fields=case.collected_fields or {},
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
                "collected_fields": collected,
                "missing_fields": [],
                "is_high_risk": True,
                "reject_reason": reject_reason,
            },
            message=""
        )
    
    safe_fields = result_dict.get("merged_fields", {})
    case.collected_fields = safe_fields
    case.missing_fields = result_dict.get("missing_fields", [])
    case.status = result_dict.get("case_status", CaseStatus.COLLECTING)

    # 5. 根据状态生成回复
    if case.status == CaseStatus.READY_FOR_DEBATE:
        reply = "信息已补充完整，可以进入正反方分析。"
    else:
        # 优先使用 C 的 next_question
        next_question = result_dict.get("next_question")
        if next_question:
            reply = next_question
        else:
            # 如果 C 模块没有返回追问，使用通用提示（不暴露字段名）
            reply = "信息仍在收集中，请继续补充相关细节。"

    # 6. 保存助手消息
    assistant_msg = Message(
        id=f"msg_{uuid.uuid4().hex[:8]}",
        case_id=case_id,
        role="assistant",
        content=reply,
        message_type="text"
    )
    db.add(assistant_msg)

    # 7. 强制标记字段已修改（解决 SQLAlchemy JSON 字段追踪问题）
    try:
        attributes.flag_modified(case, 'collected_fields')
        attributes.flag_modified(case, 'missing_fields')
    except Exception as e:
        print(f"[WARN] flag_modified 失败: {e}")

    # 8. 提交事务
    db.commit()
    print(f"[DEBUG] COMMIT 成功，case_id={case_id}")

    return ApiResponse(
        success=True,
        data={
            "reply": reply,
            "case_status": case.status,
            "collected_fields": safe_fields,
            "missing_fields": case.missing_fields,
            "is_high_risk": False,
            "reject_reason": None,
        },
        message=""
    )