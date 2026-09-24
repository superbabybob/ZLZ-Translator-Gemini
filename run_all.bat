@echo off
cd /d "%~dp0"
rem Launch hotkey app (system tray). Discord bot will launch automatically if DISCORD_TOKEN is set in .env.
call run_hotkey.bat
