# backend/schemas.py
from pydantic import BaseModel
from typing import Optional, List, Dict, Any, Union
from datetime import datetime


# 购物决策所需字段
SHOPPING_REQUIRED_FIELDS = [
    "product_name",
    "price",
    "purpose",
    "monthly_budget_left",
    "owned_alternatives",
    "expected_usage_frequency",
    "trigger_reason"
]

# ===== 枚举值（与 API 文档对齐）=====
class CaseStatus:
    COLLECTING = "collecting"
    READY_FOR_DEBATE = "ready_for_debate"
    DEBATING = "debating"
    COMPLETED = "completed"
    REJECTED = "rejected"
    ARCHIVED = "archived"

class CaseType:
    SHOPPING = "shopping"
    TIME = "time"

# ===== 请求/响应模型 =====
class CreateCaseRequest(BaseModel):
    user_id: str
    case_type: str  # shopping / time
    title: str
    description: str

class CreateCaseResponse(BaseModel):
    case_id: str
    case_status: str
    collected_fields: Dict[str, Any] = {}
    missing_fields: List[str] = []
    next_question: Optional[str] = None

class CreateHistoryRequest(BaseModel):
    """创建历史记录请求"""
    user_id: str
    case_type: str  # shopping / time
    summary: str
    result: str  # worth / regret / neutral
    tags: Optional[List[str]] = []

    # ===== 新增字段 =====
    title: Optional[str] = None  # 商品/活动名称
    price: Optional[float] = None  # 商品价格
    usage_frequency: Optional[str] = None  # daily / weekly / monthly / once
    context: Optional[str] = None  # 详细决策背景
    pros: Optional[List[str]] = []  # 正方观点摘要
    cons: Optional[List[str]] = []  # 反方观点摘要
    final_decision: Optional[str] = None  # buy / delay / reject / alternative
    case_id: Optional[str] = None  # 关联原案件 ID
    report_id: Optional[str] = None  # 关联报告 ID
    
class CreateFeedbackRequest(BaseModel):
    """决策复盘请求"""
    user_id: str
    actual_action: str  # bought / not_bought / delayed / other
    satisfaction: int  # 1-5
    review: Optional[str] = None
    
class SendMessageRequest(BaseModel):
    user_id: str
    # case_id: str # 已移除，从路径参数获取
    message: str

class SendMessageResponse(BaseModel):
    reply: str
    case_status: str
    collected_fields: Dict[str, Any] = {}
    missing_fields: List[str] = []

class DebateResponse(BaseModel):
    case_id: str
    case_status: str
    steps: List[Dict[str, Any]] = []
    rag_evidence: List[Dict[str, Any]] = []
    tool_results: List[Dict[str, Any]] = []
    report: Dict[str, Any] = {}

# 案件列表中的单个案件摘要
class CaseSummary(BaseModel):
    case_id: str
    title: str
    case_type: str
    status: str
    description: str
    updated_at: Optional[str] = None
    message_count: int = 0
    has_report: bool = False

# 判决书响应
class DecisionReportResponse(BaseModel):
    report_id: str
    case_type: str
    final_decision: str
    confidence: float
    summary: str
    case_summary: str
    pro_points: List[str] = []
    con_points: List[str] = []
    next_actions: List[str] = []
    rag_evidence: List[Dict[str, Any]] = []
    tool_results: List[Dict[str, Any]] = []
    created_at: Optional[str] = None

class UpdateCaseRequest(BaseModel):
    """更新案件请求（PATCH）"""
    user_id: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    collected_fields: Optional[Dict[str, Any]] = None

class HistoryItem(BaseModel):
    """历史记录列表项"""
    history_id: str
    user_id: str
    case_type: str
    title: Optional[str] = None
    summary: str
    result: str  # worth / regret / neutral
    tags: List[str] = []
    case_id: Optional[str] = None
    report_id: Optional[str] = None
    created_at: Optional[str] = None

class HistoryListResponse(BaseModel):
    """历史记录列表响应"""
    items: List[HistoryItem]
    total: int
    page: int
    page_size: int

class ApiResponse(BaseModel):
    success: bool
    data: Optional[Any] = None
    message: str = ""

class ErrorResponse(BaseModel):
    """统一错误响应格式"""
    success: bool = False
    data: None = None
    message: str = ""

    class Config:
        json_schema_extra = {
            "example": {
                "success": False,
                "data": None,
                "message": "VALIDATION_ERROR"
            }
        }