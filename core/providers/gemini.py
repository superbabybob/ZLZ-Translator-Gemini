"""ตัวเชื่อม Google Gemini API (มีโควต้าฟรี) ผ่าน REST ไม่ต้องติดตั้งไลบรารีเพิ่ม"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

from core.providers.base import Provider, ProviderError

_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


class GeminiProvider(Provider):
    name = "gemini"

    def __init__(self, config):
        super().__init__(config)
        self.model = str(self.cfg.get("model", "gemini-2.5-flash"))
        self.api_key = config.secret("GEMINI_API_KEY")

    def available(self) -> bool:
        return bool(self.api_key)

    def complete(self, system: str, user: str, model_alias: str) -> str:
        if not self.api_key:
            raise ProviderError("ยังไม่ได้ใส่ GEMINI_API_KEY ในไฟล์ .env")
        body = {
            "system_instruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {"temperature": 0.3},
        }
        req = urllib.request.Request(
            _ENDPOINT.format(model=self.model),
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json", "x-goog-api-key": self.api_key},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.config.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:300]
            raise ProviderError(f"Gemini ตอบ HTTP {e.code}: {detail}") from e
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise ProviderError(f"ติดต่อ Gemini ไม่ได้: {e}") from e

        try:
            parts = data["candidates"][0]["content"]["parts"]
            text = "".join(p.get("text", "") for p in parts).strip()
        except (KeyError, IndexError, TypeError) as e:
            reason = data.get("promptFeedback", {}).get("blockReason") if isinstance(data, dict) else None
            raise ProviderError(f"Gemini ไม่ส่งข้อความกลับมา ({reason or 'unknown'})") from e
        if not text:
            raise ProviderError("Gemini ส่งข้อความว่างกลับมา")
        return text
