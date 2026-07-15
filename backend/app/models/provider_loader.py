from __future__ import annotations

from app.config import Settings

from .anthropic_provider import AnthropicModelProvider
from .contracts import ModelProvider
from .mock_provider import MockModelProvider
from .openai_provider import OpenAIModelProvider


def load_providers(settings: Settings) -> list[ModelProvider]:
    providers: list[ModelProvider] = [MockModelProvider()]

    if settings.anthropic_enabled:
        if not settings.anthropic_api_key:
            raise ValueError("JARVIS_ANTHROPIC_API_KEY is required when Anthropic is enabled")
        providers.append(
            AnthropicModelProvider(
                api_key=settings.anthropic_api_key,
                model=settings.anthropic_model,
            )
        )

    if settings.openai_enabled:
        if not settings.openai_api_key:
            raise ValueError("JARVIS_OPENAI_API_KEY is required when OpenAI is enabled")
        providers.append(
            OpenAIModelProvider(
                api_key=settings.openai_api_key,
                model=settings.openai_model,
            )
        )

    return providers
