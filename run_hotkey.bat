@echo off
chcp 65001 >nul
cd /d "%~dp0"

if not exist ".venv\Scripts\pythonw.exe" (
    call "%~dp0setup.bat"
)

if not exist ".venv\Scripts\python.exe" (
    echo [!] ไม่พบสภาพแวดล้อม Python (.venv) กรุณารัน setup.bat ก่อน
    pause
    exit /b 1
)

:: ตรวจสอบความพร้อมของไลบรารี หากขาดให้เรียก setup.bat อัตโนมัติ
".venv\Scripts\python.exe" -c "import pystray, keyboard" >nul 2>nul
if %errorlevel% neq 0 (
    echo [!] ยังไม่ได้ติดตั้งไลบรารีครบถ้วน กำลังเรียก setup.bat...
    call "%~dp0setup.bat"
    exit /b %errorlevel%
)

start "" ".venv\Scripts\pythonw.exe" -m hotkey.app
