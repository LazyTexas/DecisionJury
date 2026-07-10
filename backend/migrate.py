# backend/migrate.py
"""
数据库迁移模块
供 check_database() 调用
"""

import json
import os
from datetime import datetime
from sqlalchemy import text
from backend.database import engine, SessionLocal
from backend import models


def get_existing_columns(table_name):
    """获取表中已有的列名"""
    with engine.connect() as conn:
        result = conn.execute(text(f"PRAGMA table_info({table_name})"))
        return {row[1] for row in result}


def migrate_cases():
    """迁移 cases 表"""
    columns = get_existing_columns("cases")
    additions = []

    if "debate_result" not in columns:
        additions.append("ADD COLUMN debate_result TEXT")

    if additions:
        with engine.connect() as conn:
            for stmt in additions:
                conn.execute(text(f"ALTER TABLE cases {stmt}"))
            conn.commit()
            print("[OK] cases 表迁移完成")
    else:
        print("[INFO] cases 表无需迁移")


def migrate_histories():
    """迁移 histories 表"""
    columns = get_existing_columns("histories")
    additions = []

    if "title" not in columns:
        additions.append("ADD COLUMN title TEXT")
    if "price" not in columns:
        additions.append("ADD COLUMN price REAL")
    if "usage_frequency" not in columns:
        additions.append("ADD COLUMN usage_frequency TEXT")
    if "context" not in columns:
        additions.append("ADD COLUMN context TEXT")
    if "pros" not in columns:
        additions.append("ADD COLUMN pros TEXT")
    if "cons" not in columns:
        additions.append("ADD COLUMN cons TEXT")
    if "final_decision" not in columns:
        additions.append("ADD COLUMN final_decision TEXT")
    if "case_id" not in columns:
        additions.append("ADD COLUMN case_id TEXT")
    if "report_id" not in columns:
        additions.append("ADD COLUMN report_id TEXT")

    if additions:
        with engine.connect() as conn:
            for stmt in additions:
                conn.execute(text(f"ALTER TABLE histories {stmt}"))
            conn.commit()
            print("[OK] histories 表迁移完成")
    else:
        print("[INFO] histories 表无需迁移")


def migrate_traces():
    """迁移 traces 表"""
    try:
        columns = get_existing_columns("traces")
    except Exception:
        print("[INFO] traces 表不存在，跳过迁移")
        return

    additions = []
    if "input_summary" not in columns:
        additions.append("ADD COLUMN input_summary TEXT")
    if "output_summary" not in columns:
        additions.append("ADD COLUMN output_summary TEXT")
    if "duration_ms" not in columns:
        additions.append("ADD COLUMN duration_ms INTEGER")
    if "error" not in columns:
        additions.append("ADD COLUMN error TEXT")

    if additions:
        with engine.connect() as conn:
            for stmt in additions:
                conn.execute(text(f"ALTER TABLE traces {stmt}"))
            conn.commit()
            print("[OK] traces 表迁移完成")


def migrate_reminders():
    """迁移 reminders 表"""
    try:
        columns = get_existing_columns("reminders")
    except Exception:
        print("[INFO] reminders 表不存在，跳过迁移")
        return

    additions = []
    if "reason" not in columns:
        additions.append("ADD COLUMN reason TEXT")

    if additions:
        with engine.connect() as conn:
            for stmt in additions:
                conn.execute(text(f"ALTER TABLE reminders {stmt}"))
            conn.commit()
            print("[OK] reminders 表迁移完成")


