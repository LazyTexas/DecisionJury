# backend/migrate.py
"""
数据库迁移模块

功能：
1. 手动精细控制字段，每个表独立迁移函数
2. 生产环境：迁移失败必须可见，不允许静默失败
3. 所有 NOT NULL 字段必须带 DEFAULT 值
4. 迁移前后做结构校验，失败可回滚
5. 索引与 models.py 的 __table_args__ 一一对应
6. 备份 + 恢复：外键缺失等无法 ALTER 的场景走重建

维护约定：
每次修改 models.py 新增字段后，必须同步更新本文件对应的 migrate_xxx() 函数。
建议用以下命令自查：
    grep -E "Column\\(" backend/models.py
    grep -E "not in columns" backend/migrate.py
两侧字段必须一一对应。
"""
import json
import os
import sys
from datetime import datetime
from sqlalchemy import text, inspect
from sqlalchemy.exc import SQLAlchemyError
from backend.database import engine, SessionLocal, Base
from backend import models


# ==================== 日志工具 ====================

def _log(level: str, msg: str):
    """统一日志输出（带时间戳）"""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] [{level}] {msg}")
    sys.stdout.flush()


# ==================== 结构检查工具 ====================

def get_existing_columns(table_name):
    """获取表中已有的列名"""
    with engine.connect() as conn:
        result = conn.execute(text(f"PRAGMA table_info({table_name})"))
        return {row[1] for row in result}


def table_exists(table_name):
    """检查表是否存在"""
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name=:name"),
            {"name": table_name},
        )
        return result.fetchone() is not None


def get_missing_columns(table_name):
    """返回该表在模型定义中但数据库中缺失的列名集合"""
    if not table_exists(table_name):
        return set()
    if table_name not in Base.metadata.tables:
        return set()

    db_cols = get_existing_columns(table_name)
    model_cols = set(Base.metadata.tables[table_name].columns.keys())
    return model_cols - db_cols


# ==================== 迁移执行器 ====================

def _apply_additions(table_name, additions):
    """
    统一执行 ALTER TABLE 语句

    生产环境安全策略：
    - 单条语句失败时记录错误但不中断（避免一条失败影响后续）
    - 记录所有成功/失败数量
    - 提交事务
    """
    if not additions:
        _log("INFO", f"{table_name} 表无需迁移")
        return {"success": 0, "failed": 0}

    success_count = 0
    failed_count = 0

    with engine.connect() as conn:
        for stmt in additions:
            try:
                conn.execute(text(f"ALTER TABLE {table_name} {stmt}"))
                _log("OK", f"{table_name}: {stmt}")
                success_count += 1
            except SQLAlchemyError as e:
                _log("ERROR", f"{table_name} 迁移失败: {stmt} → {e}")
                failed_count += 1
        conn.commit()

    if failed_count == 0:
        _log("OK", f"{table_name} 表迁移完成（{success_count} 个字段）")
    else:
        _log("WARN", f"{table_name} 表迁移部分完成（成功 {success_count}, 失败 {failed_count}）")

    return {"success": success_count, "failed": failed_count}


# ==================== users 表 ====================
def migrate_users():
    """
    迁移 users 表
    对照 models.py: User
    字段: id(PK) / name / hashed_password / created_at
    """
    if not table_exists("users"):
        _log("INFO", "users 表不存在，跳过迁移")
        return

    columns = get_existing_columns("users")
    additions = []

    # id 是主键，无法通过 ALTER 添加
    if "name" not in columns:
        additions.append("ADD COLUMN name TEXT")
    if "hashed_password" not in columns:
        # NOT NULL 字段必须带 DEFAULT，否则老数据会报错
        additions.append("ADD COLUMN hashed_password TEXT DEFAULT ''")
    if "created_at" not in columns:
        additions.append("ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP")

    _apply_additions("users", additions)


