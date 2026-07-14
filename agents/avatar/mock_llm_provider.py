"""Mock LLM provider for Echo avatar definition."""

from dataclasses import dataclass

from engine.llm.base_provider import BaseLLMProvider
from engine.llm.models import LLMRequest, LLMResponse


@dataclass
class MockAvatarLLMProvider(BaseLLMProvider):
    """Deterministic LLM provider for avatar definition tests."""

    provider_id: str = "mock"
    model: str = "mock-avatar-model"

    def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate deterministic avatar profile content from the request."""
        content = "\n".join(
            [
                "Name: Echo",
                "AgeGroup: 28-35",
                "Appearance: Approachable tech strategist with clean visual presence",
                "ClothingStyle: Minimal dark jacket, neutral shirt and subtle cyan accent",
                "Hairstyle: Neat modern styling with low visual distraction",
                "FacialExpression: Focused, calm and lightly optimistic",
                "BodyLanguage: Open posture, deliberate hand gestures and steady pacing",
                "VoiceStyle: Clear, grounded and practical with confident emphasis",
                "EnergyLevel: Medium-high, composed and precise",
                "PlatformFit: Short-form vertical explainers for YouTube, LinkedIn and TikTok",
                "BrandingNotes: Match the clean kinetic tech editorial style without hype",
                (
                    "Summary: Deterministic avatar profile based on the creative "
                    "brief and audience needs."
                ),
            ],
        )
        return LLMResponse(
            content=content,
            model=self.model,
            provider=self.provider_id,
        )
