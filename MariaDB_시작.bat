@echo off
chcp 65001 >nul
title SAFE MariaDB (Portable)
REM MariaDB 설치 경로 — 필요 시 수정
set "BASE=%USERPROFILE%\mariadb\mariadb-12.3.2-winx64"
set "INI=%USERPROFILE%\mariadb\my.ini"

if not exist "%BASE%\bin\mysqld.exe" (
    echo [오류] mysqld.exe 를 찾을 수 없습니다.
    echo 경로: %BASE%\bin\mysqld.exe
    pause
    exit /b 1
)

echo MariaDB 시작 중... (localhost:3306)

REM mysqld를 콘솔에서 분리해 창 종료가 정상 동작하도록 함
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%BASE%\bin\mysqld.exe' -ArgumentList '--defaults-file=%INI%' -WindowStyle Hidden"

timeout /t 3 /nobreak >nul
echo MariaDB 실행됨. (백그라운드)
echo 이 창은 닫아도 MariaDB는 계속 실행됩니다.
echo 종료: 작업 관리자에서 mysqld.exe 종료
echo.
echo 아무 키나 누르면 이 창을 닫습니다.
pause >nul
exit
