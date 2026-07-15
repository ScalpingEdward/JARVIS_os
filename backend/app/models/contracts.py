from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ModelRequest:
    prompt: str
    task_type: str = "general"


@dataclass(frozen=True, slots=True)
class ModelResponse:
    provider: str
    model: str
    content: str


class ModelProvider(ABC):
    """Provider-neutral contract implemented by every model backend."""

    name: str

    @abstractmethod
    def generate(self, request: ModelRequest) -> ModelResponse:
        """Generate one response without exposing provider-specific details."""
