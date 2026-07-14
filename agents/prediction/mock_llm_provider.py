"""Mock LLM provider for Oracle predictions."""

from dataclasses import dataclass

from engine.llm.base_provider import BaseLLMProvider
from engine.llm.models import LLMRequest, LLMResponse


@dataclass
class MockPredictionLLMProvider(BaseLLMProvider):
    """Deterministic LLM provider for prediction report tests."""

    provider_id: str = "mock"
    model: str = "mock-prediction-model"

    def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate deterministic prediction content from the request."""
        content = "\n".join(
            [
                (
                    "Prediction: Checklist CTA Lift | 0.82 | Repeated learnings "
                    "favor save-worthy checklists. | Prioritize a checklist-led "
                    "variant in the next content batch."
                ),
                (
                    "Prediction: Hook Contrast Improvement | 0.76 | Performance "
                    "summaries point to stronger retention when contrast appears "
                    "early. | Test a sharper first-three-second contrast."
                ),
                (
                    "Prediction: Platform-Specific Recut Gain | 0.68 | Weaknesses "
                    "show engagement variance by platform. | Recut pacing for the "
                    "weakest platform before changing the idea."
                ),
                (
                    "Summary: Deterministic forecast based on accumulated learning "
                    "reports and recommended experiments."
                ),
            ],
        )
        return LLMResponse(
            content=content,
            model=self.model,
            provider=self.provider_id,
        )
