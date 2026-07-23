@echo off
chcp 65001 >nul
title Dashboard Server - Auto Restart

cd /d "%~dp0"

echo ========================================
echo   流量监控面板服务器
echo   端口: 8090
echo   地址: http://localhost:8090/dashboard.html
echo ========================================
echo.
echo 按 Ctrl+C 停止服务器（会询问是否终止）
echo.

:loop
echo [%date% %time%] 启动服务器...
python dashboard_server.py
echo.
echo [%date% %time%] 服务器已停止，5秒后自动重启...
timeout /t 5 /nobreak >nul
goto loop
