@echo off
cd /d "%~dp0"

if not exist ".venv\Scripts\pythonw.exe" (
    call "%~dp0setup.bat"
)

if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" -m hotkey.app
)
