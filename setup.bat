@echo off
cd /d "%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1"
if %errorlevel% neq 0 (
    echo.
    echo ============================================================
    echo [ERROR] Setup failed with exit code: %errorlevel%
    echo ============================================================
    pause
)
