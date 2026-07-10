# backend/database.py
from sqlalchemy import create_engine
# from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from backend.config import Config

class Base(DeclarativeBase):
    """SQLAlchemy 2.0 声明式基类"""
    pass

# 创建数据库引擎
engine = create_engine(
    Config.DATABASE_URL,
    connect_args={
        "check_same_thread": False,
        "foreign_keys": True,  # ← 启用 SQLite 外键约束
        }  # SQLite 专用
)

# 会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 基类
# Base = declarative_base()

# 依赖注入函数
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()