from core.providers.base import Provider, ProviderError
from core.providers.gemini import GeminiProvider

PROVIDERS: dict[str, type[Provider]] = {
    GeminiProvider.name: GeminiProvider,
}

__all__ = ["PROVIDERS", "Provider", "ProviderError"]
