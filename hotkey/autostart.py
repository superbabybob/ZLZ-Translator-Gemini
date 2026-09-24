"""เปิดโปรแกรมอัตโนมัติเมื่อเข้า Windows ด้วย shortcut ในโฟลเดอร์ Startup ของผู้ใช้

ไม่ต้องใช้สิทธิ์ admin และตรวจสอบแล้วว่าไม่โดน redirect แม้ถูกเรียกจากโปรแกรมที่ติดตั้งแบบ Store package
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

SHORTCUT_NAME = "Discord Translator.lnk"
_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


def startup_dir() -> Path:
    return Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


def shortcut_path() -> Path:
    return startup_dir() / SHORTCUT_NAME


def is_enabled() -> bool:
    return shortcut_path().exists()


def _pythonw(root: Path) -> Path:
    p = root / ".venv" / "Scripts" / "pythonw.exe"
    return p if p.exists() else Path(sys.executable)


def enable(root: Path) -> tuple[bool, str]:
    target = _pythonw(root)
    app = root / "hotkey" / "app.py"
    lnk = shortcut_path()
    script = (
        "$s = (New-Object -ComObject WScript.Shell).CreateShortcut('{lnk}'); "
        "$s.TargetPath = '{target}'; "
        "$s.Arguments = '\"{app}\"'; "
        "$s.WorkingDirectory = '{root}'; "
        "$s.Description = 'Discord Translator'; "
        "$s.Save()"
    ).format(lnk=str(lnk).replace("'", "''"), target=str(target).replace("'", "''"),
             app=str(app).replace("'", "''"), root=str(root).replace("'", "''"))
    try:
        proc = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                              capture_output=True, text=True, encoding="utf-8", errors="replace",
                              timeout=30, creationflags=_NO_WINDOW)
    except (OSError, subprocess.TimeoutExpired) as e:
        return False, str(e)
    if proc.returncode != 0 or not lnk.exists():
        return False, (proc.stderr or proc.stdout).strip()[:300] or "สร้าง shortcut ไม่สำเร็จ"
    return True, "จะเปิดเองทุกครั้งที่เข้า Windows"


def disable() -> tuple[bool, str]:
    lnk = shortcut_path()
    try:
        if lnk.exists():
            lnk.unlink()
    except OSError as e:
        return False, str(e)
    return True, "ยกเลิกเปิดอัตโนมัติแล้ว"
