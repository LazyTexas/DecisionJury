# backend/models.py
from sqlalchemy import Column, String, DateTime, JSON, Text, Integer, Index
from sqlalchemy.sql import func
from backend.database import Base

class Case(Base):
    __tablename__ = "cases"

    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, index=True)
    case_type = Column(String)  # shopping / time
    title = Column(String)
    description = Column(Text)
    status = Column(String)  # collecting / ready_for_debate / debating / completed / rejected / archived
    collected_fields = Column(JSON, default={})   # 多轮对话收集的字段
    missing_fields = Column(JSON, default=[])     # 缺失的字段列表
    final_decision = Column(String, nullable=True)  # buy / delay / reject / alternative
    report_id = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

class Message(Base):
    __tablename__ = "messages"

    id = Column(String, primary_key=True, index=True)
    case_id = Column(String, index=True)
    role = Column(String)  # user / assistant / pro_agent / con_agent / judge
    content = Column(Text)
    message_type = Column(String, default="text")  # text / question / argument / verdict / system
    created_at = Column(DateTime, server_default=func.now())

class History(Base):
    __tablename__ = "histories"

    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, index=True)
    case_type = Column(String)  # shopping / time
    summary = Column(Text)
    result = Column(String)  # worth / regret / neutral
    tags = Column(JSON, default=[])
    created_at = Column(DateTime, server_default=func.now())

class Trace(Base):
    """Agent 执行轨迹表"""
    __tablename__ = "traces"

    id = Column(String, primary_key=True, index=True)
    case_id = Column(String, index=True, nullable=False)
    step = Column(Integer, nullable=False)
    type = Column(String, nullable=False)  # agent / rag_search / tool_call
    name = Column(String, nullable=False)  # input_parser / pro_agent / rag_search / cost_analyzer 等
    input_summary = Column(Text, nullable=True)
    output_summary = Column(Text, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    status = Column(String, nullable=False)  # completed / failed
    error = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    # 添加索引
    __table_args__ = (
        Index("ix_traces_case_id_step", "case_id", "step"),
    )