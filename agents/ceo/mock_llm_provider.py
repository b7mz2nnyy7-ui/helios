"""Mock LLM provider for Helios CEO decision reports."""

from dataclasses import dataclass

from engine.llm.base_provider import BaseLLMProvider
from engine.llm.models import LLMRequest, LLMResponse


@dataclass
class MockCEOLLMProvider(BaseLLMProvider):
    """Deterministic LLM provider for CEO foundation tests."""

    provider_id: str = "mock"
    model: str = "mock-ceo-model"

    def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate deterministic CEO decision content."""
        content = "\n".join(
            [
                "CompanyStatus: Focused growth mode with controlled execution risk",
                (
                    "Priority: Scale Checklist CTA Experiment | Business "
                    "intelligence shows the strongest opportunity is checklist-led "
                    "growth. | 0.9"
                ),
                (
                    "Decision: Approve next content batch around checklist CTA | "
                    "Athena reports clear upside and manageable platform risk. | "
                    "Higher save/share rate and clearer portfolio signal. | 0.84"
                ),
                (
                    "ExecutiveSummary: Helios recommends focused execution on the "
                    "Checklist CTA Lift opportunity while monitoring platform "
                    "engagement risk."
                ),
            ],
        )
        return LLMResponse(
            content=content,
            model=self.model,
            provider=self.provider_id,
        )
