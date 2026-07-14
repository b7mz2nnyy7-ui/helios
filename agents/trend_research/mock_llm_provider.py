"""Mock LLM provider for Atlas trend research."""

from dataclasses import dataclass

from engine.llm.base_provider import BaseLLMProvider
from engine.llm.models import LLMRequest, LLMResponse


@dataclass
class MockLLMProvider(BaseLLMProvider):
    """Deterministic LLM provider for trend summary tests."""

    provider_id: str = "mock"
    model: str = "mock-trend-model"

    def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate a deterministic response from the request."""
        return LLMResponse(
            content=f"Mock trend summary based on: {request.user_prompt}",
            model=self.model,
            provider=self.provider_id,
        )
