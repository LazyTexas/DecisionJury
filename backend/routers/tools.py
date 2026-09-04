"""MCP 工具 HTTP 接口

提供 cost_analyzer 和 cooling_reminder 的 HTTP 端点，
供 Agent 编排层和前端通过 REST API 调用。
输出统一为 ToolResult 格式（docs/04_API.md §5.5）。
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime

from backend.database import get_db
from backend.models import Reminder
from backend.schemas import ApiResponse
from mcp_tools.cost_analyzer import analyze_shopping, analyze_time
from mcp_tools.decision_score import score_decision

router = APIRouter(prefix="/api/tools", tags=["tools"])


# ==================== 请求体模型 ====================

class CostAnalyzerRequest(BaseModel):
    case_type: str
    case_id: str | None = None
    price: float | None = None
    monthly_budget_left: float | None = None
    hours_required: float | None = None
    free_hours_this_week: float | None = None
    urgent_tasks: int | None = None


class CoolingReminderRequest(BaseModel):
    user_id: str
    case_id: str
    title: str
    cooling_days: int = 3
    reason: str = ""
    watch_items: list[str] = []


class DecisionScoreRequest(BaseModel):
    case_type: str
    cost_risk_level: str = "medium"
    history_risk: float = 0.5
    usage_value: float = 0.5
    impulse_trigger: bool = False


# ==================== cost_analyzer ====================

@router.post("/cost-analyzer", response_model=ApiResponse)
def cost_analyzer_endpoint(req: CostAnalyzerRequest):
    """
    成本分析工具。

    - shopping 场景：传入 price, monthly_budget_left
    - time 场景：传入 hours_required, free_hours_this_week, urgent_tasks
    """
    try:
        if req.case_type == "shopping":
            if req.price is None or req.monthly_budget_left is None:
                return ApiResponse(
                    success=False, data=None,
                    message="shopping 场景需要 price 和 monthly_budget_left"
                )
            raw = analyze_shopping(price=req.price, monthly_budget_left=req.monthly_budget_left)
        elif req.case_type == "time":
            if req.hours_required is None or req.free_hours_this_week is None or req.urgent_tasks is None:
                return ApiResponse(
                    success=False, data=None,
                    message="time 场景需要 hours_required、free_hours_this_week 和 urgent_tasks"
                )
            raw = analyze_time(
                hours_required=req.hours_required,
                free_hours_this_week=req.free_hours_this_week,
                urgent_tasks=req.urgent_tasks,
            )
        else:
            return ApiResponse(success=False, data=None, message="UNSUPPORTED_CASE_TYPE")

        return ApiResponse(
            success=True,
            data={
                "tool_name": "cost_analyzer",
                "status": "success",
                "summary": raw.get("explanation", ""),
                "risk_level": raw.get("risk_level"),
                "metrics": raw.get("metrics", {}),
                "error": None,
            },
            message="",
        )
    except Exception as exc:
        return ApiResponse(
            success=True,
            data={
                "tool_name": "cost_analyzer",
                "status": "failed",
                "summary": "成本分析工具调用失败，主流程继续。",
                "risk_level": None,
                "metrics": {},
                "error": f"TOOL_ERROR: {exc}",
            },
            message="",
        )


# ==================== cooling_reminder ====================

@router.post("/cooling-reminder", response_model=ApiResponse)
def cooling_reminder_endpoint(req: CoolingReminderRequest, db: Session = Depends(get_db)):
    """
    冷静期提醒工具。

    创建提醒并将记录写入 Reminder 表，供观察清单接口查询。
    """
    from mcp_tools.cooling_reminder import create_reminder

    try:
        # 1. 调用 MCP 工具计算
        raw = create_reminder(
            user_id=req.user_id,
            case_id=req.case_id,
            title=req.title,
            cooling_days=req.cooling_days,
            reason=req.reason,
        )

        if raw.get("status") == "error":
            return ApiResponse(
                success=True,
                data={
                    "tool_name": "cooling_reminder",
                    "status": "failed",
                    "summary": raw.get("error", "冷静期提醒创建失败。"),
                    "risk_level": None,
                    "metrics": {},
                    "error": "REMINDER_CREATE_FAILED",
                },
                message="",
            )

        # 2. 写入 Reminder 表
        effective_days = max(req.cooling_days, 1)
        due_dt = datetime.strptime(raw["due_at"], "%Y-%m-%dT%H:%M:%S+08:00")
        reminder = Reminder(
            id=raw["reminder_id"],
            user_id=req.user_id,
            case_id=req.case_id,
            title=req.title,
            reason=req.reason,
            due_at=due_dt,
            status="waiting",
        )
        db.add(reminder)
        db.commit()

        # 3. 返回 ToolResult
        return ApiResponse(
            success=True,
            data={
                "tool_name": "cooling_reminder",
                "status": "success",
                "summary": f"已创建 {effective_days} 天冷静期提醒。",
                "risk_level": None,
                "metrics": {
                    "reminder_id": raw["reminder_id"],
                    "cooling_days": effective_days,
                    "due_at": raw["due_at"],
                    "watch_items": req.watch_items,
                },
                "error": None,
            },
            message="",
        )
    except Exception as exc:
        return ApiResponse(
            success=True,
            data={
                "tool_name": "cooling_reminder",
                "status": "failed",
                "summary": "冷静期提醒创建失败，建议用户手动设置复盘提醒。",
                "risk_level": None,
                "metrics": {},
                "error": f"REMINDER_CREATE_FAILED: {exc}",
            },
            message="",
        )


# ==================== decision_score ====================

@router.post("/decision-score", response_model=ApiResponse)
def decision_score_endpoint(req: DecisionScoreRequest):
    """
    决策评分工具。

    综合成本压力、历史证据风险、使用价值与冲动触发，输出 0~100 综合分。
    """
    try:
        raw = score_decision(
            case_type=req.case_type,
            cost_risk_level=req.cost_risk_level,
            history_risk=req.history_risk,
            usage_value=req.usage_value,
            impulse_trigger=req.impulse_trigger,
        )
        return ApiResponse(
            success=True,
            data={
                "tool_name": "decision_score",
                "status": "success",
                "summary": raw.get("suggestion", ""),
                "risk_level": raw.get("risk_level"),
                "metrics": {
                    "score": raw.get("score"),
                    "risk_level": raw.get("risk_level"),
                    "dimensions": raw.get("dimensions", {}),
                },
                "error": None,
            },
            message="",
        )
    except Exception as exc:
        return ApiResponse(
            success=True,
            data={
                "tool_name": "decision_score",
                "status": "failed",
                "summary": "决策评分工具调用失败，主流程继续。",
                "risk_level": None,
                "metrics": {},
                "error": f"TOOL_ERROR: {exc}",
            },
            message="",
        )
