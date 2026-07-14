"""Mock provider for Sage knowledge retrieval."""

from dataclasses import dataclass

from agents.knowledge.models import KnowledgeCategory, KnowledgeItem
from engine.llm.base_provider import BaseLLMProvider
from engine.llm.models import LLMRequest, LLMResponse


@dataclass
class MockKnowledgeProvider(BaseLLMProvider):
    """Deterministic provider for knowledge agent tests."""

    provider_id: str = "mock"
    model: str = "mock-knowledge-model"

    def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate deterministic knowledge content from the request."""
        content = "\n".join(
            [
                f"Summary: Mock knowledge response based on: {request.user_prompt}",
                (
                    "Item: Audience Promise | MARKETING | Clarify the audience "
                    "promise before choosing formats. | internal:marketing | 0.91"
                ),
                (
                    "Item: Narrative Tension | STORYTELLING | Strong content "
                    "contrasts current pain with a believable better state. | "
                    "internal:storytelling | 0.88"
                ),
                (
                    "Item: Specificity Bias | PSYCHOLOGY | Concrete examples "
                    "usually outperform broad claims. | internal:psychology | 0.84"
                ),
                (
                    "Item: Hook Clarity | COPYWRITING | The first line should "
                    "state a problem, promise or sharp contrast. | internal:copy | "
                    "0.86"
                ),
                (
                    "Item: Platform Fit | SOCIAL_MEDIA | Adapt depth, pacing and "
                    "format to the platform context. | internal:social | 0.83"
                ),
            ],
        )
        return LLMResponse(
            content=content,
            model=self.model,
            provider=self.provider_id,
        )

    def search(self, request: LLMRequest) -> list[KnowledgeItem]:
        """Return deterministic knowledge items for the request."""
        response = self.generate(request)
        items: list[KnowledgeItem] = []
        for line in response.content.splitlines():
            if not line.startswith("Item: "):
                continue

            parts = [part.strip() for part in line.removeprefix("Item: ").split("|")]
            if len(parts) != 5:
                msg = "Knowledge item lines must contain five fields."
                raise ValueError(msg)

            items.append(
                KnowledgeItem(
                    title=parts[0],
                    category=KnowledgeCategory(parts[1]),
                    content=parts[2],
                    source=parts[3],
                    confidence=float(parts[4]),
                ),
            )

        return items
