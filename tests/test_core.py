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
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


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
check("model_for read คือ gemini-3.5-flash-lite", cfg.model_for("read") == "gemini-3.5-flash-lite")

# 3. Gemini Provider - จำลองการเรียก API ปกติ
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
    check("gemini model ถูกต้อง", r.model == "gemini-3.5-flash-lite")
    check("gemini ไม่ได้ใช้ fallback ในสภาวะปกติ", not r.fallback_used)

# 4. ทดสอบระบบสลับโมเดลอัตโนมัติเมื่อ Quota เต็ม (HTTP 429)
t._providers.clear()
called_models: list[str] = []

def fake_urlopen_with_quota(req, timeout=None):
    url = req.full_url
    for model_name in ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-3.8-flash"]:
        if model_name in url:
            called_models.append(model_name)
            break
    # จำลองว่า gemini-3.5-flash-lite โควต้าเต็ม (HTTP 429)
    if "gemini-3.5-flash-lite:" in url:
        fp = io.BytesIO(b'{"error": {"code": 429, "message": "RESOURCE_EXHAUSTED: quota exceeded"}}')
        raise urllib.error.HTTPError(url, 429, "Too Many Requests", {}, fp)
    # โมเดลสำรองตัวแรก (gemini-3.1-flash-lite) ตอบได้ปกติ
    return io.BytesIO(json.dumps(fake_gemini_resp).encode("utf-8"))

