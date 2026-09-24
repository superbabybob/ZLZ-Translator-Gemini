"""สร้างไฟล์ zip สำหรับแจกจ่าย (Release Package) ไม่รวมคีย์, .venv, data, cache

    python make_share_zip.py
ผลลัพธ์: dist/ZLZ-Translator-Gemini-Release.zip
"""
from __future__ import annotations

import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "dist" / "ZLZ-Translator-Gemini-Release.zip"
INCLUDE = [
    "core", "hotkey", "discord_app", "tests",
    ".env.example", ".gitignore", "config.toml", "glossary.md",
    "README.md", "SETUP_GUIDE.md", "FRIEND_GUIDE.md", "requirements.txt",
    "run_all.bat", "run_discord.bat", "run_hotkey.bat", "setup.bat", "setup.ps1", "make_release.bat", "make_release.ps1", "make_share_zip.py",
]
EXCLUDE_DIRS = {"__pycache__", ".venv", "data", "dist", ".git"}


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
            arc = "ZLZ-Translator-Gemini/" + f.relative_to(ROOT).as_posix()
            z.write(f, arc)
    names = zipfile.ZipFile(OUT).namelist()
    assert not any(n.endswith("/.env") for n in names), ".env หลุดเข้า zip!"
    assert not any("/.venv/" in n or "/data/" in n for n in names), ".venv หรือ data หลุดเข้า zip!"
    print(f"สร้างสำเร็จ: {OUT} ({OUT.stat().st_size // 1024} KB, {len(names)} ไฟล์)")


if __name__ == "__main__":
    main()
