"""Mock LLM provider for Pulse music and sound concepts."""

from dataclasses import dataclass

from engine.llm.base_provider import BaseLLMProvider
from engine.llm.models import LLMRequest, LLMResponse


@dataclass
class MockMusicLLMProvider(BaseLLMProvider):
    """Deterministic LLM provider for music profile tests."""

    provider_id: str = "mock"
    model: str = "mock-music-model"

    def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate deterministic music profile content from the request."""
        content = "\n".join(
            [
                "Genre: Minimal electronic pulse",
                "Mood: Focused, modern and practical",
                "EnergyLevel: Medium-high with restrained momentum",
                "TempoBPM: 118",
                "TransitionStyle: Tight whooshes, match-cut hits and soft risers",
                "SoundEffectStyle: Clean UI taps, subtle clicks and light digital swells",
                "IntroStyle: Immediate beat with a short attention accent",
                "OutroStyle: Clean resolve with a concise sonic button",
                "PlatformFit: Short-form vertical videos with fast retention pacing",
                "CopyrightStrategy: Use original, licensed or royalty-safe production music",
                (
                    "Summary: Deterministic music concept based on the creative "
                    "brief, audience profile and script."
                ),
            ],
        )
        return LLMResponse(
            content=content,
            model=self.model,
            provider=self.provider_id,
        )
