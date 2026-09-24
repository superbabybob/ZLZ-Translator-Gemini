@echo off
chcp 65001 >nul
cd /d "%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1"
if %errorlevel% neq 0 (
    echo.
    echo ============================================================
    echo [!] เกิดข้อผิดพลาดในการติดตั้ง (Exit Code: %errorlevel%)
    echo ============================================================
    pause
)
