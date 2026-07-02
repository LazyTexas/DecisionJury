from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
from schemas import SendMessageRequest

router = APIRouter(prefix="/api", tags=["chat"])

@router.post("/chat")
def send_message(req: SendMessageRequest, db: Session = Depends(get_db)):
    # TODO: 保存消息，判断状态，调用 Agent
    return {
        "success": True,
        "data": {
            "reply": "信息已补充，可以进入辩论阶段。",
            "case_status": "ready_for_debate",
            "collected_fields": {},
            "missing_fields": []
        }
    }