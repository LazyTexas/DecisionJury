# backend/routers/history.py
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
import uuid
from backend.database import get_db
from backend.models import History
from backend.schemas import ApiResponse, CreateHistoryRequest, HistoryItem, HistoryListResponse
from pydantic import BaseModel
from typing import List, Optional

router = APIRouter(prefix="/api", tags=["history"])


@router.post("/history", response_model=ApiResponse)
def create_history(req: CreateHistoryRequest, db: Session = Depends(get_db)):
    """
    添加历史记录
    用于在决策完成后，将案件结果存入历史库，供 RAG 检索使用
    """
    history = History(
        id=f"history_{uuid.uuid4().hex[:8]}",
        user_id=req.user_id,
        case_type=req.case_type,
        summary=req.summary,
        result=req.result,
        tags=req.tags or [],

        # 新增字段
        title=req.title,
        price=req.price,
        usage_frequency=req.usage_frequency,
        context=req.context,
        pros=req.pros or [],
        cons=req.cons or [],
        final_decision=req.final_decision,
        case_id=req.case_id,
        report_id=req.report_id,
    )
    db.add(history)
    db.commit()
    db.refresh(history)

    return ApiResponse(
        success=True,
        data={
            "history_id": history.id,
            "user_id": history.user_id,
            "case_type": history.case_type,
            "summary": history.summary,
            "result": history.result,
            "tags": history.tags,
            "title": history.title,
            "price": history.price,
            "usage_frequency": history.usage_frequency,
            "context": history.context,
            "pros": history.pros,
            "cons": history.cons,
            "final_decision": history.final_decision,
            "case_id": history.case_id,
            "report_id": history.report_id,
            "created_at": history.created_at.isoformat() if history.created_at else None,
        },
        message="history created"
    )

@router.get("/history", response_model=ApiResponse)
def get_history(
    user_id: str = Query(..., description="用户 ID（必填）"),
    page: int = Query(1, ge=1, description="页码，默认 1"),
    page_size: int = Query(10, ge=1, le=1000, description="每页条数，默认 10，最大 100"),
    case_type: Optional[str] = Query(None, description="案件类型筛选：shopping / time"),
    result: Optional[str] = Query(None, description="结果筛选：worth / regret / neutral"),
    db: Session = Depends(get_db)
):
    """
    获取用户的历史记录列表
    支持分页、按案件类型和结果筛选，按创建时间倒序排列
    """
    # 1. 构建基础查询
    query = db.query(History).filter(
        History.user_id == user_id,
        History.is_deleted == 0
    )

    # 2. 应用筛选条件
    if case_type:
        query = query.filter(History.case_type == case_type)
    if result:
        query = query.filter(History.result == result)

    # 3. 获取总数
    total = query.count()

    # 4. 分页查询，按 created_at 倒序
    items = query.order_by(History.created_at.desc()) \
                 .offset((page - 1) * page_size) \
                 .limit(page_size) \
                 .all()

    # 5. 组装返回数据
    result_items = [
        HistoryItem(
            history_id=item.id,
            user_id=item.user_id,
            case_type=item.case_type,
            title=item.title,
            summary=item.summary,
            result=item.result,
            tags=item.tags or [],
            case_id=item.case_id,
            report_id=item.report_id,
            created_at=item.created_at.isoformat() if item.created_at else None,
        ).model_dump()
        for item in items
    ]

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

@router.delete("/history/{history_id}", response_model=ApiResponse)
def delete_history(
    history_id: str,
    user_id: str = Query(..., description="用户 ID"),
    db: Session = Depends(get_db)
):
    """
    软删除历史记录（前端删除后，数据仍保留供 RAG 检索使用）
    """
    # 1. 查询历史记录
    history = db.query(History).filter(History.id == history_id).first()
    if not history:
        return ApiResponse(
            success=False,
            data=None,
            message="HISTORY_NOT_FOUND"
        )

    # 2. 权限校验
    if history.user_id != user_id:
        return ApiResponse(
            success=False,
            data=None,
            message="FORBIDDEN"
        )

    # 3. 如果已经删除，返回提示
    if history.is_deleted == 1:
        return ApiResponse(
            success=False,
            data=None,
            message="HISTORY_ALREADY_DELETED"
        )

    # 4. 软删除：标记为已删除
    history.is_deleted = 1
    db.commit()

    return ApiResponse(
        success=True,
        data={"deleted": True},
        message=""
    )

@router.patch("/history/{history_id}/restore", response_model=ApiResponse)
def restore_history(
    history_id: str,
    user_id: str = Query(..., description="用户 ID"),
    db: Session = Depends(get_db)
):
    """
    恢复已软删除的历史记录
    """
    # 1. 查询历史记录
    history = db.query(History).filter(History.id == history_id).first()
    if not history:
        return ApiResponse(
            success=False,
            data=None,
            message="HISTORY_NOT_FOUND"
        )

    # 2. 权限校验
    if history.user_id != user_id:
        return ApiResponse(
            success=False,
            data=None,
            message="FORBIDDEN"
        )

    # 3. 如果未被删除，返回提示
    if history.is_deleted == 0:
        return ApiResponse(
            success=False,
            data=None,
            message="HISTORY_NOT_DELETED"
        )

    # 4. 恢复：取消软删除标记
    history.is_deleted = 0
    db.commit()

    return ApiResponse(
        success=True,
        data={"restored": True},
        message=""
    )