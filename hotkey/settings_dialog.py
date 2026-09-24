"""หน้าต่างตั้งค่าระบบ โมเดล AI และคลังศัพท์เฉพาะ (เปิดจากเมนู System Tray)

รองรับ:
- สลับผู้ให้บริการระหว่าง Google Gemini และ Local Model (Ollama)
- ตั้งค่าคีย์ Gemini, ลำดับโมเดลสำรอง Local Models (Ollama)
- แก้ไขคลังศัพท์เฉพาะทาง (glossary.md) ผ่าน UI โดยไม่ต้องเปิด Notepad
- ตั้งค่าปุ่มลัด (Hotkeys) และ Discord Bot
"""
from __future__ import annotations

import os
import threading
import tkinter as tk
import webbrowser
from tkinter import ttk
from typing import Callable

import keyboard

from core.config import MODES, set_active_provider, set_config_value, set_env_value
from core.providers import ProviderError
from core.providers.ollama import DEFAULT_OLLAMA_URL, is_ollama_running, query_ollama_models
from hotkey.popup import ACCENT, BG, FG, MUTED, PANEL

HOTKEY_LABELS = {
    "read": "แปลที่ลากคลุม -> ไทย",
    "reply": "ไทยในช่องพิมพ์ -> อังกฤษ",
    "explain": "อธิบายที่ลากคลุม",
    "polish": "แก้อังกฤษที่พิมพ์เอง",
}

GEMINI_URL = "https://aistudio.google.com/apikey"
DISCORD_URL = "https://discord.com/developers/applications"


