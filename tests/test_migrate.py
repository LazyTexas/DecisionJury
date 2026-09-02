# tests/test_migrate.py
"""测试迁移模块"""

from backend.migrate import (
    get_existing_columns,
    migrate_cases,
    migrate_histories,
    migrate_traces,
    migrate_reminders,
    migrate_indexes,
)


def test_get_existing_columns(db_engine):
    """获取表列名"""
    from backend.database import Base
    Base.metadata.create_all(bind=db_engine)

    columns = get_existing_columns("cases")
    assert "id" in columns
    assert "title" in columns
    assert "status" in columns
    assert "collected_fields" in columns


def test_migrate_cases(db_engine):
    """迁移 cases 表"""
    from backend.database import Base
    Base.metadata.create_all(bind=db_engine)

    migrate_cases()
    columns = get_existing_columns("cases")
    assert "debate_result" in columns


def test_migrate_histories(db_engine):
    """迁移 histories 表"""
    from backend.database import Base
    Base.metadata.create_all(bind=db_engine)

    migrate_histories()
    columns = get_existing_columns("histories")
    required_fields = ["title", "price", "context", "pros", "cons", "report_id"]
    for field in required_fields:
        assert field in columns


def test_migrate_traces(db_engine):
    """迁移 traces 表"""
    from backend.database import Base
    Base.metadata.create_all(bind=db_engine)

    migrate_traces()
    columns = get_existing_columns("traces")
    required_fields = ["input_summary", "output_summary", "duration_ms", "error"]
    for field in required_fields:
        assert field in columns


def test_migrate_reminders(db_engine):
    """迁移 reminders 表"""
    from backend.database import Base
    Base.metadata.create_all(bind=db_engine)

    migrate_reminders()
    columns = get_existing_columns("reminders")
    assert "reason" in columns


def test_migrate_indexes(db_engine):
    """创建索引（不报错即通过）"""
    from backend.database import Base
    Base.metadata.create_all(bind=db_engine)

    # 应该不抛出异常
    migrate_indexes()