"""Builds standalone executable with PyInstaller and packages it into an installer with Inno Setup."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DIST_DIR = ROOT / "dist"
APP_DIR = DIST_DIR / "ZLZ-translator"
ISS_FILE = ROOT / "installer.iss"


def find_iscc() -> Path | None:
    # 1. Check PATH
    cmd = shutil.which("iscc")
    if cmd:
        return Path(cmd)

    # 2. Check standard Windows installation paths
    candidates = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Inno Setup 6" / "ISCC.exe",
        Path(os.environ.get("ProgramFiles(x86)", "")) / "Inno Setup 6" / "ISCC.exe",
        Path(os.environ.get("ProgramFiles", "")) / "Inno Setup 6" / "ISCC.exe",
        Path("C:/Program Files (x86)/Inno Setup 6/ISCC.exe"),
        Path("C:/Program Files/Inno Setup 6/ISCC.exe"),
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def main() -> None:
    print("=" * 60)
    print("  Building ZLZ-translator (Gemini-version) Setup.exe")
    print("=" * 60)

    # Step 1: Run PyInstaller
    print("\n[1/3] Compiling Python code with PyInstaller...")
    pyinstaller = sys.executable.replace("python.exe", "pyinstaller.exe")
    if not Path(pyinstaller).exists():
        pyinstaller = shutil.which("pyinstaller") or "pyinstaller"

    cmd = [
        str(pyinstaller),
        "--noconfirm",
        "--clean",
        "--onedir",
        "--windowed",
        "--name", "ZLZ-translator",
        "--paths", str(ROOT),
        "--icon", str(ROOT / "assets" / "icon.ico"),
        "--add-data", f"{ROOT / 'config.toml'};.",
        "--add-data", f"{ROOT / 'glossary.md'};.",
        "--add-data", f"{ROOT / '.env.example'};.",
        "--add-data", f"{ROOT / 'assets'};assets",
        "--hidden-import", "hotkey",
        "--hidden-import", "hotkey.autostart",
        "--hidden-import", "hotkey.clipboard",
        "--hidden-import", "hotkey.popup",
        "--hidden-import", "hotkey.settings_dialog",
        "--hidden-import", "hotkey.tray",
        "--hidden-import", "pystray._win32",
        "--hidden-import", "PIL",
        "--hidden-import", "keyboard",
        "--hidden-import", "pyperclip",
        "--hidden-import", "tomllib",
        "--hidden-import", "discord",
        "--hidden-import", "core.glossary",
        "--hidden-import", "core.providers.ollama",
        str(ROOT / "run.py"),
    ]

    res = subprocess.run(cmd, cwd=str(ROOT))
    if res.returncode != 0:
        print("[!] PyInstaller build failed!")
        sys.exit(res.returncode)

    # Step 2: Copy template files into app folder
    print("\n[2/3] Preparing application directory...")
    for filename in ("config.toml", "glossary.md", ".env.example"):
        src = ROOT / filename
        dst = APP_DIR / filename
        if src.exists():
            shutil.copyfile(src, dst)
            print(f"  Copied {filename} to {APP_DIR.name}/")

    assets_src = ROOT / "assets"
    assets_dst = APP_DIR / "assets"
    if assets_src.exists():
        if assets_dst.exists():
            shutil.rmtree(assets_dst)
        shutil.copytree(assets_src, assets_dst)
        print(f"  Copied assets/ to {APP_DIR.name}/")

    # Step 3: Run Inno Setup Compiler (ISCC)
    print("\n[3/3] Packaging installer with Inno Setup...")
    iscc = find_iscc()
    if not iscc:
        print("[!] Inno Setup compiler (ISCC.exe) not found!")
        print("    Please install Inno Setup 6 (https://jrsoftware.org/isdl.php)")
        sys.exit(1)

    print(f"  Using Inno Setup: {iscc}")
    res = subprocess.run([str(iscc), str(ISS_FILE)], cwd=str(ROOT))
    if res.returncode != 0:
        print("[!] Inno Setup compilation failed!")
        sys.exit(res.returncode)

    out_exe = DIST_DIR / "ZLZ-Translator-Setup.exe"
    if out_exe.exists():
        size_mb = out_exe.stat().st_size / (1024 * 1024)
        print("\n" + "=" * 60)
        print(f"  SUCCESS! Installer generated:")
        print(f"  {out_exe} ({size_mb:.1f} MB)")
        print("=" * 60)
    else:
        print("[!] Installer file was not generated.")


if __name__ == "__main__":
    main()
