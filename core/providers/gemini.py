"""ตัวเชื่อม Google Gemini API (มีโควต้าฟรี) ผ่าน REST พร้อมระบบสลับโมเดลสำรองอัตโนมัติเมื่อโควต้าเต็ม (HTTP 429)"""
from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request

from core.config import DEFAULT_GEMINI_FALLBACKS, GEMINI_MODELS, Config
from core.providers.base import Provider, ProviderError

_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
log = logging.getLogger("gemini")


class GeminiProvider(Provider):
    name = "gemini"

    def __init__(self, config: Config):
        super().__init__(config)
        raw_model = str(self.cfg.get("model", "gemini-2.5-flash"))
        self.model = GEMINI_MODELS.get(raw_model, raw_model)
        self.api_key = config.secret("GEMINI_API_KEY")

        # รายชื่อโมเดลสำรองเมื่อโควต้าเต็ม
        raw_fallbacks = self.cfg.get("fallback_models", DEFAULT_GEMINI_FALLBACKS)
        self.fallback_models = [GEMINI_MODELS.get(str(m), str(m)) for m in raw_fallbacks]

        # เวลาพักโมเดลที่โควต้าเต็ม (วินาที)
        self.cooldown_seconds = float(self.cfg.get("cooldown_seconds", 60.0))
        self._exhausted_until: dict[str, float] = {}

        # บันทึกสถานะการเรียกใช้งานรอบล่าสุด
        self.last_model_used: str = self.model
        self.last_fallback_used: bool = False

    def available(self) -> bool:
        return bool(self.api_key)

    def _is_rate_limited(self, model: str) -> bool:
        """ตรวจสอบว่าโมเดลนี้ยังอยู่ในช่วง cooldown จากการติด quota หรือไม่"""
        return time.time() < self._exhausted_until.get(model, 0.0)

    def _mark_rate_limited(self, model: str, error_detail: str = "") -> None:
        """บันทึกว่าโมเดลนี้ติด quota: ถ้าเป็นโควต้าต่อวัน (RPD) ให้พัก 12 ชม. ถ้าเป็นต่อนาที (RPM) ให้พักตาม cooldown_seconds"""
        is_daily = any(term in error_detail.lower() for term in ["per day", "daily", "perday", "rpd"])
        duration = 43200.0 if is_daily else self.cooldown_seconds
        self._exhausted_until[model] = time.time() + duration
        log.warning(
            "Gemini model '%s' โควต้าเต็ม (HTTP 429 %s) พักการเรียก %.0f วินาที",
            model,
            "Daily Quota RPD" if is_daily else "Rate Limit RPM",
            duration,
        )

    def _candidate_models(self, primary_model: str) -> list[str]:
        """สร้างลำดับโมเดล: เริ่มจากตัวหลัก แล้วตามด้วยโมเดลสำรองที่ไม่ซ้ำ"""
        chain = [primary_model]
        for m in self.fallback_models:
            if m not in chain:
                chain.append(m)
        return chain

    def _call_model(self, model: str, system: str, user: str) -> str:
        """ส่งคำขอไปยัง Gemini REST API สำหรับโมเดลที่ระบุ"""
        body = {
            "system_instruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {"temperature": 0.3},
        }
        req = urllib.request.Request(
            _ENDPOINT.format(model=model),
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json", "x-goog-api-key": self.api_key},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.config.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:400]
            raise ProviderError(f"HTTP_{e.code}: Gemini ({model}) ตอบ {e.code}: {detail}") from e
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise ProviderError(f"ติดต่อ Gemini ({model}) ไม่ได้: {e}") from e

        try:
            parts = data["candidates"][0]["content"]["parts"]
            text = "".join(p.get("text", "") for p in parts).strip()
        except (KeyError, IndexError, TypeError) as e:
            reason = data.get("promptFeedback", {}).get("blockReason") if isinstance(data, dict) else None
            raise ProviderError(f"Gemini ({model}) ไม่ส่งข้อความกลับมา ({reason or 'unknown'})") from e
        if not text:
            raise ProviderError(f"Gemini ({model}) ส่งข้อความว่างกลับมา")
        return text

    def complete(self, system: str, user: str, model_alias: str) -> str:
        if not self.api_key:
            raise ProviderError("ยังไม่ได้ใส่ GEMINI_API_KEY ในไฟล์ .env")

        requested = model_alias or self.model
        primary = GEMINI_MODELS.get(requested, requested)
        all_candidates = self._candidate_models(primary)

        # ลำดับการลอง: นำโมเดลที่ไม่อยู่ในช่วง cooldown ขึ้นก่อน
        ready = [m for m in all_candidates if not self._is_rate_limited(m)]
        cooling = [m for m in all_candidates if self._is_rate_limited(m)]
        try_order = ready if ready else cooling

        errors: list[str] = []
        for idx, model in enumerate(try_order):
            try:
                text = self._call_model(model, system, user)
                self.last_model_used = model
                self.last_fallback_used = (model != primary)
                if self.last_fallback_used:
                    log.info("Gemini สลับมาใช้โมเดลสำรอง '%s' สำเร็จ (จากเดิม '%s')", model, primary)
                return text
            except ProviderError as e:
                err_msg = str(e)
                # เช็กว่าเป็นปัญหาคีย์หรือสิทธิ์การเข้าถึงหรือไม่ (400, 401, 403)
                is_auth_error = any(
                    k in err_msg.upper()
                    for k in ["HTTP_400", "HTTP_401", "HTTP_403", "API_KEY_INVALID", "INVALID_ARGUMENT", "PERMISSION_DENIED"]
                )
                if is_auth_error:
                    # ถ้า API Key ผิดหรือไม่มีสิทธิ์ ไม่ต้องวนลองโมเดลอื่น ให้แจ้งผู้ใช้ทันที
                    self.last_fallback_used = False
                    raise

                # เงื่อนไขต่าง ๆ ที่สามารถสลับไปลองโมเดลอื่นได้
                is_quota = "HTTP_429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg.upper() or "QUOTA" in err_msg.upper()
                is_unavailable = any(k in err_msg.upper() for k in ["HTTP_503", "HTTP_502", "HTTP_504", "HTTP_500", "UNAVAILABLE", "HIGH DEMAND"])
                is_timeout = "TIMED OUT" in err_msg.upper() or "TIMEOUT" in err_msg.upper()
                is_not_found = "HTTP_404" in err_msg or "NOT_FOUND" in err_msg.upper()

                if is_quota:
                    self._mark_rate_limited(model, err_msg)
                    errors.append(f"{model}: โควต้าเต็ม (HTTP 429)")
                    if idx + 1 < len(try_order):
                        log.warning("โมเดล '%s' โควต้าเต็ม -> กำลังสลับไปใช้ '%s'...", model, try_order[idx + 1])
                    continue
                elif is_unavailable:
                    # โมเดลมีคนใช้งานหนาแน่นชั่วคราว (503 High Demand) พักไว้ 60 วินาที แล้วลองตัวถัดไป
                    self._exhausted_until[model] = time.time() + 60.0
                    errors.append(f"{model}: เซิร์ฟเวอร์โหลดสูงชั่วคราว (HTTP 503 High Demand)")
                    if idx + 1 < len(try_order):
                        log.warning("โมเดล '%s' 503 High Demand -> กำลังสลับไปใช้ '%s'...", model, try_order[idx + 1])
                    continue
                elif is_timeout:
                    # โมเดลตอบสนองช้าจนหมดเวลา พักไว้ 60 วินาที แล้วลองตัวถัดไป
                    self._exhausted_until[model] = time.time() + 60.0
                    errors.append(f"{model}: หมดเวลารอ (Timeout)")
                    if idx + 1 < len(try_order):
                        log.warning("โมเดล '%s' ตอบสนองช้าเกินเวลา -> กำลังสลับไปใช้ '%s'...", model, try_order[idx + 1])
                    continue
                elif is_not_found:
                    errors.append(f"{model}: ไม่พบโมเดล (HTTP 404)")
                    if idx + 1 < len(try_order):
                        log.warning("โมเดล '%s' ไม่พบในระบบ -> กำลังสลับไปใช้ '%s'...", model, try_order[idx + 1])
                    continue
                else:
                    # ข้อผิดพลาดอื่น ๆ จากโมเดล ให้ลองสลับไปตัวถัดไปเช่นกัน
                    errors.append(f"{model}: {err_msg}")
                    if idx + 1 < len(try_order):
                        log.warning("โมเดล '%s' ขัดข้อง (%s) -> กำลังสลับไปใช้ '%s'...", model, err_msg, try_order[idx + 1])
                    continue

        self.last_fallback_used = False
        raise ProviderError(
            f"โมเดลของ Gemini ทั้งหมดไม่พร้อมใช้งานชั่วคราว:\n- "
            + "\n- ".join(errors)
            + f"\n(กรุณาลองใหม่อีกครั้งในอีกสักครู่ หรือตรวจสอบสถานะใน Google AI Studio)"
        )

