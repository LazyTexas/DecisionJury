# backend/schemas.py
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime

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
    case_id: str
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

class ApiResponse(BaseModel):
    success: bool
    data: Optional[Any] = None
    message: str = ""