"""อินเทอร์เฟซกลางของผู้ให้บริการแปล"""
from __future__ import annotations

from core.config import Config


class ProviderError(Exception):
    """ผู้ให้บริการตอบไม่ได้ (ไม่ได้ล็อกอิน, โควต้าหมด, เน็ตล่ม ฯลฯ) -> ให้ลองตัวถัดไป"""


class Provider:
    name = "base"

    def __init__(self, config: Config):
        self.config = config
        self.cfg = config.provider_cfg(self.name)

    def available(self) -> bool:
        """เช็กเบื้องต้นว่ามีสิ่งที่ต้องใช้ครบไหม (คีย์, ไบนารี) ยังไม่ยิงจริง"""
        return True

    def complete(self, system: str, user: str, model_alias: str) -> str:
        raise NotImplementedError
