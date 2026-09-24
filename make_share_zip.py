"""สร้างไฟล์ zip สำหรับแจกให้คนอื่น (ไม่รวมคีย์, .venv, data, cache และล้างพาธเฉพาะเครื่อง)

    .venv\\Scripts\\python.exe make_share_zip.py
ผลลัพธ์: dist\\Discord-Translator-share.zip
"""
from __future__ import annotations

import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "dist" / "Discord-Translator-share.zip"
INCLUDE = [
    "core", "hotkey", "discord_app", "tests",
    ".env.example", ".gitignore", "config.toml", "glossary.md",
    "README.md", "SETUP_GUIDE.md", "FRIEND_GUIDE.md", "requirements.txt",
    "run_all.bat", "run_discord.bat", "run_hotkey.bat", "setup.bat", "make_share_zip.py",
]
EXCLUDE_DIRS = {"__pycache__", ".venv", "data", "dist"}


def iter_files():
    for name in INCLUDE:
        p = ROOT / name
        if p.is_file():
            yield p
        elif p.is_dir():
            for f in p.rglob("*"):
                if f.is_file() and not (EXCLUDE_DIRS & set(f.relative_to(ROOT).parts)) and f.suffix != ".pyc":
                    yield f


def main() -> None:
    OUT.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        for f in iter_files():
            arc = "Discord-Translator/" + f.relative_to(ROOT).as_posix()
            if f.name == "config.toml":
                text = f.read_text(encoding="utf-8")
                text = re.sub(r'(?m)^command = ".*"$', 'command = ""', text)  # ล้างพาธเฉพาะเครื่อง
                z.writestr(arc, text)
            else:
                z.write(f, arc)
    names = zipfile.ZipFile(OUT).namelist()
    assert not any(n.endswith("/.env") for n in names), ".env หลุดเข้า zip!"
    assert not any("/.venv/" in n or "/data/" in n for n in names), ".venv หรือ data หลุดเข้า zip!"
    print(f"สร้างแล้ว: {OUT}  ({OUT.stat().st_size // 1024} KB, {len(names)} ไฟล์)")


if __name__ == "__main__":
    main()
