# backend/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect
from sqlalchemy.exc import OperationalError, SQLAlchemyError, IntegrityError
from backend.database import engine, Base
from backend import models
from backend.routers import cases, chat, debate, tools, watchlist, history
from pydantic import ValidationError
import traceback
import json
from backend.schemas import ApiResponse, ErrorResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


def check_database():
    """启动时检测数据库结构，自动修复不兼容问题"""
    try:
        inspector = inspect(engine)
        existing_tables = set(inspector.get_table_names())
        print(f"📋 现有表: {existing_tables}")

        metadata = Base.metadata
        required_tables = set(metadata.tables.keys())
        print(f"📋 模型定义表: {required_tables}")

        # ===== 1. 检查是否有表缺失 =====
        missing_tables = required_tables - existing_tables
        if missing_tables:
            print(f"⚠️  缺少表: {missing_tables}，正在重建数据库...")
            Base.metadata.create_all(bind=engine)
            print("✅ 数据库重建完成")
            return

        # ===== 2. 检查各表的字段是否完整 =====
        need_rebuild = False
        for table_name in required_tables:
            model_columns = set(metadata.tables[table_name].columns.keys())
            db_columns = set(c["name"] for c in inspector.get_columns(table_name))
            if db_columns != model_columns:
                missing = model_columns - db_columns
                if missing:
                    print(f"⚠️  表 {table_name} 缺少字段: {missing}")
                need_rebuild = True

        if need_rebuild:
            print("🔨 正在重建数据库以同步表结构...")
            Base.metadata.create_all(bind=engine)
            print("✅ 数据库重建完成")
            return

        # ===== 3. 检查外键约束 =====
        need_rebuild_fk = False
        for table_name in required_tables:
            if table_name not in existing_tables:
                continue
            model_fks = metadata.tables[table_name].foreign_keys
            if not model_fks:
                continue
            db_fks = inspector.get_foreign_keys(table_name)
            for fk in model_fks:
                referred_table = fk.column.table.name
                referred_col = fk.column.name
                has_fk = any(
                    f.get("referred_table") == referred_table and
                    f.get("referred_columns") == [referred_col]
                    for f in db_fks
                )
                if not has_fk:
                    print(f"⚠️  表 {table_name} 缺少外键: {fk.parent.name} → {referred_table}.{referred_col}")
                    need_rebuild_fk = True

        if need_rebuild_fk:
            print("🔨 正在重建数据库以添加外键约束...")
            Base.metadata.create_all(bind=engine)
            print("✅ 数据库重建完成")
            return

        # ===== 4. 检查索引是否存在 =====
        need_rebuild_idx = False
        for table_name in required_tables:
            if table_name not in existing_tables:
                continue
            model_indexes = [idx.name for idx in metadata.tables[table_name].indexes]
            if not model_indexes:
                continue
            db_indexes = [idx["name"] for idx in inspector.get_indexes(table_name)]
            missing_indexes = [idx for idx in model_indexes if idx not in db_indexes]
            if missing_indexes:
                print(f"⚠️  表 {table_name} 缺少索引: {missing_indexes}")
                need_rebuild_idx = True

        if need_rebuild_idx:
            print("🔨 正在重建数据库以添加索引...")
            Base.metadata.create_all(bind=engine)
            print("✅ 数据库重建完成")
            return

        print("✅ 数据库结构检查通过")

    except SQLAlchemyError as e:
        if "no such table" in str(e):
            print("ℹ️  数据库未初始化，正在创建...")
            Base.metadata.create_all(bind=engine)
            print("✅ 数据库初始化完成")
        else:
            raise e


# ===== 新的 lifespan 上下文管理器 =====
@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- 启动逻辑 (Startup) ---
    print("🚀 DecisionJury API 正在启动...")
    check_database()
    print("✅ API 启动完成")
    yield  # 应用在此处运行
    # --- 关闭逻辑 (Shutdown) ---
    print("🛑 DecisionJury API 正在关闭...")
    # 如果有需要清理的资源（如数据库连接池），可以放在这里


# ===== 创建 FastAPI 实例时传入 lifespan =====
app = FastAPI(
    title="DecisionJury API",
    version="1.0.0",
    lifespan=lifespan  # <-- 关键改动：使用 lifespan 参数
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===== 健康检查 =====
@app.get("/api/health")
def health_check():
    return {
        "success": True,
        "data": {"status": "ok", "version": "1.0.0"},
        "message": ""
    }

# ========== 全局异常处理器 ==========

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = []
    for error in exc.errors():
        field = ".".join(str(loc) for loc in error["loc"])
        msg = error.get("msg", "字段验证失败")
        errors.append(f"{field}: {msg}")

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "data": None,
            "message": "VALIDATION_ERROR",
            "details": errors,
        }
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "data": None,
            "message": exc.detail,
        }
    )


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    print(f"[ERROR] 数据库错误: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "data": None,
            "message": "DATABASE_ERROR",
        }
    )


@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError):
    print(f"[ERROR] 数据库完整性错误: {exc}")
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "success": False,
            "data": None,
            "message": "INTEGRITY_ERROR",
        }
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    print(f"[ERROR] 未捕获异常: {type(exc).__name__}: {exc}")
    import traceback
    print(traceback.format_exc())
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "data": None,
            "message": "INTERNAL_SERVER_ERROR",
        }
    )

@app.exception_handler(StarletteHTTPException)
async def starlette_http_exception_handler(request: Request, exc: StarletteHTTPException):
    """处理 Starlette 的 HTTP 异常（包括 404）"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "data": None,
            "message": exc.detail if exc.detail else "Not Found",
        }
    )

@app.exception_handler(json.JSONDecodeError)
async def json_decode_error_handler(request: Request, exc: json.JSONDecodeError):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "success": False,
            "data": None,
            "message": "INVALID_JSON_FORMAT",
            "details": f"JSON 解析错误: {exc.msg}",
        }
    )

# ===== 注册路由 =====
app.include_router(cases.router)
app.include_router(chat.router)
app.include_router(debate.router)
app.include_router(tools.router)
app.include_router(watchlist.router)
app.include_router(history.router)
