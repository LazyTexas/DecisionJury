from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from database import engine, Base, get_db
import models

# 创建数据库表
Base.metadata.create_all(bind=engine)

app = FastAPI(title="DecisionJury API", version="1.0.0")

# CORS 配置（允许前端调用）
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
    return {"status": "ok", "message": "DecisionJury API is running"}

# ===== 导入路由 =====
from routers import cases, chat

app.include_router(cases.router)
app.include_router(chat.router)