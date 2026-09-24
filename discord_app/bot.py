"""Discord User App: ติดตั้งที่ตัวผู้ใช้ ใช้ได้ทุกเซิร์ฟเวอร์และ DM โดยไม่ต้องขอสิทธิ์ admin

    python -m discord_app.bot

คำสั่งใน Discord (ผลลัพธ์ทั้งหมดเห็นเฉพาะคุณ):
  คลิกขวาที่ข้อความ -> Apps -> "แปลเป็นไทย" / "อธิบายข้อความนี้"
  /en   <ข้อความไทย> [tone]     -> อังกฤษสำหรับส่งลูกค้า
  /th   <ข้อความอังกฤษ>          -> ไทย
  /fix  <ข้อความอังกฤษ> [tone]   -> แก้อังกฤษที่พิมพ์เองให้ถูก
"""
from __future__ import annotations

import asyncio
import logging
import sys
from logging.handlers import RotatingFileHandler

import discord
from discord import app_commands

from core.config import load_config, set_active_provider
from core.providers import ProviderError
from core.translator import Result, Translator

log = logging.getLogger("discord_app")

TONE_LABELS = {"friendly": "เป็นกันเอง", "formal": "ทางการ", "brief": "สั้น"}
TONE_CHOICES = [
    app_commands.Choice(name="เป็นกันเอง (ค่าเริ่มต้น)", value="friendly"),
    app_commands.Choice(name="ทางการ", value="formal"),
    app_commands.Choice(name="สั้น", value="brief"),
]
MODE_LABELS = {"read": "แปลเป็นไทย", "reply": "ตอบเป็นอังกฤษ", "explain": "อธิบาย", "polish": "ขัดเกลา"}
MAX_LEN = 1900  # Discord จำกัด 2000 ตัวอักษรต่อข้อความ


class TranslatorBot(discord.Client):
    def __init__(self, translator: Translator):
        super().__init__(intents=discord.Intents.none())
        self.translator = translator
        self._cfg_mtime: float = 0.0
        # ให้ทุกคำสั่งติดตั้งได้ทั้งแบบ user และ guild และใช้ได้ทั้งใน guild, DM, group DM
        self.tree = app_commands.CommandTree(
            self,
            allowed_installs=app_commands.AppInstallationType(guild=True, user=True),
            allowed_contexts=app_commands.AppCommandContext(guild=True, dm_channel=True, private_channel=True),
        )
        register_commands(self)

    async def setup_hook(self) -> None:
        asyncio.create_task(self._sync_commands_background())

    async def _sync_commands_background(self) -> None:
        try:
            synced = await self.tree.sync()
            log.info("synced %d commands: %s", len(synced), ", ".join(c.name for c in synced))
        except Exception as e:
            log.warning("command sync warning: %s", e)

    async def on_ready(self) -> None:
        log.info("logged in as %s (id=%s)", self.user, self.user.id if self.user else "?")

    def is_ollama_available(self) -> bool:
        """ตรวจสอบว่าในเครื่องมี Ollama เปิดอยู่และมีโมเดลพร้อมใช้หรือไม่"""
        try:
            return self.translator._provider("ollama").available()
        except Exception:
            return False

    def _sync_config_if_needed(self) -> None:
        """ตรวจสอบและโหลด config.toml ใหม่ทันทีหากมีการเปลี่ยนแปลง (เช่น สลับไปใช้ Local Model ใน Tray)"""
        try:
            cfg_file = self.translator.config.root / "config.toml"
            if cfg_file.exists():
                mtime = cfg_file.stat().st_mtime
                if mtime != self._cfg_mtime:
                    self._cfg_mtime = mtime
                    self.translator.reload()
                    log.info("Discord bot reloaded config: active_provider=%s", self.translator.config.active_provider)
        except Exception as e:
            log.warning("Discord bot reload config failed: %s", e)

    async def translate(self, mode: str, text: str, tone: str | None = None, provider: str | None = None) -> Result:
        return await asyncio.to_thread(self._translate_sync, mode, text, tone, provider)

    def _translate_sync(self, mode: str, text: str, tone: str | None = None, provider: str | None = None) -> Result:
        self._sync_config_if_needed()
        return self.translator.run(mode, text, tone, provider=provider)


# ---------------------------------------------------------------------------- helpers
def _clip(text: str) -> str:
    return text if len(text) <= MAX_LEN else text[: MAX_LEN - 3] + "..."


