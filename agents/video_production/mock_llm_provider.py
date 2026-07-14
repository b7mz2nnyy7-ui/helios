"""Mock LLM provider for Forge video production planning."""

from dataclasses import dataclass

from engine.llm.base_provider import BaseLLMProvider
from engine.llm.models import LLMRequest, LLMResponse


@dataclass
class MockVideoProductionLLMProvider(BaseLLMProvider):
    """Deterministic LLM provider for video production planning tests."""

    provider_id: str = "mock"
    model: str = "mock-video-production-model"

    def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate deterministic production planning guidance."""
        content = "\n".join(
            [
                "Provider: mock-render-provider",
                "TargetPlatform: Short-form vertical video",
                "Summary: Deterministic provider-neutral production plan.",
            ],
        )
        return LLMResponse(
            content=content,
            model=self.model,
            provider=self.provider_id,
        )