with unittest.mock.patch("urllib.request.urlopen", side_effect=fake_urlopen_with_quota):
    r_fallback = t.run("reply", "ทดสอบการสลับโมเดลเมื่อโควต้าเต็ม", tone="friendly", provider="gemini")
    check("เมื่อโมเดลหลักติด 429 สามารถสลับไปโมเดลสำรองได้สำเร็จ", "Hello" in r_fallback.text)
    check("โมเดลที่ใช้งานจริงคือโมเดลสำรอง gemini-3.1-flash-lite", r_fallback.model == "gemini-3.1-flash-lite")
    check("ระบบระบุว่ามีการใช้ตัวสำรอง (fallback_used)", r_fallback.fallback_used is True)
    check("มีการเรียกโมเดลหลักก่อนแล้วสลับไปโมเดลสำรอง", called_models == ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite"])

# 5. ทดสอบ Cooldown: เรียกซ้ำขณะที่โมเดลหลักยังติด Cooldown ต้องข้ามไปโมเดลสำรองทันที
called_models.clear()
with unittest.mock.patch("urllib.request.urlopen", side_effect=fake_urlopen_with_quota):
    r_cooldown = t.run("reply", "ทดสอบ cooldown ข้ามโมเดลที่ติด quota ทันที", tone="friendly", provider="gemini")
    check("ข้ามโมเดลหลักที่ติด quota ไปยังโมเดลสำรองโดยตรง", called_models == ["gemini-3.1-flash-lite"])
    check("ผลลัพธ์ยังคงสำเร็จด้วยตัวสำรอง", r_cooldown.model == "gemini-3.1-flash-lite" and r_cooldown.fallback_used is True)

# 6. ทดสอบกรณี HTTP 503 High Demand / Timeout -> ต้องสลับโมเดลได้เช่นกัน
t._providers.clear()
called_models_503: list[str] = []

def fake_urlopen_with_503(req, timeout=None):
    url = req.full_url
    for model_name in ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite"]:
        if model_name in url:
            called_models_503.append(model_name)
            break
    if "gemini-3.5-flash-lite:" in url:
        fp = io.BytesIO(b'{"error": {"code": 503, "message": "This model is currently experiencing high demand. Spikes in demand are usually temporary."}}')
        raise urllib.error.HTTPError(url, 503, "Service Unavailable", {}, fp)
    return io.BytesIO(json.dumps(fake_gemini_resp).encode("utf-8"))

with unittest.mock.patch("urllib.request.urlopen", side_effect=fake_urlopen_with_503):
    r_503 = t.run("reply", "ทดสอบกรณี 503 high demand", tone="friendly", provider="gemini")
    check("กรณี 503 high demand สลับไปโมเดลสำรองสำเร็จ", r_503.model == "gemini-3.1-flash-lite" and r_503.fallback_used is True)


# 7. กรณีไม่มี API Key -> ProviderError
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

# 8. ทดสอบ Ollama Provider (Local Model)
from core.providers.ollama import OllamaProvider, query_ollama_models  # noqa: E402

check("มี OllamaProvider ในระบบ", "ollama" in t.config.raw.get("providers", {}))

fake_tags_resp = {
    "models": [
        {"name": "qwen2.5:7b", "model": "qwen2.5:7b"},
        {"name": "llama3.2:latest", "model": "llama3.2:latest"},
    ]
}

fake_chat_resp = {
    "model": "qwen2.5:7b",
    "message": {
        "role": "assistant",
        "content": "สวัสดีครับ! ผมจะส่งไฟล์ให้ภายในวันศุกร์นี้",
    },
    "done": True,
}

ollama_called_models: list[str] = []
ollama_chat_payloads: list[dict] = []

def fake_ollama_urlopen(req, timeout=None):
    url = req.full_url
    if "/api/tags" in url:
        return io.BytesIO(json.dumps(fake_tags_resp).encode("utf-8"))
    if "/api/chat" in url:
        body = json.loads(req.data.decode("utf-8"))
        model = body.get("model")
        ollama_called_models.append(model)
        ollama_chat_payloads.append(body)
        # จำลองกรณีโมเดลหลักขัดข้อง แล้วสลับไปตัวสำรอง llama3.2:latest
        if model == "broken-model":
            fp = io.BytesIO(b'{"error": "model broken-model not found"}')
            raise urllib.error.HTTPError(url, 404, "Not Found", {}, fp)
        return io.BytesIO(json.dumps(fake_chat_resp).encode("utf-8"))
    return io.BytesIO(b"{}")

with unittest.mock.patch("urllib.request.urlopen", side_effect=fake_ollama_urlopen):
    # ทดสอบ query_ollama_models
    tags = query_ollama_models()
    check("query_ollama_models ดึงรายชื่อโมเดลได้", "qwen2.5:7b" in tags and "llama3.2:latest" in tags)

    # ทดสอบ complete ปกติ
    t._providers.clear()
    ollama_chat_payloads.clear()
    r_ollama = t.run("read", "Hello! Could you send me the files by Friday?", provider="ollama")
    check("ollama แปลสำเร็จ", "สวัสดี" in r_ollama.text)
    check("ollama คืน provider ชื่อ ollama", r_ollama.provider == "ollama")

    # ตรวจสอบว่า Ollama ได้รับ Compact Glossary แทนที่จะเป็นตัวเต็ม
    check("ollama ได้รับข้อความ chat", len(ollama_chat_payloads) > 0)
    system_sent_to_ollama = ollama_chat_payloads[0]["messages"][0]["content"]
    check("ollama ใช้ compact glossary (Keep English:)", "Keep English:" in system_sent_to_ollama)
    check("ollama ไม่ส่ง boilerplate comments", "this file is automatically attached" not in system_sent_to_ollama.lower())

    # ทดสอบ Local Fallback Chain
    ollama_called_models.clear()
    t.config.raw.setdefault("providers", {}).setdefault("ollama", {})["model"] = "broken-model"
    t.config.raw["providers"]["ollama"]["fallback_models"] = ["llama3.2:latest"]
    t._providers.clear()

    r_ollama_fallback = t.run("read", "Hello again", provider="ollama")
    check("ollama สลับไปโมเดลสำรองเมื่อตัวหลักพัง", r_ollama_fallback.model == "llama3.2:latest")
    check("ollama fallback_used เป็น True", r_ollama_fallback.fallback_used is True)
    check("ollama ลอง broken-model ก่อน แล้วตามด้วย llama3.2:latest", ollama_called_models == ["broken-model", "llama3.2:latest"])

# 9. ทดสอบระบบ Compact Glossary แยกต่างหาก และการตรวจสอบการเปลี่ยนแปลง
from core.glossary import compact_glossary_text, get_compact_glossary  # noqa: E402

sample_glossary = """
# Glossary and Project Context
This file is automatically attached to translation prompts. Feel free to customize.

## Terms to Keep Untranslated
Rig, Mesh, Texture, Shader, Normal Map, BlendShape

## Proper Nouns & Product Names
- ZLZ Anime Shader
- Project Lumina

## Tone & Guidelines
- Use professional tone for client inquiries
"""

compacted = compact_glossary_text(sample_glossary)
check("compact_glossary_text สรุปย่อคำศัพท์", "Keep English: Rig, Mesh, Texture, Shader, Normal Map, BlendShape" in compacted)
check("compact_glossary_text เก็บชื่อเฉพาะ", "ZLZ Anime Shader" in compacted)
check("compact_glossary_text ตัด boilerplate", "feel free to customize" not in compacted.lower())
check("compact_glossary_text สั้นกว่าเดิมมาก", len(compacted) < len(sample_glossary))

# ทดสอบ get_compact_glossary ไม่แตะต้องไฟล์ glossary.md ต้นฉบับ
orig_glossary_content = (ROOT / "glossary.md").read_text(encoding="utf-8") if (ROOT / "glossary.md").exists() else ""
cached_compact = get_compact_glossary(ROOT)
check("data/glossary_compact.txt ถูกสร้างขึ้น", (ROOT / "data" / "glossary_compact.txt").exists())
check("data/glossary.sha256 ถูกสร้างขึ้น", (ROOT / "data" / "glossary.sha256").exists())
check("glossary.md ต้นฉบับไม่ถูกแก้ไข", (ROOT / "glossary.md").read_text(encoding="utf-8") == orig_glossary_content)

print("\nทุกอย่างผ่านเรียบร้อย ทั้ง Gemini Cloud, Local Model (Ollama) และ Compact Glossary")

