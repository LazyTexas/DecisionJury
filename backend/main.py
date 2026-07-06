# backend/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.database import engine, Base
from backend.routers import cases, chat, debate
from backend import models

# 创建数据库表
Base.metadata.create_all(bind=engine)

app = FastAPI(title="DecisionJury API", version="1.0.0")

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