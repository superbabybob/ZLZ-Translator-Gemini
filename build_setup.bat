@echo off
cd /d "%~dp0"

echo ============================================================
echo   Building ZLZ-translator (Gemini-version) Setup.exe
echo ============================================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [!] Python virtual environment (.venv) not found.
    echo     Please run setup.bat first.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" "%~dp0build_setup.py"
if %errorlevel% neq 0 (
    echo.
    echo [!] Build failed with exit code: %errorlevel%
    pause
    exit /b %errorlevel%
)

if exist "%~dp0dist\ZLZ-Translator-Setup.exe" (
    explorer.exe /select,"%~dp0dist\ZLZ-Translator-Setup.exe" 2>nul
)
pause