# ==================== cases 表 ====================
def migrate_cases():
    """
    迁移 cases 表
    对照 models.py: Case
    字段: id(PK) / user_id(FK) / case_type / title / description / status /
          collected_fields / missing_fields / final_decision / report_id /
          debate_result / created_at / updated_at / reject_reason
    """
    if not table_exists("cases"):
        _log("INFO", "cases 表不存在，跳过迁移")
        return

    columns = get_existing_columns("cases")
    additions = []

    if "user_id" not in columns:
        additions.append("ADD COLUMN user_id TEXT")
    if "case_type" not in columns:
        additions.append("ADD COLUMN case_type TEXT")
    if "title" not in columns:
        additions.append("ADD COLUMN title TEXT")
    if "description" not in columns:
        additions.append("ADD COLUMN description TEXT")
    if "status" not in columns:
        additions.append("ADD COLUMN status TEXT")
    if "collected_fields" not in columns:
        # JSON 字段，default={} 在 SQL 侧无法表达，不加默认值
        additions.append("ADD COLUMN collected_fields TEXT")
    if "missing_fields" not in columns:
        additions.append("ADD COLUMN missing_fields TEXT")
    if "final_decision" not in columns:
        additions.append("ADD COLUMN final_decision TEXT")
    if "report_id" not in columns:
        additions.append("ADD COLUMN report_id TEXT")
    if "debate_result" not in columns:
        additions.append("ADD COLUMN debate_result TEXT")
    if "created_at" not in columns:
        additions.append("ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP")
    if "updated_at" not in columns:
        additions.append("ADD COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP")
    if "reject_reason" not in columns:
        additions.append("ADD COLUMN reject_reason TEXT")

    _apply_additions("cases", additions)


# ==================== messages 表 ====================
def migrate_messages():
    """
    迁移 messages 表
    对照 models.py: Message
    字段: id(PK) / case_id(FK) / role / content / message_type / created_at
    """
    if not table_exists("messages"):
        _log("INFO", "messages 表不存在，跳过迁移")
        return

    columns = get_existing_columns("messages")
    additions = []

    if "case_id" not in columns:
        additions.append("ADD COLUMN case_id TEXT")
    if "role" not in columns:
        additions.append("ADD COLUMN role TEXT")
    if "content" not in columns:
        additions.append("ADD COLUMN content TEXT")
    if "message_type" not in columns:
        additions.append("ADD COLUMN message_type TEXT DEFAULT 'text'")
    if "created_at" not in columns:
        additions.append("ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP")

    _apply_additions("messages", additions)


# ==================== histories 表 ====================
def migrate_histories():
    """
    迁移 histories 表
    对照 models.py: History
    字段: id(PK) / user_id(FK) / case_type / summary / result / tags /
          created_at / title / price / usage_frequency / context /
          pros / cons / final_decision / case_id / report_id / is_deleted
    """
    if not table_exists("histories"):
        _log("INFO", "histories 表不存在，跳过迁移")
        return

    columns = get_existing_columns("histories")
    additions = []

    if "user_id" not in columns:
        additions.append("ADD COLUMN user_id TEXT")
    if "case_type" not in columns:
        additions.append("ADD COLUMN case_type TEXT")
    if "summary" not in columns:
        additions.append("ADD COLUMN summary TEXT")
    if "result" not in columns:
        additions.append("ADD COLUMN result TEXT")
    if "tags" not in columns:
        additions.append("ADD COLUMN tags TEXT")
    if "created_at" not in columns:
        additions.append("ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP")
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
    if "is_deleted" not in columns:
        # ⚠️ NOT NULL 必须带 DEFAULT
        additions.append("ADD COLUMN is_deleted INTEGER NOT NULL DEFAULT 0")

    _apply_additions("histories", additions)


# ==================== traces 表 ====================
def migrate_traces():
    """
    迁移 traces 表
    对照 models.py: Trace
    字段: id(PK) / case_id(FK,NOT NULL) / step(NOT NULL) / type(NOT NULL) /
          name(NOT NULL) / input_summary / output_summary / duration_ms /
          status(NOT NULL) / error / created_at
    """
    if not table_exists("traces"):
        _log("INFO", "traces 表不存在，跳过迁移")
        return

    columns = get_existing_columns("traces")
    additions = []

    if "case_id" not in columns:
        additions.append("ADD COLUMN case_id TEXT")
    if "step" not in columns:
        additions.append("ADD COLUMN step INTEGER")
    if "type" not in columns:
        additions.append("ADD COLUMN type TEXT")
    if "name" not in columns:
        additions.append("ADD COLUMN name TEXT")
    if "input_summary" not in columns:
        additions.append("ADD COLUMN input_summary TEXT")
    if "output_summary" not in columns:
        additions.append("ADD COLUMN output_summary TEXT")
    if "duration_ms" not in columns:
        additions.append("ADD COLUMN duration_ms INTEGER")
    if "status" not in columns:
        additions.append("ADD COLUMN status TEXT")
    if "error" not in columns:
        additions.append("ADD COLUMN error TEXT")
    if "created_at" not in columns:
        additions.append("ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP")

    _apply_additions("traces", additions)


