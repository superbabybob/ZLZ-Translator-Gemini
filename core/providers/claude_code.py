"""ตัวเชื่อม Claude Code CLI แบบไม่โต้ตอบ (ใช้โควต้าสมาชิก ไม่ใช้เครดิต API)

เรียก:  claude -p --tools "" --no-session-persistence --output-format json
               --model <m> --effort <e> --system-prompt <s>  <prompt>
ผลลัพธ์เป็น JSON หนึ่งก้อน มีฟิลด์ result / is_error
"""
from __future__ import annotations

import glob
import json
import logging
import os
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path

from core.providers.base import Provider, ProviderError

log = logging.getLogger("claude_code")

# ไบนารีที่ติดมากับแอป Claude Desktop บน Windows
# แอปเวอร์ชัน Store/MSIX เก็บไว้ใต้ AppData\Local\Packages\Claude_*\LocalCache\Roaming แทน AppData\Roaming
_DESKTOP_GLOBS = [
    os.path.join(os.environ.get("APPDATA", ""), "Claude", "claude-code", "*", "claude.exe"),
    os.path.join(os.environ.get("LOCALAPPDATA", ""), "Packages", "Claude_*", "LocalCache", "Roaming",
                 "Claude", "claude-code", "*", "claude.exe"),
    os.path.join(os.environ.get("USERPROFILE", ""), ".local", "bin", "claude.exe"),
]


# แฟล็กที่ทำให้ Claude Code เริ่มเร็วขึ้น: ไม่โหลด MCP server, ปลั๊กอิน/skill และส่วนเสริม Chrome
# (--mcp-config รับได้หลายค่า จึงต้องมีแฟล็กอื่นตามหลังเสมอ ห้ามวาง prompt ต่อท้ายทันที)
FAST_START_ARGS = [
    "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}',
    "--disable-slash-commands",
    "--no-chrome",
]


def find_claude_command(configured: str = "") -> list[str]:
    """คืนคำสั่งเป็น list (รองรับ 'python fake.py' สำหรับทดสอบ)"""
    env_cmd = os.environ.get("CLAUDE_CODE_COMMAND")  # สำหรับทดสอบ มาก่อน config
    if env_cmd:
        return shlex.split(env_cmd, posix=False)
    if configured:
        parts = shlex.split(configured, posix=False)
        parts[0] = parts[0].strip('"')
        # พาธที่ระบุไว้อาจเป็นของเครื่องอื่น (เช่น ส่งโปรเจกต์ให้เพื่อน) ถ้าไม่มีไฟล์ให้หาอัตโนมัติแทน
        if os.path.exists(parts[0]) or shutil.which(parts[0]):
            return parts
    on_path = shutil.which("claude")
    if on_path:
        return [on_path]
    candidates: list[str] = []
    for pattern in _DESKTOP_GLOBS:
        candidates.extend(glob.glob(pattern))
    candidates = sorted(set(candidates), key=_version_key)
    if candidates:
        return [candidates[-1]]
    return []


def _version_key(path: str) -> tuple[int, ...]:
    ver = Path(path).parent.name
    try:
        return tuple(int(x) for x in ver.split("."))
    except ValueError:
        return (0,)


class ClaudeCodeProvider(Provider):
    name = "claude_code"

    def __init__(self, config):
        super().__init__(config)
        self.command = find_claude_command(str(self.cfg.get("command", "")))
        self.effort = str(self.cfg.get("effort", "low") or "")
        self.extra_args = [str(a) for a in self.cfg.get("extra_args", [])]
        self.fast_start = bool(self.cfg.get("fast_start", True))

    def available(self) -> bool:
        return bool(self.command)

    def complete(self, system: str, user: str, model_alias: str) -> str:
        if not self.command:
            raise ProviderError("ไม่พบ Claude Code CLI (ตั้งค่า providers.claude_code.command หรือติดตั้ง claude)")

        args = [
            *self.command,
            "-p",
            *(FAST_START_ARGS if self.fast_start else []),
            "--tools", "",
            "--no-session-persistence",
            "--output-format", "json",
            "--model", model_alias,
            "--system-prompt", system,
        ]
        if self.effort:
            args += ["--effort", self.effort]
        args += self.extra_args
        args.append(user)

        creationflags = 0x08000000 if sys.platform == "win32" else 0  # CREATE_NO_WINDOW
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        started = time.perf_counter()
        try:
            proc = subprocess.run(
                args,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.config.timeout,
                creationflags=creationflags,
                env=env,
            )
        except subprocess.TimeoutExpired as e:
            raise ProviderError(f"Claude Code ไม่ตอบภายใน {self.config.timeout:.0f} วินาที") from e
        except OSError as e:
            raise ProviderError(f"รัน Claude Code ไม่ได้: {e}") from e

        result, data = _parse_output(proc.stdout, proc.stderr, proc.returncode)
        wall = time.perf_counter() - started
        api = float(data.get("duration_api_ms") or 0) / 1000
        log.info("model=%s wall=%.1fs api=%.1fs startup=%.1fs", model_alias, wall, api, wall - api)
        return result


def _parse_output(stdout: str, stderr: str, returncode: int) -> tuple[str, dict]:
    text = (stdout or "").strip()
    data = None
    if text:
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # บางเวอร์ชันพิมพ์บรรทัดอื่นนำหน้า ลองหาบรรทัดสุดท้ายที่เป็น JSON
            for line in reversed(text.splitlines()):
                line = line.strip()
                if line.startswith("{"):
                    try:
                        data = json.loads(line)
                        break
                    except json.JSONDecodeError:
                        continue
    if data is None:
        msg = (stderr or text or "ไม่มีผลลัพธ์").strip()
        raise ProviderError(f"Claude Code ตอบไม่เป็น JSON (exit {returncode}): {msg[:300]}")

    result = str(data.get("result", "")).strip()
    if data.get("is_error") or not result:
        if "login" in result.lower():
            raise ProviderError(
                "Claude Code ยังไม่ได้ล็อกอิน: เปิด PowerShell แล้วรันคำสั่ง claude จากนั้นพิมพ์ /login หนึ่งครั้ง"
            )
        raise ProviderError(f"Claude Code แจ้งข้อผิดพลาด: {result or stderr.strip()[:300]}")
    return result, data
