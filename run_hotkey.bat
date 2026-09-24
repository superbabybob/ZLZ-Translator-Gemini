@echo off
cd /d "%~dp0"

if not exist ".venv\Scripts\pythonw.exe" call "%~dp0setup.bat"

if not exist ".venv\Scripts\python.exe" (
    echo [!] Python environment not found. Please run setup.bat first.
    pause
    exit /b 1
)

rem Verify dependencies
".venv\Scripts\python.exe" -c "import pystray, keyboard" >nul 2>nul
if %errorlevel% neq 0 (
    echo [!] Required packages missing. Launching setup.bat...
    call "%~dp0setup.bat"
    exit /b %errorlevel%
)

start "" ".venv\Scripts\pythonw.exe" -m hotkey.app