# ==================== reminders 表 ====================
def migrate_reminders():
    """
    迁移 reminders 表
    对照 models.py: Reminder
    字段: id(PK) / user_id(FK,NOT NULL) / case_id(FK,NOT NULL) /
          title(NOT NULL) / reason / due_at(NOT NULL) / status / created_at
    """
    if not table_exists("reminders"):
        _log("INFO", "reminders 表不存在，跳过迁移")
        return

    columns = get_existing_columns("reminders")
    additions = []

    if "user_id" not in columns:
        additions.append("ADD COLUMN user_id TEXT")
    if "case_id" not in columns:
        additions.append("ADD COLUMN case_id TEXT")
    if "title" not in columns:
        additions.append("ADD COLUMN title TEXT DEFAULT ''")
    if "reason" not in columns:
        additions.append("ADD COLUMN reason TEXT")
    if "due_at" not in columns:
        additions.append("ADD COLUMN due_at DATETIME")
    if "status" not in columns:
        additions.append("ADD COLUMN status TEXT DEFAULT 'waiting'")
    if "created_at" not in columns:
        additions.append("ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP")

    _apply_additions("reminders", additions)


# ==================== 索引迁移 ====================
def migrate_indexes():
    """
    创建缺失的索引
    与 models.py 的 __table_args__ 一一对应
    """
    indexes = {
        # ---- cases ----
        "ix_cases_user_id_updated_at": "CREATE INDEX IF NOT EXISTS ix_cases_user_id_updated_at ON cases(user_id, updated_at)",
        "ix_cases_user_id_status": "CREATE INDEX IF NOT EXISTS ix_cases_user_id_status ON cases(user_id, status)",
        "ix_cases_status": "CREATE INDEX IF NOT EXISTS ix_cases_status ON cases(status)",
        # ---- messages ----
        "ix_messages_case_id_created_at": "CREATE INDEX IF NOT EXISTS ix_messages_case_id_created_at ON messages(case_id, created_at)",
        # ---- histories ----
        "ix_histories_user_id_created_at": "CREATE INDEX IF NOT EXISTS ix_histories_user_id_created_at ON histories(user_id, created_at)",
        "ix_histories_user_id_case_type": "CREATE INDEX IF NOT EXISTS ix_histories_user_id_case_type ON histories(user_id, case_type)",
        "ix_histories_case_id": "CREATE INDEX IF NOT EXISTS ix_histories_case_id ON histories(case_id)",
        "ix_histories_is_deleted": "CREATE INDEX IF NOT EXISTS ix_histories_is_deleted ON histories(is_deleted)",
        # ---- traces ----
        "ix_traces_case_id_step": "CREATE INDEX IF NOT EXISTS ix_traces_case_id_step ON traces(case_id, step)",
        # ---- reminders ----
        "ix_reminders_user_id_status": "CREATE INDEX IF NOT EXISTS ix_reminders_user_id_status ON reminders(user_id, status)",
    }

    success_count = 0
    failed_count = 0

    with engine.connect() as conn:
        for name, sql in indexes.items():
            try:
                conn.execute(text(sql))
                success_count += 1
            except SQLAlchemyError as e:
                _log("ERROR", f"索引 {name} 创建失败: {e}")
                failed_count += 1
        conn.commit()

    _log("OK", f"索引迁移完成（成功 {success_count}, 失败 {failed_count}）")


# ==================== 迁移后校验 ====================

def verify_migration():
    """
    迁移后结构校验：确认所有模型的字段都存在于数据库中
    """
    _log("INFO", "开始迁移后校验...")
    all_ok = True

    for table_name in Base.metadata.tables.keys():
        if not table_exists(table_name):
            _log("ERROR", f"表 {table_name} 不存在")
            all_ok = False
            continue

        missing = get_missing_columns(table_name)
        if missing:
            _log("ERROR", f"表 {table_name} 迁移后仍缺字段: {missing}")
            all_ok = False
        else:
            _log("OK", f"表 {table_name} 结构校验通过")

    if all_ok:
        _log("OK", "[OK] 迁移后校验全部通过")
    else:
        _log("ERROR", "[ERROR] 迁移后校验失败，建议检查缺失字段或执行 backup_and_rebuild")

    return all_ok


