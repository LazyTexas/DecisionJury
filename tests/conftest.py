# tests/conftest.py
"""共享测试 fixture：内存 SQLite 数据库 + FastAPI TestClient"""

import pytest
from sqlalchemy import create_engine, StaticPool, event
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from backend.database import Base, get_db
from backend.main import app


@pytest.fixture()
def db_engine():
    """每个测试函数独立的内存 SQLite 引擎，用完自动清表。

    使用 StaticPool 确保所有连接共享同一个内存数据库实例，
    否则 SQLite 内存数据库的每个连接会创建独立的数据库。
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # 启用外键约束
    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db_engine):
    """注入内存数据库的 TestClient，每个测试拿到干净的数据库。"""
    TestSessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=db_engine
    )

    def override_get_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()