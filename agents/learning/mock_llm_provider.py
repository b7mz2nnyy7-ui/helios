"""Mock LLM provider for Mentor learning reports."""

from dataclasses import dataclass

from engine.llm.base_provider import BaseLLMProvider
from engine.llm.models import LLMRequest, LLMResponse


@dataclass
class MockLearningLLMProvider(BaseLLMProvider):
    """Deterministic LLM provider for learning report tests."""

    provider_id: str = "mock"
    model: str = "mock-learning-model"

    def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate deterministic learning content from the request."""
        content = "\n".join(
            [
                "PerformanceSummary: Strong early traction with clear platform variance.",
                (
                    "Strength: Retention | Average watch percentage is strongest "
                    "on the leading platform. | Strongest platform and watch data "
                    "support the format. | Reuse the opening structure. | 0.86"
                ),
                (
                    "Weakness: Engagement Depth | Saves and shares lag behind "
                    "views on the weaker platform. | Weakest platform has lower "
                    "engagement rate. | Add a more explicit save-worthy checklist. | 0.79"
                ),
                "Experiment: Test a checklist CTA against a question-led CTA.",
                "Experiment: Recut the first three seconds with a sharper contrast.",
                "Action: Keep the current hook structure for the next variant.",
                "Action: Add a clear save/share prompt near the final third.",
            ],
        )
        return LLMResponse(
            content=content,
            model=self.model,
            provider=self.provider_id,
        )
