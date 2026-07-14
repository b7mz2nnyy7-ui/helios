"""Mock LLM provider for Athena business intelligence reports."""

from dataclasses import dataclass

from engine.llm.base_provider import BaseLLMProvider
from engine.llm.models import LLMRequest, LLMResponse


@dataclass
class MockBusinessLLMProvider(BaseLLMProvider):
    """Deterministic LLM provider for business intelligence tests."""

    provider_id: str = "mock"
    model: str = "mock-business-model"

    def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate deterministic business intelligence content."""
        content = "\n".join(
            [
                "KPI: Total Views | 1750 | Current portfolio-level demand signal.",
                "KPI: Total Engagement | 396 | Combined active audience response.",
                (
                    "Opportunity: Checklist CTA Lift | 0.82 | High near-term "
                    "growth upside | Prioritize checklist-led variants."
                ),
                (
                    "Risk: Platform Engagement Gap | MEDIUM | Recut weak-platform "
                    "pacing before scaling spend."
                ),
                "Priority: Launch the checklist CTA experiment first.",
                "Priority: Monitor retention and saves before expanding formats.",
                (
                    "ExecutiveSummary: Athena recommends prioritizing Checklist "
                    "CTA Lift because it is the strongest prediction and aligns "
                    "with current analytics and learnings."
                ),
            ],
        )
        return LLMResponse(
            content=content,
            model=self.model,
            provider=self.provider_id,
        )
