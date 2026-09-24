@echo off
cd /d "%~dp0"
rem ปกติไม่ต้องใช้ไฟล์นี้: run_hotkey.bat จะเปิด Discord app ให้เองเมื่อมี DISCORD_TOKEN ใน .env
rem ไฟล์นี้มีไว้กรณีอยากรัน Discord app เดี่ยวๆ พร้อมเห็น log ในหน้าต่าง (ปิดหน้าต่าง = หยุดทำงาน)
if not exist ".venv\Scripts\python.exe" (
  echo ยังไม่ได้ติดตั้ง  กรุณาดับเบิลคลิก setup.bat ก่อน
  pause & exit /b 1
)
chcp 65001 >nul
".venv\Scripts\python.exe" -m discord_app.bot
pause
