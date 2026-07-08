# backend/schemas.py
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
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

class ApiResponse(BaseModel):
    success: bool
    data: Optional[Any] = None
    message: str = ""