"""ตัวเชื่อม Ollama (โมเดลรันในเครื่อง ฟรี ออฟไลน์)"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

from core.providers.base import Provider, ProviderError


class OllamaProvider(Provider):
    name = "ollama"

    def __init__(self, config):
        super().__init__(config)
        self.host = str(self.cfg.get("host", "http://localhost:11434")).rstrip("/")
        self.model = str(self.cfg.get("model", "qwen2.5:7b"))

    def complete(self, system: str, user: str, model_alias: str) -> str:
        body = {
            "model": self.model,
            "stream": False,
            "options": {"temperature": 0.3},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        req = urllib.request.Request(
            f"{self.host}/api/chat",
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.config.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raise ProviderError(f"Ollama ตอบ HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:300]}") from e
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise ProviderError(f"ติดต่อ Ollama ไม่ได้ (เปิดโปรแกรม Ollama อยู่ไหม?): {e}") from e
        text = str(data.get("message", {}).get("content", "")).strip()
        if not text:
            raise ProviderError("Ollama ส่งข้อความว่างกลับมา")
        return text
