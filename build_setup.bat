@echo off
setlocal
cd /d "%~dp0"

echo ============================================================
echo   Building ZLZ-translator Setup.exe
echo ============================================================
echo.

if not exist ".venv\Scripts\python.exe" goto :no_venv

".venv\Scripts\python.exe" "%~dp0build_setup.py"
if %errorlevel% neq 0 goto :build_failed

echo.
if exist "%~dp0dist\ZLZ-Translator-Setup.exe" (
    explorer.exe /select,"%~dp0dist\ZLZ-Translator-Setup.exe"
)
pause
exit /b 0

:no_venv
echo [!] Python virtual environment (.venv) not found.
echo     Please run setup.bat first.
pause
exit /b 1

:build_failed
echo.
echo [!] Build failed with exit code: %errorlevel%
pause
exit /b %errorlevel%
