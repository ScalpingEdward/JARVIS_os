from types import SimpleNamespace

import pytest

from app.config import Settings
from app.models.anthropic_provider import AnthropicModelProvider
from app.models.contracts import ModelRequest
from app.models.openai_provider import OpenAIModelProvider
from app.models.provider_loader import load_providers


class FakeAnthropicMessages:
    def create(self, **kwargs):
        assert kwargs["messages"][0]["content"] == "hello"
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text="anthropic reply")]
        )


class FakeOpenAIResponses:
    def create(self, **kwargs):
        assert kwargs["input"] == "hello"
        return SimpleNamespace(output_text="openai reply")


def test_anthropic_adapter_maps_response() -> None:
    client = SimpleNamespace(messages=FakeAnthropicMessages())
    provider = AnthropicModelProvider("key", "claude-test", client=client)

    response = provider.generate(ModelRequest(prompt="hello"))

    assert response.provider == "anthropic"
    assert response.model == "claude-test"
    assert response.content == "anthropic reply"


def test_openai_adapter_maps_response() -> None:
    client = SimpleNamespace(responses=FakeOpenAIResponses())
    provider = OpenAIModelProvider("key", "gpt-test", client=client)

    response = provider.generate(ModelRequest(prompt="hello"))

    assert response.provider == "openai"
    assert response.model == "gpt-test"
    assert response.content == "openai reply"


def test_loader_keeps_external_providers_disabled_by_default() -> None:
    providers = load_providers(Settings())
    assert [provider.name for provider in providers] == ["mock"]


def test_loader_rejects_enabled_provider_without_key() -> None:
    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        load_providers(Settings(anthropic_enabled=True))

    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        load_providers(Settings(openai_enabled=True))
