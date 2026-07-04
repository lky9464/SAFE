@echo off
chcp 65001 >nul
title SAFE System
cd /d "%~dp0"

REM PATH 의 python 사용 (없으면 일반 설치 경로 시도)
set "PYTHON=python"
where python >nul 2>&1
if errorlevel 1 (
    set "PYTHON=%LocalAppData%\Programs\Python\Python312\python.exe"
    if not exist "%PYTHON%" (
        echo [오류] Python을 찾을 수 없습니다.
        echo PATH에 python을 추가하거나 이 파일의 PYTHON 경로를 수정하세요.
        pause
        exit /b 1
    )
)

echo ========================================
echo   SAFE - Local Subsidy AI Fraud Detection
echo   로컬 전용 (내부자료 외부 전송 없음)
echo ========================================
echo.

"%PYTHON%" --version
if errorlevel 1 (
    echo [오류] Python 실행에 실패했습니다.
    pause
    exit /b 1
)

echo.
echo 서버 시작 중... http://127.0.0.1:8000
echo 브라우저에서 위 주소로 접속하세요.
echo 종료: Ctrl+C
echo.

"%PYTHON%" main.py
pause
