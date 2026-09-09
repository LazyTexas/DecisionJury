# tests/conftest.py
"""共享测试 fixture：内存 SQLite 数据库 + FastAPI TestClient"""

import pytest
from sqlalchemy import create_engine, StaticPool, event
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from backend.database import Base, get_db
from backend.main import app
from backend.models import Case, User
from backend.schemas import CaseStatus


# 外键占位数据说明：
#   cases.user_id / histories.user_id / reminders.user_id  → users.id
#   messages.case_id / traces.case_id / reminders.case_id  → cases.id
# 用例正文里直接写死了 user_id="u001"~"u005"、case_id="case_001" 等，
# 因此这些用户和案件必须先存在，否则插入会被外键约束拦下（IntegrityError）。
TEST_USER_IDS = ("u001", "u002", "u003", "u004", "u005")
TEST_CASE_IDS = ("case_001", "case_002", "case_003")
PLACEHOLDER_OWNER_ID = "u_seed"


def _seed_foreign_key_placeholders(engine):
    """为每个测试库插入外键占位数据。

    占位案件统一挂在 PLACEHOLDER_OWNER_ID 名下，避免污染各用例
    自己针对 u001~u005 的案件列表与分页断言。
    """
    TestSessionLocal = sessionmaker(bind=engine)
    db = TestSessionLocal()
    try:
        for user_id in (PLACEHOLDER_OWNER_ID, *TEST_USER_IDS):
            db.add(User(id=user_id, name=f"测试用户{user_id}", hashed_password="not-used"))
        # 先 flush 保证 users 落库，再插 cases，否则 cases.user_id 外键会失败
        db.flush()
        for case_id in TEST_CASE_IDS:
            db.add(
                Case(
                    id=case_id,
                    user_id=PLACEHOLDER_OWNER_ID,
                    case_type="shopping",
                    title=f"占位案件 {case_id}",
                    description="外键占位数据，仅供测试使用",
                    status=CaseStatus.COLLECTING,
                    collected_fields={},
                    missing_fields=[],
                )
            )
        db.commit()
    finally:
        db.close()


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
    _seed_foreign_key_placeholders(engine)
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


@pytest.fixture()
def db_session(db_engine):
    """共享内存数据库的会话，供路由测试直接读写数据。

    与 client 共用同一个 db_engine，因此在测试里通过 db_session
    写入的案例/提醒，能通过 HTTP 接口读出来。
    """
    TestSessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=db_engine
    )
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()