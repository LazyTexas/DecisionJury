@echo off
title DecisionJury Launcher

echo ============================================
echo   DecisionJury one-click launcher
echo   Frontend: http://127.0.0.1:5173
echo   Backend:  http://127.0.0.1:8000
echo   RAG:      http://127.0.0.1:8001
echo   API docs: http://127.0.0.1:8000/docs
echo ============================================
echo.

cd /d "%~dp0"

rem Always use the project root uv virtualenv (.venv), not backend/venv or rag/venv.
set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"

if not exist "%PYTHON_EXE%" (
    echo [WARN] Project venv .venv not found. Creating and installing dependencies...
    where uv >nul 2>&1
    if not errorlevel 1 (
        echo [INFO] uv detected. Running: uv sync
        uv sync
    ) else (
        echo [INFO] uv not detected. Falling back to python -m venv...
        python -m venv .venv
        call .venv\Scripts\activate.bat
        echo [BACKEND] Installing backend requirements...
        pip install -r backend\requirements.txt
        echo [RAG] Installing rag requirements...
        pip install -r rag\requirements.txt
    )
    if not exist "%PYTHON_EXE%" (
        echo [ERROR] Failed to create venv. Please run: uv sync
        pause
        exit /b 1
    )
)

rem ========== 1. Start Backend (B + C modules) ==========
rem Use cmd /c (not /k) so the window closes automatically once the process is stopped.
echo [1/3] Starting backend...
start "DecisionJury Backend" cmd /c "cd /d %~dp0 && .venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000"

timeout /t 3 /nobreak >nul

rem ========== 2. Start RAG service (D module) ==========
echo [2/3] Starting RAG...
start "DecisionJury RAG" cmd /c "cd /d %~dp0rag && ..\.venv\Scripts\python.exe -m uvicorn retriever:app --host 127.0.0.1 --port 8001"

timeout /t 2 /nobreak >nul

rem ========== 3. Start Frontend (A module) ==========
rem Run vite directly (not via npm) so the window closes when the dev server is killed.
echo [3/3] Starting frontend...
if not exist "frontend\node_modules" (
    echo [WARN] Frontend deps not installed. Running npm install...
    cd frontend
    call npm install
    cd ..
)

start "DecisionJury Frontend" cmd /c "cd /d %~dp0frontend && node node_modules/vite/bin/vite.js"

rem Wait a bit for the services to come up, then open the default browser.
echo Waiting for services to be ready, then opening browser...
timeout /t 8 /nobreak >nul
start "" http://localhost:5173

echo.
echo ============================================
echo   [OK] All services started! Browser opened.
echo   Frontend: http://localhost:5173
echo   Backend:  http://127.0.0.1:8000
echo   RAG:      http://127.0.0.1:8001
echo   API:      http://127.0.0.1:8000/docs
echo ============================================
echo.
echo [HINT] Run stop_all.bat to stop all services and close the windows.
echo.
pause