class SettingsDialog:
    _current: "SettingsDialog | None" = None

    def __init__(self, root: tk.Tk, app, on_saved: Callable[[], None], initial_tab: str = "general"):
        if SettingsDialog._current is not None:
            SettingsDialog._current.win.lift()
            if initial_tab != SettingsDialog._current.active_tab:
                SettingsDialog._current.switch_tab(initial_tab)
            return

        SettingsDialog._current = self
        self.app = app
        self.on_saved = on_saved
        cfg = app.cfg
        self.active_tab = initial_tab

        font = ("Segoe UI", 10)
        small = ("Segoe UI", 9)

        win = self.win = tk.Toplevel(root)
        win.title("ZLZ-Translator: การตั้งค่าระบบและคลังศัพท์")
        win.configure(bg=BG)

        ico_file = os.path.join(str(app.cfg.root), "assets", "icon.ico")
        if os.path.exists(ico_file):
            try:
                win.iconbitmap(ico_file)
            except Exception:
                pass

        win.attributes("-topmost", True)
        win.resizable(True, True)
        win.minsize(580, 620)
        win.geometry("640x700")
        win.protocol("WM_DELETE_WINDOW", self.close)

        # ============================================================
        # แถบสลับแท็บด้านบน (Custom Dark Tabs)
        # ============================================================
        tab_bar = tk.Frame(win, bg=PANEL, padx=8, pady=6)
        tab_bar.pack(fill="x")

        self.btn_tab_general = tk.Button(
            tab_bar,
            text="⚙️ การตั้งค่าทั่วไป & โมเดล AI",
            command=lambda: self.switch_tab("general"),
            bd=0,
            padx=14,
            pady=6,
            font=("Segoe UI", 9, "bold"),
            cursor="hand2",
        )
        self.btn_tab_general.pack(side="left", padx=(0, 6))

        self.btn_tab_glossary = tk.Button(
            tab_bar,
            text="📖 คลังศัพท์เฉพาะทาง (glossary.md)",
            command=lambda: self.switch_tab("glossary"),
            bd=0,
            padx=14,
            pady=6,
            font=("Segoe UI", 9, "bold"),
            cursor="hand2",
        )
        self.btn_tab_glossary.pack(side="left")

        # Container สำหรับแสดงเนื้อหาแต่ละแท็บ
        self.container = tk.Frame(win, bg=BG)
        self.container.pack(fill="both", expand=True)

        # ------------------------------------------------------------
        # แท็บ 1: ทั่วไปและโมเดล (Scrollable)
        # ------------------------------------------------------------
        self.tab_general_frame = tk.Frame(self.container, bg=BG)
        self._build_general_tab(self.tab_general_frame, cfg, font, small)

        # ------------------------------------------------------------
        # แท็บ 2: คลังศัพท์เฉพาะ (glossary.md)
        # ------------------------------------------------------------
        self.tab_glossary_frame = tk.Frame(self.container, bg=BG)
        self._build_glossary_tab(self.tab_glossary_frame, cfg, font, small)

        # ------------------------------------------------------------
        # แถบปุ่มด้านล่างสุด (บันทึก / ทดสอบ / ปิด)
        # ------------------------------------------------------------
        bottom_bar = tk.Frame(win, bg=PANEL, padx=16, pady=10)
        bottom_bar.pack(fill="x", side="bottom")

        self._button(bottom_bar, "💾 บันทึกทั้งหมด", self._save, primary=True).pack(side="left")
        self._button(bottom_bar, "⚡ บันทึกและทดสอบแปล", self._save_and_test).pack(side="left", padx=(8, 0))
        self._button(bottom_bar, "ปิด", self.close).pack(side="right")

        self.status = tk.Label(win, text="", bg=BG, fg="#c7d2fe", font=small, justify="left", wraplength=600)
        self.status.pack(side="bottom", fill="x", padx=16, pady=(4, 0))

        # สลับไปยังแท็บเริ่มต้น
        self.switch_tab(initial_tab)

        # จัดให้อยู่กึ่งกลางหน้าจอ
        win.update_idletasks()
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        w, h = win.winfo_reqwidth(), win.winfo_reqheight()
        win.geometry(f"+{max(20, (sw - w) // 2)}+{max(20, (sh - h) // 2)}")
        win.focus_force()

        # ตรวจสอบ Ollama ในพื้นหลัง
        self._refresh_ollama_status_async()

    def switch_tab(self, tab_name: str) -> None:
        self.active_tab = tab_name
        if tab_name == "general":
            self.tab_glossary_frame.pack_forget()
            self.tab_general_frame.pack(fill="both", expand=True)
            self.btn_tab_general.configure(bg=ACCENT, fg="white", activebackground=ACCENT, activeforeground="white")
            self.btn_tab_glossary.configure(bg=PANEL, fg=MUTED, activebackground=PANEL, activeforeground=FG)
        else:
            self.tab_general_frame.pack_forget()
            self.tab_glossary_frame.pack(fill="both", expand=True)
            self.btn_tab_glossary.configure(bg=ACCENT, fg="white", activebackground=ACCENT, activeforeground="white")
            self.btn_tab_general.configure(bg=PANEL, fg=MUTED, activebackground=PANEL, activeforeground=FG)

    # =========================================================================
    # TAB 1: GENERAL & MODELS
    # =========================================================================
    def _build_general_tab(self, parent: tk.Frame, cfg, font, small) -> None:
        canvas = tk.Canvas(parent, bg=BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=BG, padx=16, pady=12)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")

        def _on_canvas_configure(event):
            canvas.itemconfig(canvas_window, width=event.width)
        canvas.bind("<Configure>", _on_canvas_configure)

        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # เพื่อรองรับการเลื่อนล้อเมาส์
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        body = scrollable_frame

        # ----------------------------------------------------
        # 1. ผู้ให้บริการแปลหลัก (Active Provider Selection)
        # ----------------------------------------------------
        self._section(body, "1. ผู้ให้บริการแปลหลัก (Primary Provider)", font)
        prov_box = tk.Frame(body, bg=PANEL, padx=10, pady=8)
        prov_box.pack(fill="x", pady=(2, 10))

        self.provider_var = tk.StringVar(value=cfg.active_provider)

        r_gemini = tk.Radiobutton(
            prov_box,
            text="Google Gemini (Cloud API: เร็ว, โควต้าฟรีสูงถึง 1,000 ครั้ง/วัน, แนะนำ)",
            variable=self.provider_var,
            value="gemini",
            bg=PANEL,
            fg=FG,
            selectcolor=BG,
            activebackground=PANEL,
            activeforeground="white",
            font=font,
        )
        r_gemini.pack(anchor="w", pady=2)

        r_ollama = tk.Radiobutton(
            prov_box,
            text="Local Model (Ollama ในเครื่อง: ออฟไลน์ ไม่ต้องต่อเน็ต, ฟรีไม่จำกัด)",
            variable=self.provider_var,
            value="ollama",
            bg=PANEL,
            fg=FG,
            selectcolor=BG,
            activebackground=PANEL,
            activeforeground="white",
            font=font,
        )
        r_ollama.pack(anchor="w", pady=2)

        self.ollama_status_lbl = tk.Label(
            prov_box,
            text="กำลังตรวจสอบ Ollama ในเครื่อง...",
            bg=PANEL,
            fg=MUTED,
            font=small,
        )
        self.ollama_status_lbl.pack(anchor="w", padx=20, pady=(2, 0))

        # ----------------------------------------------------
        # 2. Google Gemini
        # ----------------------------------------------------
        self._section(body, "2. Google Gemini (คีย์ฟรี)", font, top=6)
        tk.Label(
            body,
            text="ขอคีย์ฟรีด้วยบัญชี Google ของคุณ กดปุ่ม Create API key แล้วก๊อปมาวางในช่อง",
            bg=BG,
            fg=MUTED,
            font=small,
            justify="left",
            wraplength=560,
        ).pack(anchor="w")

        self._link_button(body, "เปิดหน้าขอคีย์ Gemini (aistudio.google.com)", GEMINI_URL).pack(anchor="w", pady=(4, 6))
        self.gemini_var = tk.StringVar(value=cfg.env.get("GEMINI_API_KEY", ""))
        self._entry(body, "GEMINI_API_KEY", self.gemini_var)

        tk.Label(
            body,
            text="ลำดับโมเดลสำรองอัตโนมัติ: 3.1 Flash Lite (500/วัน) → 3.5 Flash Lite (500/วัน) → 3.8 Flash → ...",
            bg=BG,
            fg="#94a3b8",
            font=("Segoe UI", 8),
        ).pack(anchor="w", pady=(4, 8))

        # ----------------------------------------------------
        # 3. Local Model (Ollama)
        # ----------------------------------------------------
        self._section(body, "3. Local Models (Ollama ในเครื่อง)", font, top=8)
        tk.Label(
            body,
            text="หากเครื่องคุณเปิด Ollama อยู่ ระบบจะตรวจพบโมเดลทั้งหมดโดยอัตโนมัติ สามารถเลือกลำดับโมเดลได้ตามต้องการ",
            bg=BG,
            fg=MUTED,
            font=small,
            justify="left",
            wraplength=560,
        ).pack(anchor="w")

        ollama_frame = tk.Frame(body, bg=PANEL, padx=10, pady=8)
        ollama_frame.pack(fill="x", pady=(4, 10))

        # Ollama URL
        url_row = tk.Frame(ollama_frame, bg=PANEL)
        url_row.pack(fill="x", pady=2)
        tk.Label(url_row, text="Ollama URL:", bg=PANEL, fg=MUTED, font=small, width=16, anchor="w").pack(side="left")
        self.ollama_url_var = tk.StringVar(value=cfg.ollama_url or DEFAULT_OLLAMA_URL)
        url_ent = tk.Entry(url_row, textvariable=self.ollama_url_var, bg=BG, fg=FG, relief="flat", font=("Consolas", 9))
        url_ent.pack(side="left", fill="x", expand=True, ipady=3)
        self._button(url_row, "🔄 รีเฟรชโมเดล", self._refresh_ollama_status_async).pack(side="left", padx=(6, 0))

        # โมเดลหลัก
        m_row = tk.Frame(ollama_frame, bg=PANEL)
        m_row.pack(fill="x", pady=(6, 2))
        tk.Label(m_row, text="โมเดลหลัก (Primary):", bg=PANEL, fg=FG, font=small, width=16, anchor="w").pack(side="left")
        self.ollama_model_var = tk.StringVar(value=cfg.ollama_model)
        self.ollama_combobox = ttk.Combobox(
            m_row,
            textvariable=self.ollama_model_var,
            font=("Consolas", 10),
            state="normal",
        )
        self.ollama_combobox.pack(side="left", fill="x", expand=True)

        # ลำดับโมเดลสำรอง (Local Fallback Chain)
        tk.Label(
            ollama_frame,
            text="ลำดับโมเดลสำรองของ Local Model (เมื่อโมเดลหลักขัดข้อง จะลองตามลำดับนี้):",
            bg=PANEL,
            fg=MUTED,
            font=small,
            anchor="w",
        ).pack(fill="x", pady=(8, 2))

        fb_box = tk.Frame(ollama_frame, bg=PANEL)
        fb_box.pack(fill="x", pady=2)

        self.fallback_listbox = tk.Listbox(
            fb_box,
            height=4,
            bg=BG,
            fg=FG,
            selectbackground=ACCENT,
            selectforeground="white",
            relief="flat",
            font=("Consolas", 9),
        )
        self.fallback_listbox.pack(side="left", fill="x", expand=True)

        # ใส่โมเดลสำรองเดิมลงใน listbox
        for m in cfg.ollama_fallback_models:
            self.fallback_listbox.insert("end", m)

        btn_col = tk.Frame(fb_box, bg=PANEL)
        btn_col.pack(side="left", padx=(6, 0))
        self._button(btn_col, "▲ เลื่อนขึ้น", self._move_fallback_up).pack(fill="x", pady=1)
        self._button(btn_col, "▼ เลื่อนลง", self._move_fallback_down).pack(fill="x", pady=1)
        self._button(btn_col, "➕ เพิ่ม", self._add_fallback_model).pack(fill="x", pady=1)
        self._button(btn_col, "➖ ลบ", self._remove_fallback_model).pack(fill="x", pady=1)

        # ----------------------------------------------------
        # 4. ปุ่มลัด (Hotkeys)
        # ----------------------------------------------------
        self._section(body, "4. ปุ่มลัด (Hotkeys ใช้งานได้ทุกแอป)", font, top=8)
        tk.Label(
            body,
            text='กด "กดปุ่ม" แล้วกดคีย์ที่ต้องการบนคีย์บอร์ด เช่น F8 หรือ Ctrl+Shift+T',
            bg=BG,
            fg=MUTED,
            font=small,
            justify="left",
            wraplength=560,
        ).pack(anchor="w")

        self.hotkey_vars: dict[str, tk.StringVar] = {}
        for mode in MODES:
            row = tk.Frame(body, bg=BG)
            row.pack(fill="x", pady=1)
            tk.Label(row, text=HOTKEY_LABELS[mode], bg=BG, fg=MUTED, font=small, width=24, anchor="w").pack(side="left")
            var = tk.StringVar(value=cfg.hotkey(mode) or "")
            self.hotkey_vars[mode] = var
            tk.Entry(
                row,
                textvariable=var,
                bg=PANEL,
                fg=FG,
                insertbackground=FG,
                relief="flat",
                font=("Consolas", 10),
                width=18,
            ).pack(side="left", ipady=3)
            self._button(row, "กดปุ่ม", lambda m=mode: self._capture_hotkey(m)).pack(side="left", padx=(6, 0))

        self.only_discord_var = tk.BooleanVar(value=any("discord" in a.lower() for a in cfg.only_in_apps))
        tk.Checkbutton(
            body,
            text="ให้ปุ่มลัดทำงานเฉพาะตอนหน้าต่าง Discord เปิดอยู่ (กันชนกับโปรแกรมอื่น)",
            variable=self.only_discord_var,
            bg=BG,
            fg=FG,
            selectcolor=PANEL,
            activebackground=BG,
            activeforeground=FG,
            font=small,
            anchor="w",
        ).pack(anchor="w", pady=(4, 0))

        # ----------------------------------------------------
        # 5. Discord App
        # ----------------------------------------------------
        self._section(body, "5. Discord App (ทางเลือก: แปลในแชทและมือถือ)", font, top=8)
        tk.Label(
            body,
            text="สร้างแอปที่ Developer Portal > แท็บ Installation ติ๊ก User Install, Scope: applications.commands > แท็บ Bot กด Reset Token แล้วนำมาใส่",
            bg=BG,
            fg=MUTED,
            font=small,
            justify="left",
            wraplength=560,
        ).pack(anchor="w")

        self._link_button(body, "เปิด Discord Developer Portal", DISCORD_URL).pack(anchor="w", pady=(4, 6))
        self.discord_var = tk.StringVar(value=cfg.env.get("DISCORD_TOKEN", ""))
        self._entry(body, "DISCORD_TOKEN", self.discord_var)

        self.discord_autostart_var = tk.BooleanVar(value=cfg.discord_autostart)
        tk.Checkbutton(
            body,
            text="เปิด Discord app อัตโนมัติพร้อมโปรแกรม (ต้องมี DISCORD_TOKEN)",
            variable=self.discord_autostart_var,
            bg=BG,
            fg=FG,
            selectcolor=PANEL,
            activebackground=BG,
            activeforeground=FG,
            font=small,
            anchor="w",
        ).pack(anchor="w", pady=(4, 10))

    # =========================================================================
    # TAB 2: GLOSSARY EDITOR (glossary.md)
    # =========================================================================
    def _build_glossary_tab(self, parent: tk.Frame, cfg, font, small) -> None:
        body = tk.Frame(parent, bg=BG, padx=16, pady=12)
        body.pack(fill="both", expand=True)

        header_row = tk.Frame(body, bg=BG)
        header_row.pack(fill="x", pady=(0, 6))

        tk.Label(
            header_row,
            text="📖 จัดการคลังศัพท์เฉพาะทางและบริบทงาน (glossary.md)",
            bg=BG,
            fg=FG,
            font=(font[0], font[1], "bold"),
            anchor="w",
        ).pack(side="left")

        self._button(
            header_row,
            "📂 เปิดใน Notepad",
            lambda: os.startfile(os.path.join(str(cfg.root), "glossary.md")),
        ).pack(side="right")

        tk.Label(
            body,
            text="เนื้อหาด้านล่างจะถูกแนบเป็นบริบทกับคำสั่งแปลของ AI ทุกครั้ง เพื่อแปลศัพท์เฉพาะทางได้ตรงใจและแม่นยำที่สุด",
            bg=BG,
            fg=MUTED,
            font=small,
            anchor="w",
            justify="left",
            wraplength=600,
        ).pack(fill="x", pady=(0, 6))

        # แถบเครื่องมือช่วยแทรกด่วน (Quick Insert Toolbar)
        toolbar = tk.Frame(body, bg=PANEL, padx=8, pady=6)
        toolbar.pack(fill="x", pady=(0, 8))

        tk.Label(toolbar, text="แทรกด่วน:", bg=PANEL, fg=MUTED, font=("Segoe UI", 8, "bold")).pack(side="left", padx=(0, 6))
        self._button(
            toolbar,
            "➕ คำทับศัพท์ (Keep English)",
            lambda: self._insert_glossary_snippet("\n## Terms to Keep Untranslated\nShader, Rig, Mesh, Texture, Normal Map\n"),
        ).pack(side="left", padx=2)
        self._button(
            toolbar,
            "➕ ชื่อเฉพาะ (Proper Noun)",
            lambda: self._insert_glossary_snippet("\n## Proper Nouns & Product Names\n- MyProduct = ชื่อโปรเจกต์ ห้ามแปลหรือเปลี่ยนตัวสะกด\n"),
        ).pack(side="left", padx=2)
        self._button(
            toolbar,
            "➕ ข้อตกลงภาษา (Guidelines)",
            lambda: self._insert_glossary_snippet("\n## Tone & Communication Guidelines\n- ไม่สัญญาเกินกว่าที่ลูกค้าพิมพ์\n"),
        ).pack(side="left", padx=2)
        self._button(
            toolbar,
            "↩️ โหลดไฟล์ใหม่",
            self._reload_glossary_file,
        ).pack(side="right")

        # Text Editor
        text_frame = tk.Frame(body, bg=BG)
        text_frame.pack(fill="both", expand=True)

        self.glossary_text = tk.Text(
            text_frame,
            bg=PANEL,
            fg=FG,
            insertbackground=FG,
            relief="flat",
            font=("Consolas", 10),
            wrap="word",
            padx=10,
            pady=8,
        )
        gl_scroll = ttk.Scrollbar(text_frame, orient="vertical", command=self.glossary_text.yview)
        self.glossary_text.configure(yscrollcommand=gl_scroll.set)

        self.glossary_text.pack(side="left", fill="both", expand=True)
        gl_scroll.pack(side="right", fill="y")

        # โหลดเนื้อหา glossary.md เริ่มต้น
        self._reload_glossary_file()

    def _reload_glossary_file(self) -> None:
        path = self.app.cfg.root / "glossary.md"
        content = ""
        if path.exists():
            try:
                content = path.read_text(encoding="utf-8")
            except Exception as e:
                content = f"# ข้อผิดพลาดในการอ่านไฟล์: {e}"
        self.glossary_text.delete("1.0", "end")
        self.glossary_text.insert("1.0", content)

    def _insert_glossary_snippet(self, snippet: str) -> None:
        self.glossary_text.insert("end", snippet)
        self.glossary_text.see("end")

    # =========================================================================
    # OLLAMA HELPERS
    # =========================================================================
    def _refresh_ollama_status_async(self) -> None:
        url = self.ollama_url_var.get().strip() or DEFAULT_OLLAMA_URL
        self.ollama_status_lbl.configure(text=f"กำลังตรวจสอบ Ollama ที่ {url}...", fg=MUTED)

        def worker():
            models = query_ollama_models(url, timeout=2.0)
            running = is_ollama_running(url, timeout=1.5)

            def apply():
                if running and models:
                    self.ollama_status_lbl.configure(
                        text=f"🟢 เชื่อมต่อสำเร็จ: ตรวจพบ {len(models)} โมเดลในเครื่อง ({', '.join(models[:4])})",
                        fg="#86efac",
                    )
                    # อัปเดตรายการใน combobox
                    self.ollama_combobox["values"] = models
                    if not self.ollama_model_var.get() or self.ollama_model_var.get() not in models:
                        self.ollama_model_var.set(models[0])
                elif running:
                    self.ollama_status_lbl.configure(
                        text=f"🟡 เชื่อมต่อ Ollama ได้แต่ไม่พบโมเดล (ดาวน์โหลดก่อน เช่น 'ollama run qwen2.5:7b')",
                        fg="#fde047",
                    )
                else:
                    self.ollama_status_lbl.configure(
                        text=f"⚪ ไม่พบ Ollama ที่ {url} (หากไม่ได้เปิด Ollama ให้ข้ามส่วนนี้ได้)",
                        fg=MUTED,
                    )

            self._ui(apply)

        threading.Thread(target=worker, daemon=True).start()

    def _move_fallback_up(self) -> None:
        idx = self.fallback_listbox.curselection()
        if not idx or idx[0] == 0:
            return
        i = idx[0]
        item = self.fallback_listbox.get(i)
        self.fallback_listbox.delete(i)
        self.fallback_listbox.insert(i - 1, item)
        self.fallback_listbox.selection_set(i - 1)

    def _move_fallback_down(self) -> None:
        idx = self.fallback_listbox.curselection()
        if not idx or idx[0] >= self.fallback_listbox.size() - 1:
            return
        i = idx[0]
        item = self.fallback_listbox.get(i)
        self.fallback_listbox.delete(i)
        self.fallback_listbox.insert(i + 1, item)
        self.fallback_listbox.selection_set(i + 1)

    def _add_fallback_model(self) -> None:
        # ดึงโมเดลจาก combobox หรือ prompt
        m = self.ollama_model_var.get().strip()
        models_available = list(self.ollama_combobox["values"]) if self.ollama_combobox["values"] else []
        existing = list(self.fallback_listbox.get(0, "end"))

        # ถ้ามีโมเดลอื่นที่ยังไม่ได้เพิ่ม ให้เพิ่มตัวแรกที่ว่าง
        to_add = None
        for cand in models_available:
            if cand != m and cand not in existing:
                to_add = cand
                break
        if not to_add and m and m not in existing:
            to_add = m

        if to_add:
            self.fallback_listbox.insert("end", to_add)
            self.fallback_listbox.selection_clear(0, "end")
            self.fallback_listbox.selection_set("end")
        else:
            self.status.configure(text="ไม่มีโมเดลอื่นให้เพิ่ม หรือโมเดลถูกเพิ่มไปหมดแล้ว", fg="#fbbf24")

    def _remove_fallback_model(self) -> None:
        idx = self.fallback_listbox.curselection()
        if not idx:
            return
        self.fallback_listbox.delete(idx[0])

    # =========================================================================
    # ACTIONS & SAVING
    # =========================================================================
    def _save(self, quiet: bool = False) -> bool:
        # ตรวจปุ่มลัด
        hotkeys: dict[str, str] = {}
        for mode, var in self.hotkey_vars.items():
            combo = var.get().strip().lower().replace(" ", "")
            if not combo:
                continue
            try:
                keyboard.parse_hotkey(combo)
            except (ValueError, KeyError):
                self.status.configure(
                    text=f"ปุ่มลัด '{combo}' ({HOTKEY_LABELS[mode]}) ไม่ถูกต้อง ลองกดปุ่ม \"กดปุ่ม\" แล้วกดคีย์ที่ต้องการ",
                    fg="#f87171",
                )
                return False
            if combo in hotkeys.values():
                self.status.configure(text=f"ปุ่มลัด '{combo}' ถูกใช้ซ้ำ 2 โหมด", fg="#f87171")
                return False
            hotkeys[mode] = combo

        try:
            root = self.app.cfg.root

            # 1. เขียน .env
            set_env_value(root, "GEMINI_API_KEY", self.gemini_var.get())
            set_env_value(root, "DISCORD_TOKEN", self.discord_var.get())

            # 2. บันทึก Provider หลัก
            active_p = self.provider_var.get()
            set_active_provider(root, active_p)

            # 3. บันทึก Ollama config
            set_config_value(root, "providers.ollama", "url", self.ollama_url_var.get().strip())
            set_config_value(root, "providers.ollama", "model", self.ollama_model_var.get().strip())

            # บันทึก Fallback Models ของ Ollama
            fallbacks = list(self.fallback_listbox.get(0, "end"))
            set_config_value(root, "providers.ollama", "fallback_models", fallbacks)

            # 4. บันทึกปุ่มลัด และ discord autostart
            for mode in MODES:
                set_config_value(root, "hotkeys", mode, hotkeys.get(mode, ""))
            set_config_value(root, "hotkeys", "only_in_apps", ["Discord"] if self.only_discord_var.get() else [])
            set_config_value(root, "discord", "autostart", self.discord_autostart_var.get())

            # 5. บันทึก glossary.md และสร้าง compact glossary ทันทีโดยไม่แก้ glossary.md ต้นฉบับ
            glossary_content = self.glossary_text.get("1.0", "end-1c")
            (root / "glossary.md").write_text(glossary_content, encoding="utf-8")
            from core.glossary import get_compact_glossary
            get_compact_glossary(root, glossary_content)

        except OSError as e:
            self.status.configure(text=f"บันทึกไม่สำเร็จ: {e}", fg="#f87171")
            return False

        self.on_saved()
        if not quiet:
            self.status.configure(text="✓ บันทึกการตั้งค่าและคลังศัพท์เรียบร้อย ระบบโหลดค่าใหม่แล้ว", fg="#86efac")
        return True

    def _save_and_test(self) -> None:
        if not self._save(quiet=True):
            return
        active_p = self.provider_var.get()
        self.status.configure(text=f"กำลังทดสอบแปลด้วย {active_p}...", fg="#c7d2fe")

        def run():
            try:
                r = self.app.translator.run("read", "Hello! Could you send me the files by Friday?", provider=active_p)
                text = f"✓ ใช้ได้: แปลผ่าน {r.provider} ({r.model}) ใน {r.seconds:.1f} วินาที\n{r.text}"
                color = "#86efac"
            except (ProviderError, ValueError) as e:
                text, color = f"ยังใช้ไม่ได้:\n{e}", "#f87171"
            self._ui(lambda: self.status.configure(text=text, fg=color))

        threading.Thread(target=run, daemon=True).start()

    def _capture_hotkey(self, mode: str) -> None:
        self.status.configure(text=f"กดปุ่มที่ต้องการสำหรับ \"{HOTKEY_LABELS[mode]}\" ได้เลย (รอ 10 วินาที)", fg="#c7d2fe")
        was_paused = getattr(self.app, "paused", False)
        if hasattr(self.app, "paused"):
            self.app.paused = True

        def run():
            combo = ""
            try:
                combo = keyboard.read_hotkey(suppress=False)
            except Exception as e:
                self._ui(lambda: self.status.configure(text=f"อ่านปุ่มไม่ได้: {e}", fg="#f87171"))
            finally:
                if hasattr(self.app, "paused"):
                    self.app.paused = was_paused
            if combo:
                def apply():
                    self.hotkey_vars[mode].set(combo)
                    self.status.configure(text=f"ตั้งเป็น {combo} แล้ว กด \"บันทึก\" เพื่อใช้งาน", fg="#86efac")
                self._ui(apply)

        threading.Thread(target=run, daemon=True).start()

    # =========================================================================
    # WIDGET HELPERS
    # =========================================================================
    def _section(self, parent, text, font, top=0):
        tk.Label(parent, text=text, bg=BG, fg=FG, font=(font[0], font[1], "bold"), anchor="w").pack(fill="x", pady=(top, 2))

    def _entry(self, parent, label, var):
        row = tk.Frame(parent, bg=BG)
        row.pack(fill="x")
        tk.Label(row, text=label, bg=BG, fg=MUTED, font=("Consolas", 9), width=16, anchor="w").pack(side="left")
        entry = tk.Entry(row, textvariable=var, show="•", bg=PANEL, fg=FG, insertbackground=FG, relief="flat",
                         font=("Consolas", 10), width=46)
        entry.pack(side="left", fill="x", expand=True, ipady=4)
        tk.Button(row, text="แสดง", bg=PANEL, fg=MUTED, bd=0, font=("Segoe UI", 8), padx=6,
                  command=lambda e=entry: e.configure(show="" if e.cget("show") else "•")).pack(side="left", padx=(4, 0))

    def _button(self, parent, text, command, primary=False):
        return tk.Button(parent, text=text, command=command, bg=ACCENT if primary else PANEL, fg="white" if primary else FG,
                         bd=0, padx=12, pady=5, font=("Segoe UI", 9), cursor="hand2",
                         activebackground=ACCENT, activeforeground="white")

    def _link_button(self, parent, text, url):
        return self._button(parent, "🌐 " + text, lambda: webbrowser.open(url))

    def _ui(self, fn) -> None:
        def safe():
            try:
                fn()
            except tk.TclError:
                pass
        if hasattr(self.app, "ui"):
            self.app.ui(safe)
        else:
            try:
                self.win.after(0, safe)
            except RuntimeError:
                pass

    def close(self) -> None:
        SettingsDialog._current = None
        try:
            self.win.destroy()
        except tk.TclError:
            pass
