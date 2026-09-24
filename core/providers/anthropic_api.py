"""ตัวเชื่อม Claude API โดยตรง (ใช้เครดิต API ไม่ใช่โควต้าสมาชิก)

ต้อง pip install anthropic และใส่ ANTHROPIC_API_KEY ใน .env
"""
from __future__ import annotations

from core.config import MODEL_ALIASES
from core.providers.base import Provider, ProviderError

_FALLBACK_BETA = "server-side-fallback-2026-06-01"
_FALLBACK_MODEL = "claude-opus-4-8"


class AnthropicProvider(Provider):
    name = "anthropic"

    def __init__(self, config):
        super().__init__(config)
        self.api_key = config.secret("ANTHROPIC_API_KEY")
        self._client = None

    def available(self) -> bool:
        return bool(self.api_key)

    def _get_client(self):
        if self._client is None:
            try:
                import anthropic
            except ImportError as e:
                raise ProviderError("ยังไม่ได้ติดตั้งไลบรารี anthropic (pip install anthropic)") from e
            self._client = anthropic.Anthropic(api_key=self.api_key, timeout=self.config.timeout, max_retries=1)
        return self._client

    def complete(self, system: str, user: str, model_alias: str) -> str:
        if not self.api_key:
            raise ProviderError("ยังไม่ได้ใส่ ANTHROPIC_API_KEY ในไฟล์ .env")
        import anthropic

        client = self._get_client()
        model = str(self.cfg.get("model") or MODEL_ALIASES.get(model_alias, model_alias))
        kwargs = dict(
            model=model,
            max_tokens=4096,
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user}],
        )
        try:
            if model.startswith(("claude-opus-5", "claude-fable")):
                # รุ่นใหญ่มีตัวกรองความปลอดภัย ถ้าปฏิเสธให้เซิร์ฟเวอร์สลับไปรุ่นสำรองในคำขอเดียวกัน
                response = client.beta.messages.create(
                    betas=[_FALLBACK_BETA], fallbacks=[{"model": _FALLBACK_MODEL}], **kwargs
                )
            else:
                response = client.messages.create(**kwargs)
        except anthropic.AuthenticationError as e:
            raise ProviderError("ANTHROPIC_API_KEY ไม่ถูกต้อง") from e
        except anthropic.RateLimitError as e:
            raise ProviderError("Claude API ติด rate limit หรือเครดิตหมด") from e
        except anthropic.APIStatusError as e:
            raise ProviderError(f"Claude API ตอบ HTTP {e.status_code}: {e.message}") from e
        except anthropic.APIConnectionError as e:
            raise ProviderError(f"ติดต่อ Claude API ไม่ได้: {e}") from e

        if response.stop_reason == "refusal":
            raise ProviderError("Claude API ปฏิเสธคำขอนี้")
        text = "".join(b.text for b in response.content if b.type == "text").strip()
        if not text:
            raise ProviderError("Claude API ส่งข้อความว่างกลับมา")
        return text
