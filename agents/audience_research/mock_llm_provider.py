"""Mock LLM provider for Mira audience research."""

from dataclasses import dataclass

from engine.llm.base_provider import BaseLLMProvider
from engine.llm.models import LLMRequest, LLMResponse


@dataclass
class MockAudienceLLMProvider(BaseLLMProvider):
    """Deterministic LLM provider for audience research tests."""

    provider_id: str = "mock"
    model: str = "mock-audience-model"

    def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate deterministic audience research content from the request."""
        content = "\n".join(
            [
                f"Summary: Mock audience profile based on: {request.user_prompt}",
                "Interest: Automation workflows",
                "Interest: Practical AI tools",
                "Interest: Creator productivity",
                "PainPoint: Tool overload | 0.82 | Frustration",
                "PainPoint: Unclear ROI | 0.76 | Uncertainty",
                "PainPoint: Content consistency | 0.69 | Pressure",
                "Tone: Clear, practical and evidence-led",
                "Platform: YouTube",
                "Platform: LinkedIn",
                "Platform: TikTok",
            ],
        )
        return LLMResponse(
            content=content,
            model=self.model,
            provider=self.provider_id,
        )
