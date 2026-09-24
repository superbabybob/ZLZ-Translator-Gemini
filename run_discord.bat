@echo off
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    call "%~dp0setup.bat"
)

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -m discord_app.bot
)
pause