def _format(result: Result) -> str:
    fallback_tag = " · (ตัวสำรอง)" if result.fallback_used else ""
    provider_label = "Ollama (Local)" if result.provider == "ollama" else "Gemini"
    footer = f"-# 🤖 ผู้ให้บริการ: **{provider_label}** (`{result.model}`){fallback_tag} · {result.seconds:.1f}s · {MODE_LABELS.get(result.mode, result.mode)}"
    if result.mode in ("reply", "polish"):
        footer += f" · {TONE_LABELS.get(result.tone, result.tone)}"
    return _clip(result.text) + "\n" + footer


async def _send_draft(interaction: discord.Interaction, original: str, result: Result) -> None:
    """โหมดตอบ/ขัดเกลา: ส่งข้อความร่าง (เห็นเฉพาะคุณ) พร้อมปุ่มส่งลงแชนเนลทันทีและปุ่มเปลี่ยนน้ำเสียง"""
    draft_msg = await interaction.followup.send(_clip(result.text), ephemeral=True, wait=True)
    fallback_tag = " · (ตัวสำรอง)" if result.fallback_used else ""
    provider_label = "Ollama (Local)" if result.provider == "ollama" else "Gemini"
    footer = (f"-# 🤖 แปลด้วย: **{provider_label}** (`{result.model}`){fallback_tag} · {result.seconds:.1f}s · {TONE_LABELS.get(result.tone, result.tone)}\n"
              f"-# ⬆ ก๊อปข้อความไปส่งเอง หรือกดปุ่ม «ส่งข้อความนี้เลย» ด้านล่าง")
    view = ReplyView(original, result, orig_interaction=interaction, draft_msg=draft_msg)
    panel_msg = await interaction.followup.send(footer, view=view, ephemeral=True, wait=True)
    view.panel_msg = panel_msg


