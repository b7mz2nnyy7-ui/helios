"""Mock LLM provider for Vox voice profile generation."""

from dataclasses import dataclass

from engine.llm.base_provider import BaseLLMProvider
from engine.llm.models import LLMRequest, LLMResponse


@dataclass
class MockVoiceLLMProvider(BaseLLMProvider):
    """Deterministic LLM provider for voice profile tests."""

    provider_id: str = "mock"
    model: str = "mock-voice-model"

    def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate deterministic voice profile content from the request."""
        content = "\n".join(
            [
                "Language: de",
                "VoiceCharacter: Calm strategic narrator with practical authority",
                "SpeakingStyle: Clear, concise and slightly energetic",
                "EmotionalTone: Focused, empowering and grounded",
                "PaceWPM: 145",
                "Pitch: Medium, warm and stable",
                "EmphasisNotes: Emphasize workflow, fastest AI win and one repeatable task",
                "PronunciationNotes: Keep AI terms crisp and avoid over-dramatic delivery",
                "MultilingualNotes: Preserve English product terms when common in German content",
                "PlatformFit: Short-form vertical narration with strong first-second clarity",
                (
                    "Summary: Deterministic voice profile based on the script, "
                    "avatar and creative direction."
                ),
            ],
        )
        return LLMResponse(
            content=content,
            model=self.model,
            provider=self.provider_id,
        )
