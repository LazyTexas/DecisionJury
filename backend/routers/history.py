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
    query = db.query(History).filter(History.user_id == user_id)

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