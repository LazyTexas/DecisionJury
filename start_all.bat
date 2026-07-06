@echo off
chcp 65001 >nul
title DecisionJury 项目启动器

echo ============================================
echo   DecisionJury 项目一键启动脚本
echo   前端: http://127.0.0.1:5173
echo   后端: http://127.0.0.1:8000
echo   RAG:  http://127.0.0.1:8001
echo   API文档: http://127.0.0.1:8000/docs
echo ============================================
echo.

cd /d "%~dp0"

:: ========== 1. 启动后端（B 模块） ==========
echo [1/3] 启动后端服务...

if not exist "backend\venv\Scripts\activate.bat" (
    echo [警告] 未找到后端虚拟环境，正在创建...
    cd backend
    python -m venv venv
    cd ..
)

start "DecisionJury Backend" cmd /k "cd /d %~dp0 && call backend\venv\Scripts\activate.bat && echo [后端] 检查并安装依赖... && pip install -r backend\requirements.txt && echo [后端] 启动服务... && uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000"

timeout /t 3 /nobreak >nul

:: ========== 2. 启动 RAG 服务（D 模块） ==========
echo [2/3] 启动 RAG 检索服务...

if not exist "rag\venv\Scripts\activate.bat" (
    echo [警告] 未找到 RAG 虚拟环境，正在创建...
    cd rag
    python -m venv venv
    cd ..
)

start "DecisionJury RAG" cmd /k "cd /d %~dp0rag && call venv\Scripts\activate.bat && echo [RAG] 检查并安装依赖... && pip install -r requirements.txt && echo [RAG] 启动服务... && uvicorn retriever:app --reload --host 127.0.0.1 --port 8001"

timeout /t 2 /nobreak >nul

:: ========== 3. 启动前端（A 模块） ==========
echo [3/3] 启动前端服务...

if not exist "frontend\node_modules" (
    echo [警告] 前端依赖未安装，正在安装...
    cd frontend
    call npm install
    cd ..
)

start "DecisionJury Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"

echo.
echo ============================================
echo   ✅ 项目启动完成！
echo   前端: http://127.0.0.1:5173
echo   后端: http://127.0.0.1:8000
echo   RAG:  http://127.0.0.1:8001
echo   API文档: http://127.0.0.1:8000/docs
echo ============================================
echo.
echo [提示] 如需停止服务，请关闭对应的命令行窗口。
pause