@echo off
chcp 65001 >nul
title Dashboard Watchdog

cd /d "%~dp0"

echo ========================================
echo   Dashboard 守护进程
echo   每 30 秒检查一次服务器状态
echo   如挂掉自动重启
echo ========================================
echo.

:check
timeout /t 30 /nobreak >nul

curl -s -o NUL -w "%%{http_code}" http://localhost:8090/api/health 2>nul > %temp%\dashboard_status.txt
set /p status=<%temp%\dashboard_status.txt
del %temp%\dashboard_status.txt

if "%status%"=="200" (
    echo [%date% %time%] 服务器运行正常
) else (
    echo [%date% %time%] 服务器无响应 (status=%status%)，正在重启...
    taskkill /F /IM python.exe /FI "WINDOWTITLE eq Dashboard*" 2>nul
    timeout /t 2 /nobreak >nul
    start "Dashboard Server" cmd /c start_dashboard.bat
    echo [%date% %time%] 已触发重启
)

goto check
