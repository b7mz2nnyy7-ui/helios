"""Base abstraction for LLM providers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from engine.llm.models import LLMRequest, LLMResponse


@dataclass
class BaseLLMProvider(ABC):
    """Abstract base class for provider-specific LLM integrations."""

    provider_id: str
    model: str

    @abstractmethod
    def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate an LLM response for a request."""
