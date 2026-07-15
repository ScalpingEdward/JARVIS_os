from __future__ import annotations

from typing import Any

from .contracts import ModelProvider, ModelRequest, ModelResponse


class AnthropicModelProvider(ModelProvider):
    name = "anthropic"

    def __init__(self, api_key: str, model: str, max_tokens: int = 1024, client: Any | None = None) -> None:
        if not api_key:
            raise ValueError("Anthropic API key is required")
        self._model = model
        self._max_tokens = max_tokens
        if client is None:
            from anthropic import Anthropic

            client = Anthropic(api_key=api_key)
        self._client = client

    def generate(self, request: ModelRequest) -> ModelResponse:
        message = self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            messages=[{"role": "user", "content": request.prompt}],
        )
        text = "".join(
            block.text for block in message.content if getattr(block, "type", None) == "text"
        ).strip()
        return ModelResponse(provider=self.name, model=self._model, content=text)