def migrate_indexes():
    """创建缺失的索引"""
    with engine.connect() as conn:
        indexes = {
            "ix_cases_user_id_updated_at": "CREATE INDEX IF NOT EXISTS ix_cases_user_id_updated_at ON cases(user_id, updated_at)",
            "ix_cases_user_id_status": "CREATE INDEX IF NOT EXISTS ix_cases_user_id_status ON cases(user_id, status)",
            "ix_cases_status": "CREATE INDEX IF NOT EXISTS ix_cases_status ON cases(status)",
            "ix_messages_case_id_created_at": "CREATE INDEX IF NOT EXISTS ix_messages_case_id_created_at ON messages(case_id, created_at)",
            "ix_histories_user_id_created_at": "CREATE INDEX IF NOT EXISTS ix_histories_user_id_created_at ON histories(user_id, created_at)",
            "ix_histories_user_id_case_type": "CREATE INDEX IF NOT EXISTS ix_histories_user_id_case_type ON histories(user_id, case_type)",
            "ix_histories_case_id": "CREATE INDEX IF NOT EXISTS ix_histories_case_id ON histories(case_id)",
            "ix_traces_case_id_step": "CREATE INDEX IF NOT EXISTS ix_traces_case_id_step ON traces(case_id, step)",
            "ix_reminders_user_id_status": "CREATE INDEX IF NOT EXISTS ix_reminders_user_id_status ON reminders(user_id, status)",
        }
        for name, sql in indexes.items():
            try:
                conn.execute(text(sql))
            except Exception as e:
                print(f"[WARN] 索引 {name} 创建失败: {e}")
        conn.commit()
        print("[OK] 索引迁移完成")


def run_all_migrations():
    """执行所有字段迁移（不包含索引）"""
    print("[INFO] 开始执行数据库迁移...")
    migrate_cases()
    migrate_histories()
    migrate_traces()
    migrate_reminders()
    print("[OK] 所有字段迁移完成")


def backup_data():
    """备份所有表数据到 JSON 文件"""
    db = SessionLocal()
    data = {}
    tables = ["cases", "messages", "histories", "traces", "reminders"]

    for table_name in tables:
        try:
            result = db.execute(text(f"SELECT * FROM {table_name}"))
            rows = result.fetchall()
            if rows:
                columns = result.keys()
                data[table_name] = [dict(zip(columns, row)) for row in rows]
                print(f"[INFO] 备份 {table_name}: {len(rows)} 条记录")
            else:
                data[table_name] = []
                print(f"[INFO] {table_name}: 无数据")
        except Exception as e:
            print(f"[WARN] 备份 {table_name} 失败: {e}")
            data[table_name] = []

    db.close()

    backup_path = f"data/backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    os.makedirs("data", exist_ok=True)
    with open(backup_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)

    print(f"[OK] 数据已备份到: {backup_path}")
    return backup_path


def restore_data(backup_path):
    """从 JSON 文件恢复数据"""
    if not os.path.exists(backup_path):
        print(f"[ERROR] 备份文件不存在: {backup_path}")
        return False

    with open(backup_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    db = SessionLocal()
    model_tables = {
        "cases": models.Case,
        "messages": models.Message,
        "histories": models.History,
        "traces": models.Trace,
        "reminders": models.Reminder,
    }

    # 按依赖顺序插入
    insert_order = ["cases", "messages", "histories", "traces", "reminders"]

    # 临时关闭外键检查，避免恢复时约束冲突
    with engine.connect() as conn:
        conn.execute(text("PRAGMA foreign_keys=OFF"))
        conn.commit()

    try:
        for table_name in insert_order:
            if table_name not in data or not data[table_name]:
                continue

            model_class = model_tables.get(table_name)
            if not model_class:
                continue

            print(f"[INFO] 恢复 {table_name}: {len(data[table_name])} 条记录")
            for row_data in data[table_name]:
                try:
                    obj = model_class(**row_data)
                    db.add(obj)
                except Exception as e:
                    print(f"[WARN] 插入失败: {e}")
                    continue

        db.commit()
        print("[OK] 数据恢复完成")
    except Exception as e:
        db.rollback()
        print(f"[ERROR] 恢复失败: {e}")
        return False
    finally:
        # 重新启用外键检查
        with engine.connect() as conn:
            conn.execute(text("PRAGMA foreign_keys=ON"))
            conn.commit()
        db.close()

    return True


def backup_and_rebuild():
    """备份数据 → 重建数据库 → 恢复数据"""
    print("[INFO] 开始备份数据...")
    backup_path = backup_data()

    if not backup_path:
        print("[ERROR] 备份失败，停止重建")
        return False

    print("[INFO] 正在重建数据库...")
    from backend.database import Base
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    print("[OK] 数据库重建完成")

    print("[INFO] 正在恢复数据...")
    success = restore_data(backup_path)
    return success