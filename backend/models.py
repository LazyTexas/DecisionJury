from sqlalchemy import Column, String, DateTime, JSON, Float, Integer
from sqlalchemy.dialects.sqlite import TEXT
from database import Base
from datetime import datetime

class Case(Base):
    __tablename__ = "cases"

    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, index=True)
    case_type = Column(String)  # "shopping" / "time"
    title = Column(String)
    description = Column(TEXT)
    status = Column(String)  # "collecting" / "ready_for_debate" / "debating" / "completed" / "archived"
    final_decision = Column(String, nullable=True)  # "buy" / "delay" / "reject" / "alternative"
    report_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(String, primary_key=True, index=True)
    case_id = Column(String, index=True)
    user_id = Column(String, index=True)
    role = Column(String)  # "user" / "system" / "assistant"
    content = Column(TEXT)
    message_type = Column(String)  # "text" / "argument" / "verdict" / "tool_call"
    created_at = Column(DateTime, default=datetime.now)

class History(Base):
    __tablename__ = "histories"

    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, index=True)
    case_type = Column(String)
    summary = Column(TEXT)
    result = Column(String)  # "regret" / "satisfied" / "neutral"
    tags = Column(JSON, default=[])
    created_at = Column(DateTime, default=datetime.now)