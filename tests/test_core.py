"""ทดสอบแกนแปลและ Gemini Provider
"""
from __future__ import annotations

import io
import json
import sys
import unittest.mock
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.config import load_config  # noqa: E402
from core.prompts import build_system_prompt, build_user_prompt  # noqa: E402
from core.providers import ProviderError  # noqa: E402
from core.providers.gemini import GeminiProvider  # noqa: E402
from core.translator import Translator  # noqa: E402


def check(name: str, condition: bool, detail: str = "") -> None:
    print(("PASS " if condition else "FAIL ") + name + (f"  ({detail})" if detail and not condition else ""))
    if not condition:
        sys.exit(1)


cfg = load_config(ROOT)
t = Translator(cfg)

# 1. Prompt ครบส่วนสำคัญ
sp = build_system_prompt("reply", cfg.glossary, "formal")
check("system prompt มี glossary", "ZLZ Anime Shader" in sp)
check("system prompt มีน้ำเสียง formal", "formal" in sp.lower())
check("user prompt ห่อข้อความ", "<<<" in build_user_prompt("read", "hi"))

# 2. Config ค่าเริ่มต้นสำหรับ Gemini
check("provider_order คือ gemini", cfg.provider_order == ["gemini"])
check("model_for read คือ gemini-3.6-flash", cfg.model_for("read") == "gemini-3.6-flash")

# 3. Gemini Provider - จำลองการเรียก API
old_key = t.config.env.get("GEMINI_API_KEY")
t.config.env["GEMINI_API_KEY"] = "test-mock-key"
t._providers.clear()

fake_gemini_resp = {
    "candidates": [
        {
            "content": {
                "parts": [{"text": "Hello! I will send the files tomorrow morning."}]
            }
        }
    ]
}

def fake_urlopen(req, timeout=None):
    resp_bytes = json.dumps(fake_gemini_resp).encode("utf-8")
    resp_obj = io.BytesIO(resp_bytes)
    return resp_obj

with unittest.mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
    r = t.run("reply", "เดี๋ยวส่งให้พรุ่งนี้เช้าครับ", tone="friendly", provider="gemini")
    check("gemini run สำเร็จ", "Hello" in r.text)
    check("gemini คืน provider ชื่อ gemini", r.provider == "gemini")
    check("gemini model ถูกต้อง", r.model == "gemini-3.6-flash")

# 4. กรณีไม่มี API Key -> ProviderError
old_key = t.config.env.get("GEMINI_API_KEY")
t.config.env["GEMINI_API_KEY"] = ""
t._providers.clear()
try:
    t.run("read", "Hello", provider="gemini")
    check("ไม่มีคีย์ -> ProviderError", False)
except ProviderError as e:
    check("ไม่มีคีย์ -> แสดง ProviderError ชัดเจน", "GEMINI_API_KEY" in str(e) or "ยังไม่พร้อมใช้" in str(e))
finally:
    if old_key:
        t.config.env["GEMINI_API_KEY"] = old_key
    t._providers.clear()

print("\nทุกอย่างผ่านเรียบร้อย")
