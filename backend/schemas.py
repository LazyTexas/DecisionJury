from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

# ===== 枚举（与 API 文档对齐）=====
class CaseStatus(str):
    COLLECTING = "collecting"
    READY_FOR_DEBATE = "ready_for_debate"
    DEBATING = "debating"
    COMPLETED = "completed"
    ARCHIVED = "archived"

class CaseType(str):
    SHOPPING = "shopping"
    TIME = "time"

# ===== 请求/响应模型 =====
class CreateCaseRequest(BaseModel):
    user_id: str
    case_type: str  # "shopping" / "time"
    title: str
    description: str

class CreateCaseResponse(BaseModel):
    case_id: str
    status: str
    missing_fields: List[str] = []
    next_question: Optional[str] = None

class SendMessageRequest(BaseModel):
    user_id: str
    case_id: str
    message: str