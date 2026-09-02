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

    # ===== 4. 直接使用 C 计算好的 merged_fields =====
    # 不再遍历 extracted_fields，而是直接使用 merged_fields
    safe_fields = result_dict.get("merged_fields", {})
    case.collected_fields = safe_fields
    case.missing_fields = result_dict.get("missing_fields", [])
    case.status = result_dict.get("case_status", CaseStatus.COLLECTING)

    # 5. 根据状态生成回复
    if result_dict.get("is_high_risk"):
        case.status = CaseStatus.REJECTED
        reply = result_dict.get("reject_reason", "该决策超出系统支持范围。")
    elif case.status == CaseStatus.READY_FOR_DEBATE:
        reply = "信息已补充完整，可以进入正反方分析。"
    else:
        # 优先使用 C 的 next_question
        next_question = result_dict.get("next_question")
        if next_question:
            reply = next_question
        else:
            # 兜底：如果 next_question 为空，列出缺失字段
            missing = case.missing_fields or []
            if missing:
                reply = f"还需要补充以下信息：{', '.join(missing)}。请继续补充。"
            else:
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
        },
        message=""
    )