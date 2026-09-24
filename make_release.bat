@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================================
echo   ZLZ-translator (Gemini-version): Create Release Package (.zip)
echo ============================================================
echo.

set "PY="
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"
if "%PY%"=="" where py >nul 2>nul && set "PY=py -3"
if "%PY%"=="" where python >nul 2>nul && set "PY=python"

if not "%PY%"=="" (
  %PY% --version >nul 2>nul || set "PY="
)

if not "%PY%"=="" (
  echo [1/2] Packaging with Python...
  %PY% "%~dp0make_share_zip.py"
  if %errorlevel% equ 0 goto :done
)

echo [1/2] Packaging with PowerShell...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0make_release.ps1"

:done
echo.
echo ============================================================
echo   Release Package Created Successfully!
echo ============================================================
echo.
if exist "%~dp0dist\ZLZ-Translator-Gemini-Release.zip" (
  echo Output: %~dp0dist\ZLZ-Translator-Gemini-Release.zip
  echo.
  explorer.exe /select,"%~dp0dist\ZLZ-Translator-Gemini-Release.zip" 2>nul
)
pause
