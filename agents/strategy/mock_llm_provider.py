"""Mock LLM provider for Nova strategy generation."""

from dataclasses import dataclass

from engine.llm.base_provider import BaseLLMProvider
from engine.llm.models import LLMRequest, LLMResponse


@dataclass
class MockStrategyLLMProvider(BaseLLMProvider):
    """Deterministic LLM provider for strategy tests."""

    provider_id: str = "mock"
    model: str = "mock-strategy-model"

    def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate deterministic strategy content from the request."""
        content = "\n".join(
            [
                f"Summary: Mock content strategy based on: {request.user_prompt}",
                (
                    "Idea: Explainer Sprint | Educational breakdown | "
                    "YouTube | Turns the strongest trend into a searchable asset."
                ),
                (
                    "Idea: Founder POV | Opinion-led narrative | "
                    "LinkedIn | Converts trend evidence into executive relevance."
                ),
                (
                    "Idea: Short Myth Bust | Fast misconception hook | "
                    "TikTok | Creates a compact shareable angle from the trend."
                ),
                (
                    "Idea: Workflow Demo | Practical implementation | "
                    "Instagram Reels | Shows the trend as a repeatable workflow."
                ),
                (
                    "Idea: Data Story | Performance-led insight | "
                    "X | Makes the trend easy to discuss and compare."
                ),
            ],
        )
        return LLMResponse(
            content=content,
            model=self.model,
            provider=self.provider_id,
        )

