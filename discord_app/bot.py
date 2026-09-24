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

from core.config import load_config
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
        # ให้ทุกคำสั่งติดตั้งได้ทั้งแบบ user และ guild และใช้ได้ทั้งใน guild, DM, group DM
        self.tree = app_commands.CommandTree(
            self,
            allowed_installs=app_commands.AppInstallationType(guild=True, user=True),
            allowed_contexts=app_commands.AppCommandContext(guild=True, dm_channel=True, private_channel=True),
        )
        register_commands(self)

    async def setup_hook(self) -> None:
        synced = await self.tree.sync()
        log.info("synced %d commands: %s", len(synced), ", ".join(c.name for c in synced))

    async def on_ready(self) -> None:
        log.info("logged in as %s (id=%s)", self.user, self.user.id if self.user else "?")

    async def translate(self, mode: str, text: str, tone: str | None = None) -> Result:
        return await asyncio.to_thread(self.translator.run, mode, text, tone)


# ---------------------------------------------------------------------------- helpers
def _clip(text: str) -> str:
    return text if len(text) <= MAX_LEN else text[: MAX_LEN - 3] + "..."


def _format(result: Result) -> str:
    footer = f"-# {MODE_LABELS.get(result.mode, result.mode)} · {result.provider}/{result.model} · {result.seconds:.1f}s"
    if result.mode in ("reply", "polish"):
        footer += f" · {TONE_LABELS.get(result.tone, result.tone)}"
    if result.fallback_used:
        footer += " · ตัวสำรอง"
    return _clip(result.text) + "\n" + footer


async def _send_draft(interaction: discord.Interaction, original: str, result: Result) -> None:
    """โหมดตอบ/ขัดเกลา: ส่ง 2 ข้อความ (เห็นเฉพาะคุณ)
    1) อังกฤษล้วนๆ เพื่อก๊อปไปวางในช่องพิมพ์แล้วส่งในชื่อคุณเอง
    2) แปลกลับเป็นไทยให้เช็กความหมาย + ปุ่มเปลี่ยนน้ำเสียง
    """
    bot: TranslatorBot = interaction.client  # type: ignore[assignment]
    await interaction.followup.send(_clip(result.text), ephemeral=True)
    check = ""
    if bot.translator.config.auto_back_translate:
        try:
            back = await bot.translate("read", result.text)
            check = "🔁 **ลูกค้าจะอ่านว่า:** " + _clip(back.text)
        except ProviderError as e:
            check = f"(แปลกลับไม่สำเร็จ: {_clip(str(e))})"
    footer = (f"-# ⬆ ก๊อปข้อความด้านบนไปวางในช่องพิมพ์แล้วกด Enter ด้วยตัวเอง จะขึ้นเป็นชื่อคุณ · "
              f"{result.provider}/{result.model} · {result.seconds:.1f}s · {TONE_LABELS.get(result.tone, result.tone)}")
    content = (check + "\n" if check else "") + footer
    await interaction.followup.send(content, view=ReplyView(original, result), ephemeral=True)


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
    """ปุ่มใต้ร่างคำตอบ: เปลี่ยนน้ำเสียงแล้วแปลใหม่ (ไม่มีปุ่มโพสต์ เพราะข้อความต้องส่งในชื่อคุณเอง)"""

    def __init__(self, original: str, result: Result):
        super().__init__(timeout=900)
        self.original = original
        self.result = result
        for tone, label in TONE_LABELS.items():
            btn = discord.ui.Button(label=f"แปลใหม่แบบ{label}", style=discord.ButtonStyle.secondary,
                                    disabled=(tone == result.tone))
            btn.callback = self._make_retone(tone)
            self.add_item(btn)

    def _make_retone(self, tone: str):
        async def callback(interaction: discord.Interaction):
            bot: TranslatorBot = interaction.client  # type: ignore[assignment]
            await interaction.response.defer(ephemeral=True, thinking=True)
            try:
                result = await bot.translate(self.result.mode, self.original, tone)
            except ProviderError as e:
                await interaction.followup.send(f"❌ {_clip(str(e))}", ephemeral=True)
                return
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
