@echo off
cd /d "%~dp0"
echo === ZLZ-translator (Gemini-version): Update to Latest ===
echo.

if exist ".git" (
  where git >nul 2>nul || (
    echo Git not found on system. Please download the latest ZIP from GitHub and overwrite files.
    pause & exit /b 1
  )
  echo Pulling latest code from GitHub...
  git pull --ff-only || (
    echo Git pull failed. If you modified files locally, backup your changes and download ZIP.
    pause & exit /b 1
  )
) else (
  echo This folder was not cloned with Git. Please download latest ZIP from GitHub and extract here.
  echo (Your .env and glossary.md will not be overwritten)
  pause & exit /b 0
)

if not exist ".venv\Scripts\python.exe" (
  echo Environment not found. Running setup.bat...
  call setup.bat
  exit /b
)
echo Updating packages...
".venv\Scripts\python.exe" -m pip install --quiet -r requirements.txt

echo.
echo Update complete! If the program is currently running, right-click the tray icon, choose Exit, and restart run_hotkey.bat.
pause
