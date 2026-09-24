"""โหลด config.toml, glossary.md และ .env จากโฟลเดอร์โปรเจกต์"""
from __future__ import annotations

import os
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

if getattr(sys, "frozen", False):
    PROJECT_ROOT = Path(sys.executable).resolve().parent
else:
    PROJECT_ROOT = Path(__file__).resolve().parent.parent

GEMINI_MODELS = {
    # โมเดลตระกูล Flash-Lite (โควต้าใหญ่สุด 500 ครั้ง/วัน, 15 RPM)
    "flash-lite": "gemini-3.5-flash-lite",
    "gemini-3.5-flash-lite": "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite": "gemini-3.1-flash-lite",
    # โมเดลตระกูล Flash (ความแม่นยำสูง 20 ครั้ง/วัน, 5 RPM)
    "flash": "gemini-3.5-flash-lite",
    "gemini-3.8-flash": "gemini-3.8-flash",
    "gemini-3.7-flash": "gemini-3.7-flash",
    "gemini-3.6-flash": "gemini-3.6-flash",
    "gemini-3.5-flash": "gemini-3.5-flash",
    "gemini-3-flash": "gemini-3-flash",
    "gemini-2.5-flash-lite": "gemini-2.5-flash-lite",
    "gemini-2.5-flash": "gemini-2.5-flash",
}

# ลำดับการสลับโมเดลสำรองเมื่อโควต้าเต็ม (HTTP 429 Quota Exceeded)
# โมเดลหลักคือ Gemini 3.5 Flash Lite และสำรองอันดับ 1 คือ Gemini 3.1 Flash Lite (โควต้ารวม 1,000 ครั้ง/วัน)
DEFAULT_GEMINI_FALLBACKS = [
    "gemini-3.1-flash-lite",  # อันดับ 2: เร็ว โควต้าใหญ่ (15 RPM / 500 RPD)
    "gemini-3.8-flash",       # อันดับ 3: Flash ใหม่สุด (5 RPM / 20 RPD)
    "gemini-3.7-flash",       # อันดับ 4: (5 RPM / 20 RPD)
    "gemini-3.6-flash",       # อันดับ 5: (5 RPM / 20 RPD)
    "gemini-3.5-flash",       # อันดับ 6: (5 RPM / 20 RPD)
    "gemini-3-flash",         # อันดับ 7: (5 RPM / 20 RPD)
    "gemini-2.5-flash-lite",  # อันดับ 8: (10 RPM / 20 RPD)
    "gemini-2.5-flash",       # อันดับ 9: (5 RPM / 20 RPD)
]


TONES = ("formal", "friendly", "brief")
MODES = ("read", "reply", "explain", "polish")


@dataclass
class Config:
    raw: dict[str, Any]
    root: Path
    glossary: str = ""
    env: dict[str, str] = field(default_factory=dict)

    # ---- general -------------------------------------------------------
    @property
    def default_tone(self) -> str:
        tone = self.raw.get("general", {}).get("default_tone", "friendly")
        return tone if tone in TONES else "friendly"

    @property
    def provider_order(self) -> list[str]:
        order = self.raw.get("general", {}).get("provider_order") or ["gemini"]
        return [str(p) for p in order]

    @property
    def timeout(self) -> float:
        return float(self.raw.get("general", {}).get("timeout_seconds", 60))

    @property
    def auto_back_translate(self) -> bool:
        return bool(self.raw.get("general", {}).get("auto_back_translate", False))

    @property
    def compact_glossary(self) -> str:
        """คลังศัพท์แบบสรุปย่อกระชับ ลด token สำหรับ local model โดยไม่แตะต้องไฟล์ glossary.md ต้นฉบับ"""
        from core.glossary import get_compact_glossary
        return get_compact_glossary(self.root, self.glossary)

    def model_for(self, mode: str) -> str:
        """ชื่อรุ่นโมเดลสำหรับโหมดนั้น"""
        model = str(self.raw.get("modes", {}).get(mode, "gemini-3.5-flash-lite"))
        return GEMINI_MODELS.get(model, model)


    @property
    def gemini_fallback_models(self) -> list[str]:
        """รายชื่อโมเดลสำรองสำหรับ Gemini เมื่อโควต้าเต็ม"""
        cfg = self.provider_cfg("gemini")
        fallbacks = cfg.get("fallback_models")
        if fallbacks and isinstance(fallbacks, list):
            return [GEMINI_MODELS.get(str(m), str(m)) for m in fallbacks]
        return list(DEFAULT_GEMINI_FALLBACKS)

    def provider_cfg(self, name: str) -> dict[str, Any]:
        return dict(self.raw.get("providers", {}).get(name, {}))

    def hotkey(self, mode: str) -> str | None:
        value = self.raw.get("hotkeys", {}).get(mode)
        return str(value) if value else None

    @property
    def discord_autostart(self) -> bool:
        return bool(self.raw.get("discord", {}).get("autostart", True))

    @property
    def only_in_apps(self) -> list[str]:
        return [str(a) for a in self.raw.get("hotkeys", {}).get("only_in_apps", []) if a]

    def ui(self, key: str, default: Any) -> Any:
        return self.raw.get("ui", {}).get(key, default)

    def secret(self, key: str) -> str | None:
        """ค่าจาก .env ก่อน ถ้าไม่มีค่อยดูตัวแปรสภาพแวดล้อมของระบบ"""
        return self.env.get(key) or os.environ.get(key)

    @property
    def active_provider(self) -> str:
        """ผู้ให้บริการตัวแรกในลำดับ (ตัวหลัก) เช่น 'gemini' หรือ 'ollama'"""
        order = self.provider_order
        return order[0] if order else "gemini"

    @property
    def ollama_url(self) -> str:
        """URL ของ Ollama server ในเครื่อง"""
        return str(self.provider_cfg("ollama").get("url") or "http://localhost:11434")

    @property
    def ollama_model(self) -> str:
        """ชื่อโมเดลหลักใน Ollama"""
        return str(self.provider_cfg("ollama").get("model") or "qwen2.5:7b")

    @property
    def ollama_fallback_models(self) -> list[str]:
        """รายชื่อโมเดลสำรองของ Ollama ตามลำดับความสำคัญ"""
        raw = self.provider_cfg("ollama").get("fallback_models") or []
        if isinstance(raw, list):
            return [str(m) for m in raw if m]
        return []

    @property
    def data_dir(self) -> Path:
        d = self.root / "data"
        d.mkdir(exist_ok=True)
        return d



