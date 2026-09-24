@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
  echo ยังไม่ได้ติดตั้ง  กรุณาดับเบิลคลิก setup.bat ก่อน
  pause & exit /b 1
)
rem pythonw = ไม่เปิดหน้าต่างดำค้างไว้  โปรแกรมจะไปอยู่ที่ system tray
start "" ".venv\Scripts\pythonw.exe" -m hotkey.app
