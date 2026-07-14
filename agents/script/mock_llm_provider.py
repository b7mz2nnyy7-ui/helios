"""Mock LLM provider for Orion script generation."""

from dataclasses import dataclass

from engine.llm.base_provider import BaseLLMProvider
from engine.llm.models import LLMRequest, LLMResponse


@dataclass
class MockScriptLLMProvider(BaseLLMProvider):
    """Deterministic LLM provider for script generation tests."""

    provider_id: str = "mock"
    model: str = "mock-script-model"

    def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate deterministic script content from the request."""
        content = "\n".join(
            [
                "Title: AI Agents That Actually Save Time",
                (
                    "Hook: Most AI agent content sounds futuristic, but the real "
                    "opportunity is simpler: remove one painful workflow today."
                ),
                (
                    "Section: Problem | Teams are overwhelmed by tools, unclear "
                    "ROI and the pressure to publish consistently."
                ),
                (
                    "Section: Insight | The strongest trend is practical automation "
                    "that turns scattered work into repeatable systems."
                ),
                (
                    "Section: Action | Start with one audience pain point, map the "
                    "workflow and show a concrete before-and-after example."
                ),
                (
                    "CTA: Pick one recurring content task and design the smallest "
                    "AI-assisted workflow around it."
                ),
                (
                    "Summary: A practical script that connects trend evidence, "
                    "audience needs, knowledge and strategy."
                ),
            ],
        )
        return LLMResponse(
            content=content,
            model=self.model,
            provider=self.provider_id,
        )