def _load_env(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    if not path.exists():
        return env
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def set_env_value(root: Path, key: str, value: str) -> None:
    """เขียนค่าลง .env: แทนที่บรรทัดเดิม (รวมที่ถูก comment ไว้) หรือเพิ่มท้ายไฟล์ ค่าว่าง = ปิดบรรทัดนั้น"""
    path = root / ".env"
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    new_line = f"{key}={value.strip()}" if value.strip() else f"# {key}="
    replaced = False
    for i, line in enumerate(lines):
        stripped = line.strip().lstrip("#").strip()
        if stripped.startswith(f"{key}="):
            lines[i] = new_line
            replaced = True
            break
    if not replaced:
        lines.append(new_line)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def set_config_value(root: Path, section: str, key: str, value: Any) -> None:
    """แก้ค่าหนึ่งบรรทัดใน config.toml โดยคง comment และลำดับเดิมไว้ (รองรับ string, bool, int, float, list)"""
    import re

    path = root / "config.toml"
    text = path.read_text(encoding="utf-8")
    if isinstance(value, bool):
        rendered = "true" if value else "false"
    elif isinstance(value, (int, float)):
        rendered = str(value)
    elif isinstance(value, list):
        rendered = "[" + ", ".join('"' + str(v).replace('"', '\\"') + '"' for v in value) + "]"
    else:
        rendered = '"' + str(value).replace('"', '\\"') + '"'
    lines = text.splitlines()
    in_section = False
    done = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            in_section = stripped == f"[{section}]"
            continue
        if in_section and re.match(rf"^\s*{re.escape(key)}\s*=", line):
            m = re.search(r"\s+#.*$", line)  # เก็บ comment ท้ายบรรทัดไว้
            comment = m.group(0) if m else ""
            lines[i] = f"{key} = {rendered}{comment}"
            done = True
            break
    if not done:
        # ไม่มีบรรทัดนี้: เพิ่มท้าย section (หรือสร้าง section ใหม่ท้ายไฟล์)
        for i, line in enumerate(lines):
            if line.strip() == f"[{section}]":
                lines.insert(i + 1, f"{key} = {rendered}")
                done = True
                break
        if not done:
            lines += ["", f"[{section}]", f"{key} = {rendered}"]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def set_active_provider(root: Path, provider: str) -> None:
    """สลับผู้ให้บริการหลักใน config.toml (เช่น 'gemini' หรือ 'ollama')"""
    set_config_value(root, "general", "provider_order", [provider])



def load_config(root: Path | None = None) -> Config:
    root = Path(root or os.environ.get("TRANSLATOR_ROOT") or PROJECT_ROOT)
    cfg_path = root / "config.toml"
    if not cfg_path.exists():
        bundled = root / "_internal" / "config.toml"
        if bundled.exists():
            import shutil
            shutil.copyfile(bundled, cfg_path)
            for extra in ("glossary.md", ".env.example"):
                src = root / "_internal" / extra
                dst = root / extra
                if src.exists() and not dst.exists():
                    shutil.copyfile(src, dst)
        else:
            raise FileNotFoundError(f"ไม่พบไฟล์ตั้งค่า: {cfg_path}")
    with cfg_path.open("rb") as f:
        raw = tomllib.load(f)
    glossary_path = root / "glossary.md"
    glossary = glossary_path.read_text(encoding="utf-8") if glossary_path.exists() else ""
    return Config(raw=raw, root=root, glossary=glossary, env=_load_env(root / ".env"))
