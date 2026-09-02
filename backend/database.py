# backend/database.py
from sqlalchemy import create_engine, event
# from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from backend.config import Config

class Base(DeclarativeBase):
    """SQLAlchemy 2.0 声明式基类"""
    pass

# 创建数据库引擎
engine = create_engine(
    Config.DATABASE_URL,
    connect_args={"check_same_thread": False}  # SQLite 专用
)

# ===== 启用 SQLite 外键约束 =====
@event.listens_for(engine, "connect")
def enable_foreign_keys(dbapi_connection, connection_record):
    """每次连接数据库时启用外键约束"""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

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