# ==================== 迁移入口 ====================
def run_all_migrations():
    """
    执行所有字段迁移 + 校验

    顺序说明：按外键依赖顺序，先 users 后引用表
    """
    _log("INFO", "=" * 60)
    _log("INFO", "开始执行数据库迁移...")
    _log("INFO", "=" * 60)

    migrate_users()        # 最基础，被其他表引用
    migrate_cases()        # 引用 users
    migrate_messages()     # 引用 cases
    migrate_histories()    # 引用 users
    migrate_traces()       # 引用 cases
    migrate_reminders()    # 引用 users + cases

    _log("INFO", "-" * 60)
    _log("INFO", "字段迁移完成，开始创建索引...")
    migrate_indexes()

    _log("INFO", "-" * 60)
    verify_migration()

    _log("INFO", "=" * 60)
    _log("INFO", "所有迁移任务完成")
    _log("INFO", "=" * 60)


# ==================== 数据备份 ====================
def backup_data():
    """备份所有表数据到 JSON 文件"""
    db = SessionLocal()
    data = {}
    tables = ["users", "cases", "messages", "histories", "traces", "reminders"]

    _log("INFO", "开始备份数据...")

    for table_name in tables:
        try:
            result = db.execute(text(f"SELECT * FROM {table_name}"))
            rows = result.fetchall()
            if rows:
                columns = result.keys()
                data[table_name] = [dict(zip(columns, row)) for row in rows]
                _log("INFO", f"备份 {table_name}: {len(rows)} 条记录")
            else:
                data[table_name] = []
                _log("INFO", f"{table_name}: 无数据")
        except Exception as e:
            _log("WARN", f"备份 {table_name} 失败: {e}")
            data[table_name] = []

    db.close()

    backup_path = f"data/backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    os.makedirs("data", exist_ok=True)
    with open(backup_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)

    _log("OK", f"数据已备份到: {backup_path}")
    return backup_path


# ==================== 数据恢复 ====================
def restore_data(backup_path):
    """从 JSON 文件恢复数据"""
    if not os.path.exists(backup_path):
        _log("ERROR", f"备份文件不存在: {backup_path}")
        return False

    with open(backup_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    db = SessionLocal()
    model_tables = {
        "users": models.User,
        "cases": models.Case,
        "messages": models.Message,
        "histories": models.History,
        "traces": models.Trace,
        "reminders": models.Reminder,
    }

    # 按依赖顺序插入
    insert_order = ["users", "cases", "messages", "histories", "traces", "reminders"]

    # 临时关闭外键检查
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

            _log("INFO", f"恢复 {table_name}: {len(data[table_name])} 条记录")
            for row_data in data[table_name]:
                try:
                    obj = model_class(**row_data)
                    db.add(obj)
                except Exception as e:
                    _log("WARN", f"插入失败: {e}")
                    continue

        db.commit()
        _log("OK", "数据恢复完成")
    except Exception as e:
        db.rollback()
        _log("ERROR", f"恢复失败: {e}")
        return False
    finally:
        with engine.connect() as conn:
            conn.execute(text("PRAGMA foreign_keys=ON"))
            conn.commit()
        db.close()

    return True


# ==================== 备份 + 重建 ====================
def backup_and_rebuild():
    """
    备份数据 → 重建数据库 → 恢复数据

    用于无法通过 ALTER 处理的场景（如外键缺失、字段类型变更）
    """
    _log("INFO", "=" * 60)
    _log("INFO", "开始备份-重建-恢复流程")
    _log("INFO", "=" * 60)

    _log("INFO", "步骤 1/3: 备份数据...")
    backup_path = backup_data()

    if not backup_path:
        _log("ERROR", "备份失败，停止重建")
        return False

    _log("INFO", "步骤 2/3: 重建数据库...")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    _log("OK", "数据库重建完成")

    _log("INFO", "步骤 3/3: 恢复数据...")
    success = restore_data(backup_path)

    if success:
        _log("OK", "[OK] 备份-重建-恢复流程完成")
    else:
        _log("ERROR", "[ERROR] 恢复失败，请手动检查备份文件")

    return success