class FailoverView(discord.ui.View):
    """ปุ่มสำหรับสลับไปแปลด้วย Local Model (Ollama) ทันทีเมื่อ Gemini ล้มเหลว"""

    def __init__(
        self,
        bot: TranslatorBot,
        mode: str,
        text: str,
        tone: str | None,
        orig_interaction: discord.Interaction | None = None,
    ):
        super().__init__(timeout=300)
        self.bot = bot
        self.mode = mode
        self.text = text
        self.tone = tone
        self.orig_interaction = orig_interaction
        self.fail_msg: discord.WebhookMessage | None = None

        local_model = bot.translator.config.ollama_model or "Local"

        # ปุ่มลองแปลด้วย Local Model
        retry_btn = discord.ui.Button(
            label=f"ลองแปลด้วย Local Model ({local_model})",
            emoji="🔄",
            style=discord.ButtonStyle.primary,
            row=0,
        )
        retry_btn.callback = self._retry_local
        self.add_item(retry_btn)

        # ปุ่มสลับใช้ Local Model เป็นหลัก
        switch_btn = discord.ui.Button(
            label="สลับใช้ Local Model เป็นหลัก",
            emoji="⚙️",
            style=discord.ButtonStyle.secondary,
            row=0,
        )
        switch_btn.callback = self._switch_and_retry_local
        self.add_item(switch_btn)

        # ปุ่มปิด
        dismiss_btn = discord.ui.Button(
            label="ปิด",
            emoji="🗑️",
            style=discord.ButtonStyle.secondary,
            row=1,
        )
        dismiss_btn.callback = self._dismiss
        self.add_item(dismiss_btn)

    async def _cleanup(self):
        if self.fail_msg is not None:
            try:
                await self.fail_msg.delete()
            except Exception:
                pass

    async def _dismiss(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer()
        except Exception:
            pass
        await self._cleanup()

    async def _retry_local(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            result = await self.bot.translate(self.mode, self.text, self.tone, provider="ollama")
        except ProviderError as e:
            await interaction.followup.send(
                f"❌ Local Model ({self.bot.translator.config.ollama_model}) ก็แปลไม่สำเร็จ:\n{_clip(str(e))}",
                ephemeral=True,
            )
            return
        await self._cleanup()
        if self.mode in ("reply", "polish"):
            await _send_draft(interaction, self.text, result)
        else:
            await interaction.followup.send(_format(result), ephemeral=True)

    async def _switch_and_retry_local(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            set_active_provider(self.bot.translator.config.root, "ollama")
            self.bot.translator.reload()
            result = await self.bot.translate(self.mode, self.text, self.tone, provider="ollama")
        except Exception as e:
            await interaction.followup.send(f"❌ สลับผู้ให้บริการไม่สำเร็จ: {_clip(str(e))}", ephemeral=True)
            return
        await self._cleanup()
        await interaction.followup.send("⚙️ สลับผู้ให้บริการหลักเป็น **Local Model (Ollama)** เรียบร้อยแล้ว", ephemeral=True)
        if self.mode in ("reply", "polish"):
            await _send_draft(interaction, self.text, result)
        else:
            await interaction.followup.send(_format(result), ephemeral=True)


async def _run(interaction: discord.Interaction, mode: str, text: str, tone: str | None = None) -> None:
    bot: TranslatorBot = interaction.client  # type: ignore[assignment]
    text = (text or "").strip()
    if not text:
        await interaction.response.send_message("ข้อความนี้ไม่มีตัวหนังสือให้แปล (อาจเป็นรูปหรือไฟล์)", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True, thinking=True)
    try:
        result = await bot.translate(mode, text, tone)
    except ProviderError as e:
        # หากแปลด้วย Gemini ล้มเหลว และในเครื่องมี Ollama/Local Model พร้อมใช้
        if bot.translator.config.active_provider != "ollama" and bot.is_ollama_available():
            view = FailoverView(bot, mode, text, tone, orig_interaction=interaction)
            local_model = bot.translator.config.ollama_model or "Local Model"
            err_short = str(e).strip().splitlines()[0] if str(e) else "เซิร์ฟเวอร์ขัดข้อง"
            msg = (
                f"⚠️ **Gemini แปลไม่สำเร็จ** ({err_short})\n"
                f"-# ตรวจพบ Local Model ({local_model}) ในเครื่องของคุณ กดปุ่มด้านล่างเพื่อแปลทันที:"
            )
            fail_msg = await interaction.followup.send(msg, view=view, ephemeral=True, wait=True)
            view.fail_msg = fail_msg
            return

        await interaction.followup.send(f"❌ แปลไม่สำเร็จ\n{_clip(str(e))}", ephemeral=True)
        return
    except Exception as e:  # noqa: BLE001
        log.exception("unexpected")
        await interaction.followup.send(f"❌ ข้อผิดพลาดไม่คาดคิด: {e}", ephemeral=True)
        return
    if mode in ("reply", "polish"):
        await _send_draft(interaction, text, result)
    else:
        await interaction.followup.send(_format(result), ephemeral=True)



class ReplyView(discord.ui.View):
    """ปุ่มใต้ร่างคำตอบ: ส่งทันที, ปิด/Dismiss, เปลี่ยนน้ำเสียง"""

    def __init__(
        self,
        original: str,
        result: Result,
        orig_interaction: discord.Interaction | None = None,
        draft_msg: discord.WebhookMessage | None = None,
    ):
        super().__init__(timeout=900)
        self.original = original
        self.result = result
        self.orig_interaction = orig_interaction
        self.draft_msg = draft_msg
        self.panel_msg: discord.WebhookMessage | None = None

        # ปุ่มส่งข้อความทันที
        send_btn = discord.ui.Button(
            label="ส่งข้อความนี้เลย",
            emoji="🚀",
            style=discord.ButtonStyle.success,
            row=0,
        )
        send_btn.callback = self._send_now
        self.add_item(send_btn)

        # ปุ่มปิด / Dismiss ข้อความ
        dismiss_btn = discord.ui.Button(
            label="ปิด",
            emoji="🗑️",
            style=discord.ButtonStyle.secondary,
            row=0,
        )
        dismiss_btn.callback = self._dismiss
        self.add_item(dismiss_btn)

        # ปุ่มเปลี่ยนน้ำเสียง
        for tone, label in TONE_LABELS.items():
            btn = discord.ui.Button(
                label=f"แปลใหม่แบบ{label}",
                style=discord.ButtonStyle.secondary,
                disabled=(tone == result.tone),
                row=1,
            )
            btn.callback = self._make_retone(tone)
            self.add_item(btn)

    async def _send_now(self, interaction: discord.Interaction):
        text_to_send = _clip(self.result.text)
        sent = False
        if interaction.channel:
            try:
                await interaction.channel.send(text_to_send)
                sent = True
            except Exception:
                sent = False

        if not sent:
            await interaction.response.send_message(text_to_send, ephemeral=False)
        else:
            try:
                await interaction.response.defer()
            except Exception:
                pass

        await self._cleanup_ephemeral()

    async def _dismiss(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer()
        except Exception:
            pass
        await self._cleanup_ephemeral()

    async def _cleanup_ephemeral(self):
        for msg in (self.draft_msg, self.panel_msg):
            if msg is not None:
                try:
                    await msg.delete()
                except Exception:
                    pass
        if self.orig_interaction is not None:
            try:
                await self.orig_interaction.delete_original_response()
            except Exception:
                pass

    def _make_retone(self, tone: str):
        async def callback(interaction: discord.Interaction):
            bot: TranslatorBot = interaction.client  # type: ignore[assignment]
            await interaction.response.defer(ephemeral=True, thinking=True)
            try:
                result = await bot.translate(self.result.mode, self.original, tone)
            except ProviderError as e:
                if bot.translator.config.active_provider != "ollama" and bot.is_ollama_available():
                    view = FailoverView(bot, self.result.mode, self.original, tone, orig_interaction=interaction)
                    local_model = bot.translator.config.ollama_model or "Local Model"
                    msg = (
                        f"⚠️ **Gemini แปลไม่สำเร็จ** ({str(e).strip().splitlines()[0]})\n"
                        f"-# ตรวจพบ Local Model ({local_model}) ในเครื่องของคุณ กดปุ่มด้านล่างเพื่อแปลทันที:"
                    )
                    fail_msg = await interaction.followup.send(msg, view=view, ephemeral=True, wait=True)
                    view.fail_msg = fail_msg
                    return
                await interaction.followup.send(f"❌ {_clip(str(e))}", ephemeral=True)
                return
            await self._cleanup_ephemeral()
            await _send_draft(interaction, self.original, result)
        return callback



# ---------------------------------------------------------------------------- commands
def register_commands(bot: TranslatorBot) -> None:
    tree = bot.tree

    @tree.context_menu(name="แปลเป็นไทย")
    async def ctx_read(interaction: discord.Interaction, message: discord.Message):
        await _run(interaction, "read", message.content)

    @tree.context_menu(name="อธิบายข้อความนี้")
    async def ctx_explain(interaction: discord.Interaction, message: discord.Message):
        await _run(interaction, "explain", message.content)

    @tree.command(name="en", description="ร่างคำตอบอังกฤษจากไทย + แปลกลับให้เช็ก แล้วก๊อปไปส่งเอง (เห็นเฉพาะคุณ)")
    @app_commands.describe(text="ข้อความไทยที่อยากตอบ", tone="น้ำเสียง")
    @app_commands.choices(tone=TONE_CHOICES)
    async def en(interaction: discord.Interaction, text: str, tone: app_commands.Choice[str] | None = None):
        await _run(interaction, "reply", text, tone.value if tone else None)

    @tree.command(name="th", description="แปลอังกฤษเป็นไทย (เห็นเฉพาะคุณ)")
    @app_commands.describe(text="ข้อความอังกฤษ")
    async def th(interaction: discord.Interaction, text: str):
        await _run(interaction, "read", text)

    @tree.command(name="fix", description="แก้อังกฤษที่พิมพ์เองให้ถูกและเป็นธรรมชาติ (เห็นเฉพาะคุณ)")
    @app_commands.describe(text="ข้อความอังกฤษที่พิมพ์เอง", tone="น้ำเสียง")
    @app_commands.choices(tone=TONE_CHOICES)
    async def fix(interaction: discord.Interaction, text: str, tone: app_commands.Choice[str] | None = None):
        await _run(interaction, "polish", text, tone.value if tone else None)

    @tree.error
    async def on_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
        log.error("command error: %s", error)
        msg = f"❌ {error}"
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)


# ---------------------------------------------------------------------------- entry
def main() -> int:
    cfg = load_config()
    handler = RotatingFileHandler(cfg.data_dir / "discord.log", maxBytes=512_000, backupCount=2, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[handler, logging.StreamHandler()])

    token = cfg.secret("DISCORD_TOKEN")
    if not token:
        print("ยังไม่ได้ใส่ DISCORD_TOKEN ในไฟล์ .env (ดูวิธีใน README.md หัวข้อ Discord)", file=sys.stderr)
        return 2
    bot = TranslatorBot(Translator(cfg))
    try:
        bot.run(token, log_handler=None)
    except discord.LoginFailure:
        print("DISCORD_TOKEN ไม่ถูกต้อง (Reset Token ในหน้า Bot ของ Developer Portal แล้วใส่ใหม่)", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
