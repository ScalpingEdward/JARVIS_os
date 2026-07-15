from app.config import get_settings

from .contracts import ModelProvider, ModelRequest, ModelResponse
from .provider_loader import load_providers


class UnknownProviderError(ValueError):
    pass


class ModelRouter:
    """Selects a registered model provider without coupling callers to vendors."""

    def __init__(self, providers: list[ModelProvider] | None = None) -> None:
        configured = providers if providers is not None else load_providers(get_settings())
        self._providers = {provider.name: provider for provider in configured}

    def available_providers(self) -> list[str]:
        return sorted(self._providers)

    def generate(self, request: ModelRequest, provider_name: str = "mock") -> ModelResponse:
        try:
            provider = self._providers[provider_name]
        except KeyError as exc:
            raise UnknownProviderError(
                f"Unknown model provider: {provider_name}"
            ) from exc
        return provider.generate(request)


model_router = ModelRouter()
