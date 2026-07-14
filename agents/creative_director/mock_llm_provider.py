"""Mock LLM provider for Aether creative direction."""

from dataclasses import dataclass

from engine.llm.base_provider import BaseLLMProvider
from engine.llm.models import LLMRequest, LLMResponse


@dataclass
class MockCreativeLLMProvider(BaseLLMProvider):
    """Deterministic LLM provider for creative direction tests."""

    provider_id: str = "mock"
    model: str = "mock-creative-model"

    def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate deterministic creative brief content from the request."""
        content = "\n".join(
            [
                "VisualStyle: Clean kinetic tech editorial",
                "ColorPalette: Deep charcoal, electric cyan, soft white",
                "Typography: Bold grotesk headlines with compact caption text",
                "CameraStyle: Fast push-ins, locked-off explainers and UI closeups",
                "LightingStyle: High-contrast desk light with crisp screen glow",
                "AnimationStyle: Minimal motion graphics, node lines and checklist reveals",
                "AvatarStyle: Confident operator, practical and calm",
                "EditingStyle: Tight cuts, match cuts and caption-led pacing",
                "MusicStyle: Modern pulse, restrained percussion and light synth",
                "EmotionalTone: Clear, focused and empowering",
                "PlatformStyle: Short-form vertical video optimized for retention",
                "BrandingNotes: Use practical proof, avoid hype and keep every visual useful",
                (
                    "Summary: Deterministic creative brief connecting storyboard, "
                    "strategy and audience needs."
                ),
            ],
        )
        return LLMResponse(
            content=content,
            model=self.model,
            provider=self.provider_id,
        )
