@echo off
cd /d "%~dp0"
rem เปิดโปรแกรม Hotkey (ไป tray) ซึ่งจะเปิด Discord app ให้เองถ้ามี DISCORD_TOKEN ใน .env
rem หน้าต่างนี้จะปิดตัวเองทันที โปรแกรมทำงานอยู่เบื้องหลัง ปิดได้ที่เมนูไอคอน tray
call run_hotkey.bat
