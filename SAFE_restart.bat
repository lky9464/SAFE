@echo off
chcp 65001 >nul
title SAFE System Restart
cd /d "%~dp0"

set "PYTHON=python"
where python >nul 2>&1
if errorlevel 1 (
    set "PYTHON=%LocalAppData%\Programs\Python\Python312\python.exe"
    if not exist "%PYTHON%" (
        echo [오류] Python을 찾을 수 없습니다.
        pause
        exit /b 1
    )
)
set "PORT=8000"

echo [SAFE] Stopping process on port %PORT%...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":%PORT% " ^| findstr "LISTENING"') do (
    echo   kill PID %%p
    taskkill /PID %%p /F >nul 2>&1
)

timeout /t 2 /nobreak >nul

echo [SAFE] Starting http://127.0.0.1:%PORT%
start "SAFE System" "%PYTHON%" main.py
echo [SAFE] Restart done
