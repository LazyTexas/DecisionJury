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
    except Exception as e:
        print(f"[WARN] input_parser 调用失败: {e}")
        return ApiResponse(
            success=False,
            data=None,
            message="PARSE_ERROR"
        )

    # 4. 增量更新 collected_fields
    safe_fields = case.collected_fields or {}
    print(f"[DEBUG] BEFORE: {safe_fields}")

    for key, value in result_dict.get("extracted_fields", {}).items():
        if value is None or value == "":
            continue
        # 关键：已有字段不覆盖，只填缺失字段
        if key not in safe_fields:
            safe_fields[key] = value

    print(f"[DEBUG] AFTER: {safe_fields}")

    # 5. 更新案件
    case.collected_fields = safe_fields

    # 6. 重新计算缺失字段
    if case.case_type == "shopping":
        still_missing = [
            f for f in SHOPPING_REQUIRED_FIELDS
            if f not in safe_fields or safe_fields.get(f) in [None, ""]
        ]
    else:
        still_missing = []
    case.missing_fields = still_missing

    # 7. 更新状态
    if result_dict.get("is_high_risk"):
        case.status = CaseStatus.REJECTED
        reply = result_dict.get("reject_reason", "该决策超出系统支持范围。")
    elif not still_missing:
        case.status = CaseStatus.READY_FOR_DEBATE
        reply = "信息已补充完整，可以进入正反方分析。"
    else:
        case.status = CaseStatus.COLLECTING
        next_question = result_dict.get("next_question")
        if next_question:
            reply = f"还需要补充以下信息：{', '.join(still_missing)}。{next_question}"
        else:
            reply = f"还需要补充以下信息：{', '.join(still_missing)}。请继续补充。"

    # 8. 保存助手消息
    assistant_msg = Message(
        id=f"msg_{uuid.uuid4().hex[:8]}",
        case_id=case_id,
        role="assistant",
        content=reply,
        message_type="text"
    )
    db.add(assistant_msg)

    # 9. 强制标记字段已修改（解决 SQLAlchemy JSON 字段追踪问题）
    try:
        attributes.flag_modified(case, 'collected_fields')
        attributes.flag_modified(case, 'missing_fields')
    except Exception as e:
        print(f"[WARN] flag_modified 失败: {e}")

    # 10. 提交事务
    db.commit()
    print(f"[DEBUG] COMMIT 成功，case_id={case_id}")

    return ApiResponse(
        success=True,
        data={
            "reply": reply,
            "case_status": case.status,
            "collected_fields": safe_fields,
            "missing_fields": still_missing,
        },
        message=""
    )