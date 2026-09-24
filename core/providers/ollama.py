"""ตัวเชื่อมต่อ Ollama (Local AI Models) ผ่าน REST API ไม่ต้องใช้อินเทอร์เน็ต

รองรับการตรวจหาโมเดลในเครื่องอัตโนมัติ และระบบสลับโมเดลสำรอง (Local Fallback Chain)
"""
from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from typing import Any

from core.config import Config
from core.providers.base import Provider, ProviderError

log = logging.getLogger("ollama")

DEFAULT_OLLAMA_URL = "http://localhost:11434"


def query_ollama_models(url: str = DEFAULT_OLLAMA_URL, timeout: float = 1.5) -> list[str]:
    """ดึงรายชื่อโมเดลทั้งหมดที่ติดตั้งอยู่ในเครื่องผ่าน Ollama REST API

    คืนค่าเป็น list ของชื่อโมเดล เช่น ['qwen2.5:7b', 'llama3.2:latest']
    หากเชื่อมต่อไม่ได้หรือไม่พบโมเดล จะคืนค่าเป็น list ว่าง []
    """
    req_url = f"{url.rstrip('/')}/api/tags"
    req = urllib.request.Request(req_url, headers={"User-Agent": "ZLZ-Translator"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            models = data.get("models", [])
            names: list[str] = []
            for item in models:
                name = item.get("name") or item.get("model")
                if name and name not in names:
                    names.append(name)
            return names
    except Exception as e:
        log.debug("ตรวจหา Ollama models ไม่สำเร็จ (%s): %s", req_url, e)
        return []


def is_ollama_running(url: str = DEFAULT_OLLAMA_URL, timeout: float = 1.0) -> bool:
    """ตรวจสอบอย่างรวดเร็วว่า Ollama server ในเครื่องกำลังทำงานอยู่หรือไม่"""
    req_url = f"{url.rstrip('/')}/api/tags"
    req = urllib.request.Request(req_url, headers={"User-Agent": "ZLZ-Translator"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False


class OllamaProvider(Provider):
    name = "ollama"

    def __init__(self, config: Config):
        super().__init__(config)
        self.url = str(self.cfg.get("url") or DEFAULT_OLLAMA_URL).rstrip("/")
        self.model = str(self.cfg.get("model") or "qwen2.5:7b")
        
        # รายชื่อโมเดลสำรองกรณีโมเดลหลักขัดข้องหรือไม่มีในเครื่อง
        raw_fallbacks = self.cfg.get("fallback_models") or []
        if isinstance(raw_fallbacks, list):
            self.fallback_models = [str(m) for m in raw_fallbacks if m]
        else:
            self.fallback_models = []

        self.timeout = float(self.cfg.get("timeout_seconds") or 120.0)
        self.temperature = float(self.cfg.get("temperature") or 0.3)

        self.last_model_used: str = self.model
        self.last_fallback_used: bool = False
        self._cached_available: bool | None = None
        self._cached_at: float = 0.0

    def available(self) -> bool:
        """ตรวจสอบว่า Ollama เปิดอยู่และมีโมเดลอย่างน้อย 1 ตัว (แคชไว้ 5 วินาทีเพื่อความเร็ว)"""
        now = time.time()
        if self._cached_available is not None and (now - self._cached_at) < 5.0:
            return self._cached_available

        models = query_ollama_models(self.url, timeout=1.5)
        is_ok = len(models) > 0
        self._cached_available = is_ok
        self._cached_at = now
        return is_ok

    def installed_models(self) -> list[str]:
        """คืนค่ารายชื่อโมเดลในเครื่องปัจจุบัน"""
        return query_ollama_models(self.url, timeout=2.0)

    def _candidate_models(self, primary_model: str) -> list[str]:
        """เรียงลำดับโมเดล: โมเดลหลัก -> โมเดลสำรองที่กำหนดไว้ -> โมเดลอื่นที่มีในเครื่อง"""
        chain: list[str] = [primary_model]
        for m in self.fallback_models:
            if m not in chain:
                chain.append(m)

        # เสริม: หากโมเดลที่ตั้งไว้ไม่มี ให้ดึงโมเดลที่มีในเครื่องมาเป็นตัวสำรองท้ายสุด
        installed = self.installed_models()
        for m in installed:
            if m not in chain:
                chain.append(m)
        return chain

    def _call_model(self, model: str, system: str, user: str) -> str:
        """ยิงคำขอไปยัง Ollama REST /api/chat"""
        endpoint = f"{self.url}/api/chat"
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "options": {
                "temperature": self.temperature,
            },
        }

        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            endpoint,
            data=data_bytes,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:300]
            raise ProviderError(f"HTTP_{e.code}: Ollama ({model}) ตอบข้อผิดพลาด: {detail}") from e
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise ProviderError(f"ติดต่อ Ollama ({self.url}) ไม่ได้: {e}") from e

        content = data.get("message", {}).get("content", "").strip()
        if not content:
            raise ProviderError(f"Ollama ({model}) ส่งข้อความว่างกลับมา")
        return content

    def complete(self, system: str, user: str, model_alias: str) -> str:
        # หาก model_alias เป็นโมเดลของ Gemini หรือค่าว่าง ให้ใช้โมเดลหลักของ Ollama ที่ตั้งค่าไว้ (self.model)
        if not model_alias or "gemini" in model_alias.lower() or model_alias in ("flash", "flash-lite"):
            requested = self.model
        else:
            requested = model_alias

        candidates = self._candidate_models(requested)
        if not candidates:
            raise ProviderError(
                f"ไม่พบโมเดลใน Ollama ({self.url})\n"
                "กรุณาเปิด Ollama และดาวน์โหลดโมเดลก่อน เช่น: ollama run qwen2.5:7b"
            )


        errors: list[str] = []
        for idx, model in enumerate(candidates):
            try:
                text = self._call_model(model, system, user)
                self.last_model_used = model
                self.last_fallback_used = (idx > 0)
                if self.last_fallback_used:
                    log.info("Ollama สลับมาใช้โมเดลสำรอง '%s' สำเร็จ (จากเดิม '%s')", model, requested)
                return text
            except ProviderError as e:
                err_str = str(e)
                log.warning("Ollama model '%s' ล้มเหลว: %s", model, err_str)
                errors.append(f"{model}: {err_str}")
                # ถ้ายังเหลือโมเดลตัวถัดไป ให้ลองวนต่อ
                continue

        self.last_fallback_used = False
        raise ProviderError(
            f"Ollama ทั้งหมดล้มเหลว (ลอง {len(candidates)} โมเดล):\n- "
            + "\n- ".join(errors)
            + f"\n(โปรดตรวจสอบว่า Ollama กำลังรันอยู่ที่ {self.url})"
        )
