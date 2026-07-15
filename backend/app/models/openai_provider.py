from __future__ import annotations

from typing import Any

from .contracts import ModelProvider, ModelRequest, ModelResponse


class OpenAIModelProvider(ModelProvider):
    name = "openai"

    def __init__(self, api_key: str, model: str, client: Any | None = None) -> None:
        if not api_key:
            raise ValueError("OpenAI API key is required")
        self._model = model
        if client is None:
            from openai import OpenAI

            client = OpenAI(api_key=api_key)
        self._client = client

    def generate(self, request: ModelRequest) -> ModelResponse:
        response = self._client.responses.create(model=self._model, input=request.prompt)
        return ModelResponse(
            provider=self.name,
            model=self._model,
            content=response.output_text.strip(),
        )
