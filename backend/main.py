# backend/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect
from sqlalchemy.exc import OperationalError
from backend.database import engine, Base
from backend import models
from backend.routers import cases, chat, debate, tools, watchlist, history


def check_database():
    """启动时检测数据库结构，自动修复不兼容问题"""
    try:
        inspector = inspect(engine)
        existing_tables = inspector.get_table_names()
        print(f"📋 现有表: {existing_tables}")

        required_tables = ["cases", "messages", "histories", "traces", "reminders"]
        missing_tables = [t for t in required_tables if t not in existing_tables]

        if missing_tables:
            print(f"⚠️  缺少表: {missing_tables}，正在重建数据库...")
            Base.metadata.create_all(bind=engine)
            print("✅ 数据库重建完成")
            return

        if "cases" in existing_tables:
            columns = [c["name"] for c in inspector.get_columns("cases")]
            if "debate_result" not in columns:
                print("⚠️  cases 表缺少 debate_result 字段，正在重建数据库...")
                Base.metadata.create_all(bind=engine)
                print("✅ 数据库重建完成")
                return

        if "histories" in existing_tables:
            columns = [c["name"] for c in inspector.get_columns("histories")]
            required_fields = ["title", "price", "context", "pros", "cons", "report_id"]
            missing_fields = [f for f in required_fields if f not in columns]
            if missing_fields:
                print(f"⚠️  histories 表缺少字段: {missing_fields}，正在重建数据库...")
                Base.metadata.create_all(bind=engine)
                print("✅ 数据库重建完成")
                return

        print("✅ 数据库结构检查通过")

    except OperationalError as e:
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

# ===== 注册路由 =====
app.include_router(cases.router)
app.include_router(chat.router)
app.include_router(debate.router)
app.include_router(tools.router)
app.include_router(watchlist.router)
app.include_router(history.router)
