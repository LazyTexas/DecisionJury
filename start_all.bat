@echo off
chcp 65001 >nul
title DecisionJury 项目启动器

echo ============================================
echo   DecisionJury 项目一键启动脚本
echo   前端: http://127.0.0.1:5173
echo   后端: http://127.0.0.1:8000
echo   API文档: http://127.0.0.1:8000/docs
echo ============================================
echo.

cd /d "%~dp0"

:: ========== 后端启动 ==========
echo [1/2] 启动后端服务...

:: 检查是否有虚拟环境，没有则创建
if not exist backend\venv\Scripts\activate.bat (
    echo [警告] 未找到虚拟环境，正在创建...
    cd backend
    python -m venv venv
    call venv\Scripts\activate.bat
    pip install fastapi uvicorn sqlalchemy pydantic python-dotenv
    cd ..
)

:: 启动后端（在项目根目录启动，使用 backend.main:app）
start "DecisionJury Backend" cmd /k "cd /d %~dp0 && call backend\venv\Scripts\activate.bat && uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000"

:: 等待后端启动
timeout /t 3 /nobreak >nul

:: ========== 前端启动 ==========
echo [2/2] 启动前端服务...

if not exist frontend\node_modules (
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
echo   API文档: http://127.0.0.1:8000/docs
echo ============================================
echo.
echo [提示] 如需停止服务，请关闭对应的命令行窗口。
echo.

pause