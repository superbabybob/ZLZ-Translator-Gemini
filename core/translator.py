"""แกนแปล: เลือกโหมด สร้าง prompt ยิงผู้ให้บริการตามลำดับสำรอง และนับการใช้งาน"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from datetime import date

from core.config import MODES, TONES, Config, load_config
from core.prompts import build_system_prompt, build_user_prompt
from core.providers import PROVIDERS, Provider, ProviderError

log = logging.getLogger("translator")


@dataclass
class Result:
    text: str
    mode: str
    tone: str
    provider: str
    model: str
    seconds: float
    fallback_used: bool


class UsageCounter:
    """นับจำนวนครั้งต่อวันต่อผู้ให้บริการ เก็บใน data/usage.json"""

    def __init__(self, config: Config):
        self.path = config.data_dir / "usage.json"

    def _load(self) -> dict:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def record(self, provider: str) -> None:
        data = self._load()
        today = date.today().isoformat()
        day = data.setdefault(today, {})
        day[provider] = day.get(provider, 0) + 1
        # เก็บแค่ 30 วันล่าสุด
        for key in sorted(data)[:-30]:
            data.pop(key, None)
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def today(self) -> dict[str, int]:
        return self._load().get(date.today().isoformat(), {})


class Translator:
    def __init__(self, config: Config | None = None):
        self.config = config or load_config()
        self.usage = UsageCounter(self.config)
        self._providers: dict[str, Provider] = {}

    def reload(self) -> None:
        self.config = load_config(self.config.root)
        self._providers.clear()

    def _provider(self, name: str) -> Provider:
        if name not in self._providers:
            cls = PROVIDERS.get(name)
            if cls is None:
                raise ProviderError(f"ไม่รู้จักผู้ให้บริการ '{name}' (มี: {', '.join(PROVIDERS)})")
            self._providers[name] = cls(self.config)
        return self._providers[name]

    def run(self, mode: str, text: str, tone: str | None = None, provider: str | None = None) -> Result:
        if mode not in MODES:
            raise ValueError(f"โหมดต้องเป็นหนึ่งใน {MODES}")
        text = (text or "").strip()
        if not text:
            raise ValueError("ไม่มีข้อความให้แปล")
        tone = tone if tone in TONES else self.config.default_tone

        user = build_user_prompt(mode, text)
        model_alias = self.config.model_for(mode)
        order = [provider] if provider else self.config.provider_order

        errors: list[str] = []
        for index, name in enumerate(order):
            try:
                prov = self._provider(name)
            except ProviderError as e:
                errors.append(str(e))
                continue
            if not prov.available():
                errors.append(f"{name}: ยังไม่พร้อมใช้ (ขาดคีย์หรือไบนารี)")
                continue

            # สรุป glossary ย่อกระชับเมื่อใช้ Local Model (ollama) หรือเปิด compact_glossary ใน config
            use_compact = (name == "ollama") or bool(self.config.raw.get("general", {}).get("compact_glossary", False))
            active_glossary = self.config.compact_glossary if use_compact else self.config.glossary
            system = build_system_prompt(mode, active_glossary, tone)

            started = time.perf_counter()
            try:
                out = prov.complete(system, user, model_alias)
            except ProviderError as e:
                log.warning("%s ล้มเหลว: %s", name, e)
                errors.append(f"{name}: {e}")
                continue
            elapsed = time.perf_counter() - started
            self.usage.record(name)
            model = getattr(prov, "last_model_used", None) or getattr(prov, "model", None) or model_alias
            fallback_used = (index > 0) or bool(getattr(prov, "last_fallback_used", False))
            return Result(out, mode, tone, name, str(model), elapsed, fallback_used=fallback_used)

        raise ProviderError("แปลไม่สำเร็จ ทุกผู้ให้บริการล้มเหลว:\n- " + "\n- ".join(errors))
