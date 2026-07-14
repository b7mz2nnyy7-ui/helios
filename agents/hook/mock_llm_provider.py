"""Mock LLM provider for Apollo hook optimization."""

from dataclasses import dataclass

from engine.llm.base_provider import BaseLLMProvider
from engine.llm.models import LLMRequest, LLMResponse


@dataclass
class MockHookLLMProvider(BaseLLMProvider):
    """Deterministic LLM provider for hook optimization tests."""

    provider_id: str = "mock"
    model: str = "mock-hook-model"

    def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate deterministic hook candidates from the request."""
        content = "\n".join(
            [
                "Summary: Deterministic hook optimization based on the script.",
                (
                    "Hook: Stop wasting hours on AI tools that do not change your "
                    "workflow. | 0.74 | Clear pain contrast."
                ),
                (
                    "Hook: Most AI agent advice skips the only part that matters: "
                    "the workflow. | 0.88 | Strong contrarian framing."
                ),
                (
                    "Hook: Your next AI agent should replace one repeatable task, "
                    "not your whole team. | 0.93 | Specific and practical promise."
                ),
                (
                    "Hook: If AI agents feel overwhelming, start with one boring "
                    "process. | 0.81 | Reduces complexity quickly."
                ),
                (
                    "Hook: The best AI agent strategy begins before you open a new "
                    "tool. | 0.79 | Creates curiosity."
                ),
                (
                    "Hook: Everyone talks about autonomous agents. Few talk about "
                    "the work they should remove. | 0.86 | Sharp market critique."
                ),
                (
                    "Hook: Build one AI workflow your team will actually use this "
                    "week. | 0.91 | Immediate actionable promise."
                ),
                (
                    "Hook: The fastest AI win is not a chatbot. It is a workflow "
                    "you stop repeating. | 0.95 | Highest clarity and novelty."
                ),
                (
                    "Hook: AI agents become useful when they attack a specific "
                    "bottleneck. | 0.84 | Practical problem framing."
                ),
                (
                    "Hook: Before buying another AI tool, name the task it will "
                    "delete. | 0.9 | Strong decision trigger."
                ),
            ],
        )
        return LLMResponse(
            content=content,
            model=self.model,
            provider=self.provider_id,
        )
