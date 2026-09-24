"""ไอคอนใน system tray (pystray) พร้อมเมนูตั้งค่าเร็ว

คลิกซ้ายที่ไอคอน = เปิด/ปิดการทำงาน (ไอคอนสีเทาเมื่อปิด)
คลิกขวา = เมนู
"""
from __future__ import annotations

import os
from typing import Callable

import pystray
from PIL import Image, ImageDraw, ImageFont

from core.config import TONES

TONE_LABELS = {"formal": "ทางการ", "friendly": "เป็นกันเอง", "brief": "สั้น"}

_DARK_BG = (15, 23, 42, 255)
_CYAN_ACCENT = (56, 189, 248, 255)
_ORANGE = (245, 158, 11, 255)
_GRAY = (100, 116, 139, 255)


def _make_icon_image(color: tuple, text: str = "ZLZ", text_color: tuple | str = "white") -> Image.Image:
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((2, 2, size - 2, size - 2), radius=16, fill=color)
    try:
        font = ImageFont.truetype("segoeuib.ttf", 26)
    except OSError:
        font = ImageFont.load_default()
    draw.text((size / 2, size / 2), text, fill=text_color, font=font, anchor="mm")
    return img


class Tray:
    def __init__(
        self,
        *,
        get_status: Callable[[], str],
        get_tone: Callable[[], str],
        set_tone: Callable[[str], None],
        get_usage: Callable[[], str],
        reload: Callable[[], None],
        quit_app: Callable[[], None],
        root_dir: str,
        get_enabled: Callable[[], bool] = lambda: True,
        toggle_enabled: Callable[[], None] = lambda: None,
        get_discord_running: Callable[[], bool] = lambda: False,
        toggle_discord: Callable[[], None] = lambda: None,
        has_discord_token: Callable[[], bool] = lambda: False,
        open_settings: Callable[[], None] = lambda: None,
        open_glossary: Callable[[], None] = lambda: None,
        get_provider: Callable[[], str] = lambda: "gemini",
        set_provider: Callable[[str], None] = lambda _p: None,
        is_ollama_available: Callable[[], bool] = lambda: False,
        get_ollama_model: Callable[[], str] = lambda: "",
        get_autostart: Callable[[], bool] = lambda: False,
        toggle_autostart: Callable[[], None] = lambda: None,
        get_hotkeys: Callable[[], str] = lambda: "",
    ):
        self._get_hotkeys = get_hotkeys
        self._get_status = get_status
        self._get_tone = get_tone
        self._set_tone = set_tone
        self._get_usage = get_usage
        self._reload = reload
        self._quit = quit_app
        self._root_dir = root_dir
        self._get_enabled = get_enabled
        self._toggle_enabled = toggle_enabled
        self._get_discord_running = get_discord_running
        self._toggle_discord = toggle_discord
        self._has_discord_token = has_discord_token
        self._open_settings = open_settings
        self._open_glossary = open_glossary
        self._get_provider = get_provider
        self._set_provider = set_provider
        self._is_ollama_available = is_ollama_available
        self._get_ollama_model = get_ollama_model
        self._get_autostart = get_autostart
        self._toggle_autostart = toggle_autostart

        normal_icon = None
        for candidate in (
            os.path.join(root_dir, "assets", "icon.png"),
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "icon.png"),
        ):
            if os.path.exists(candidate):
                try:
                    normal_icon = Image.open(candidate).convert("RGBA").resize((64, 64), Image.Resampling.LANCZOS)
                    break
                except Exception:
                    pass
        if normal_icon is None:
            normal_icon = _make_icon_image(_DARK_BG, "ZLZ", _CYAN_ACCENT)

        self._icons = {
            "normal": normal_icon,
            "busy": _make_icon_image(_ORANGE, "ZLZ", "white"),
            "off": _make_icon_image(_GRAY, "ZLZ", "white"),
        }
        self._busy = False
        self.icon = pystray.Icon("zlz-translator", self._icons["normal"], "ZLZ-translator (Gemini-version)", menu=self._menu())

    def _menu(self) -> pystray.Menu:
        def tone_item(tone: str):
            return pystray.MenuItem(
                TONE_LABELS[tone],
                lambda: self._set_tone(tone),
                checked=lambda _item, t=tone: self._get_tone() == t,
                radio=True,
            )

        def ollama_label():
            avail = self._is_ollama_available()
            model = self._get_ollama_model() or "Local"
            if avail:
                return f"Local Model (Ollama: {model})"
            return "Local Model (Ollama: ไม่พบในเครื่อง)"

        return pystray.Menu(
            # default=True -> คลิกซ้ายที่ไอคอนจะเรียกรายการนี้
            pystray.MenuItem(
                lambda _i: "เปิดใช้งานอยู่ (คลิกเพื่อปิด)" if self._get_enabled() else "ปิดอยู่ (คลิกเพื่อเปิด)",
                lambda: self._toggle_enabled(),
                checked=lambda _item: self._get_enabled(),
                default=True,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(lambda _i: self._get_hotkeys(), None, enabled=False),
            pystray.MenuItem(lambda _i: self._get_status(), None, enabled=False),
            pystray.MenuItem(lambda _i: self._get_usage(), None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "ผู้ให้บริการแปล (Provider)",
                pystray.Menu(
                    pystray.MenuItem(
                        "Google Gemini (Cloud API)",
                        lambda: self._set_provider("gemini"),
                        checked=lambda _item: self._get_provider() == "gemini",
                        radio=True,
                    ),
                    pystray.MenuItem(
                        lambda _i: ollama_label(),
                        lambda: self._set_provider("ollama"),
                        checked=lambda _item: self._get_provider() == "ollama",
                        enabled=lambda _item: self._is_ollama_available(),
                        radio=True,
                    ),
                ),
            ),
            pystray.MenuItem("น้ำเสียงตอนตอบ", pystray.Menu(*[tone_item(t) for t in TONES])),
            pystray.MenuItem(
                lambda _i: "Discord app: กำลังทำงาน (คลิกเพื่อปิด)" if self._get_discord_running()
                else "Discord app: ปิดอยู่ (คลิกเพื่อเปิด)",
                lambda: self._toggle_discord(),
                enabled=lambda _item: self._has_discord_token(),
            ),
            pystray.MenuItem("เปิดอัตโนมัติเมื่อเข้า Windows", lambda: self._toggle_autostart(),
                             checked=lambda _item: self._get_autostart()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("⚙️ ตั้งค่าระบบและโมเดล...", lambda: self._open_settings()),
            pystray.MenuItem("📖 จัดการคลังศัพท์ (glossary.md)...", lambda: self._open_glossary()),
            pystray.MenuItem(
                "เปิดไฟล์ดิบ (Notepad)",
                pystray.Menu(
                    pystray.MenuItem("เปิด config.toml", lambda: self._open("config.toml")),
                    pystray.MenuItem("เปิด glossary.md", lambda: self._open("glossary.md")),
                ),
            ),
            pystray.MenuItem("โหลดการตั้งค่าใหม่", lambda: self._reload()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("ออกจากโปรแกรม", lambda: self._quit()),
        )


    def _open(self, name: str) -> None:
        os.startfile(os.path.join(self._root_dir, name))

    def set_busy(self, busy: bool) -> None:
        self._busy = busy
        self.refresh_icon()

    def refresh_icon(self) -> None:
        if not self._get_enabled():
            self.icon.icon = self._icons["off"]
            self.icon.title = "ZLZ-translator (Gemini-version) (ปิดอยู่)"
        elif self._busy:
            self.icon.icon = self._icons["busy"]
            self.icon.title = "ZLZ-translator (Gemini-version) (กำลังแปล...)"
        else:
            self.icon.icon = self._icons["normal"]
            self.icon.title = "ZLZ-translator (Gemini-version)"

    def refresh(self) -> None:
        self.refresh_icon()
        self.icon.update_menu()

    def start(self) -> None:
        self.icon.run_detached()

    def stop(self) -> None:
        try:
            self.icon.stop()
        except Exception:
            pass
