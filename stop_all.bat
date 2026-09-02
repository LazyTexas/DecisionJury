@echo off
title DecisionJury Stop All

echo Stopping DecisionJury services...
echo.

rem Kill the processes listening on the project ports.
rem Because the launcher uses cmd /c (not /k), killing the foreground process
rem makes each cmd window close automatically - no title/PowerShell matching needed.
for %%P in (8000 8001 5173) do call :kill_port %%P

echo.
echo Done. All DecisionJury services should have been stopped.
echo.
exit /b 0

:kill_port
setlocal
set "P=%~1"
for /f "tokens=5" %%A in ('netstat -ano ^| findstr /r /c:":%P% .*LISTENING"') do (
    echo Killing PID %%A on port %P% ...
    taskkill /T /F /PID %%A >nul 2>&1
)
endlocal
exit /b 0
