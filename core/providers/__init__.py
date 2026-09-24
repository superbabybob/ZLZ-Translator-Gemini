from core.providers.base import Provider, ProviderError
from core.providers.gemini import GeminiProvider
from core.providers.ollama import OllamaProvider

PROVIDERS: dict[str, type[Provider]] = {
    GeminiProvider.name: GeminiProvider,
    OllamaProvider.name: OllamaProvider,
}

__all__ = ["PROVIDERS", "Provider", "ProviderError", "GeminiProvider", "OllamaProvider"]

