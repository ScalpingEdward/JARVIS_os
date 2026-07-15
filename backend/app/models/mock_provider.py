from .contracts import ModelProvider, ModelRequest, ModelResponse


class MockModelProvider(ModelProvider):
    """Deterministic local provider used until paid APIs are configured."""

    name = "mock"

    def generate(self, request: ModelRequest) -> ModelResponse:
        normalized = request.prompt.strip()
        return ModelResponse(
            provider=self.name,
            model="jarvis-mock-v1",
            content=f"Mock response for {request.task_type}: {normalized}",
        )
