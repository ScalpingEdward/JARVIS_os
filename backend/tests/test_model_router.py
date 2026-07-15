import pytest

from app.models.contracts import ModelRequest
from app.models.router import ModelRouter, UnknownProviderError


def test_router_lists_mock_provider() -> None:
    router = ModelRouter()
    assert router.available_providers() == ["mock"]


def test_router_generates_with_mock_provider() -> None:
    router = ModelRouter()
    response = router.generate(ModelRequest(prompt="Hello", task_type="chat"))

    assert response.provider == "mock"
    assert response.model == "jarvis-mock-v1"
    assert response.content == "Mock response for chat: Hello"


def test_router_rejects_unknown_provider() -> None:
    router = ModelRouter()

    with pytest.raises(UnknownProviderError):
        router.generate(ModelRequest(prompt="Hello"), provider_name="unknown")
