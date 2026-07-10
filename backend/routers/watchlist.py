# backend/routers/watchlist.py
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import Reminder
from backend.schemas import ApiResponse

router = APIRouter(prefix="/api", tags=["watchlist"])


@router.get("/watchlist", response_model=ApiResponse)
def get_watchlist(
    user_id: str = Query(..., description="用户 ID"),
    db: Session = Depends(get_db)
):
    """
    获取用户的观察清单（冷静期中的案件列表）
    按冷静期结束时间升序排列（即将到期的在前）
    """
    # 查询该用户所有状态为 waiting 的提醒
    reminders = db.query(Reminder).filter(
        Reminder.user_id == user_id,
        Reminder.status == "waiting"
    ).order_by(Reminder.due_at.asc()).all()

    items = [
        {
            "reminder_id": r.id,
            "case_id": r.case_id,
            "title": r.title,
            "reason": r.reason,
            "due_at": r.due_at.isoformat() if r.due_at else None,
            "status": r.status,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in reminders
    ]

    return ApiResponse(
        success=True,
        data={"items": items},
        message=""
    )