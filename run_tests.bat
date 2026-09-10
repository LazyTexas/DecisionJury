@echo off
title DecisionJury Tests
setlocal

rem One-click isolated test runner.
rem
rem Why the environment variables below matter: without them the pytest process
rem loads the project .env, so tests would run against the daily SQLite database
rem and would call the real DeepSeek API. See docs/05_TestPlan.md section 2.
rem
rem Usage:
rem   run_tests.bat                                  full suite under tests\
rem   run_tests.bat tests\test_input_parser.py       single file
rem   run_tests.bat tests -k savings                 extra pytest args

cd /d "%~dp0"

set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" (
    echo [ERROR] Project venv .venv not found. Run: uv sync
    pause
    exit /b 1
)

rem Isolated environment: in-memory DB, no dotenv, no API key, no live RAG history.
set "DATABASE_URL=sqlite:///:memory:"
set "ENV=development"
set "DEEPSEEK_API_KEY="
set "PYTHON_DOTENV_DISABLED=1"
set "RAG_LIVE_RECORDS=0"
set "PYTHONIOENCODING=utf-8"

set "PYTEST_TARGET=%*"
if "%PYTEST_TARGET%"=="" set "PYTEST_TARGET=tests"

echo ============================================
echo   DecisionJury isolated test run
echo   target     : %PYTEST_TARGET%
echo   database   : in-memory (daily db untouched)
echo   api key    : disabled (local rules / mock)
echo   live RAG   : off
echo ============================================
echo.

"%PYTHON_EXE%" -m pytest -p no:cacheprovider %PYTEST_TARGET% -q
set "EXIT_CODE=%ERRORLEVEL%"

echo.
if "%EXIT_CODE%"=="0" (
    echo [OK] All tests passed.
) else (
    echo [FAIL] pytest exited with code %EXIT_CODE%.
    echo        tests\test_migrate.py failures are documented known issues,
    echo        see docs\05_TestPlan.md section 9.
)

rem Keep the window open when double-clicked; exit quietly when called from a cmd window.
rem Use the absolute find.exe path so a git-bash PATH cannot shadow it with the Unix find.
echo %cmdcmdline% | "%SystemRoot%\System32\find.exe" /i "%~nx0" >nul
if not errorlevel 1 pause

exit /b %EXIT_CODE%
