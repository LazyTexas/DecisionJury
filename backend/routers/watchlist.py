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


@router.delete("/watchlist/{reminder_id}", response_model=ApiResponse)
def delete_watchlist_item(
    reminder_id: str,
    user_id: str = Query(..., description="用户 ID"),
    db: Session = Depends(get_db)
):
    """
    删除观察清单项：将提醒标记为已取消（不再出现在待复盘列表）。
    对应前端“删除”操作；软删除，保留记录。
    """
    # 1. 查询提醒
    reminder = db.query(Reminder).filter(Reminder.id == reminder_id).first()
    if not reminder:
        return ApiResponse(
            success=False,
            data=None,
            message="REMINDER_NOT_FOUND"
        )

    # 2. 权限校验：确保该提醒属于当前用户
    if reminder.user_id != user_id:
        return ApiResponse(
            success=False,
            data=None,
            message="FORBIDDEN"
        )
    
    # 3. 软删除：标记为已取消
    reminder.status = "cancelled"
    db.commit()
    return ApiResponse(
        success=True,
        data={"deleted": True, "reminder_id": reminder_id},
        message=""
    )