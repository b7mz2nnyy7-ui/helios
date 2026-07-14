"""Mock LLM provider for Lumen storyboard generation."""

from dataclasses import dataclass

from engine.llm.base_provider import BaseLLMProvider
from engine.llm.models import LLMRequest, LLMResponse


@dataclass
class MockStoryboardLLMProvider(BaseLLMProvider):
    """Deterministic LLM provider for storyboard generation tests."""

    provider_id: str = "mock"
    model: str = "mock-storyboard-model"

    def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate deterministic storyboard content from the request."""
        content = "\n".join(
            [
                "Title: AI Agents Workflow Storyboard",
                "Style: Clean kinetic captions with practical product visuals",
                (
                    "Summary: A concise storyboard that turns the optimized hook "
                    "and script into a 30-second short-form video."
                ),
                (
                    "Scene: 1 | 6.0 | Open with the selected hook and name the "
                    "workflow pain. | Creator at desk surrounded by tool tabs. | "
                    "Fast push-in to laptop screen. | Stop repeating this task | "
                    "Smash cut"
                ),
                (
                    "Scene: 2 | 8.0 | Show the repeated task before automation. | "
                    "Split screen of manual copying, planning and publishing. | "
                    "Side-by-side tracking shot. | The old workflow | Match cut"
                ),
                (
                    "Scene: 3 | 8.0 | Introduce the AI workflow as a small system. | "
                    "Simple node diagram connecting inputs, script and output. | "
                    "Slow zoom on the system map. | Build one useful loop | Swipe"
                ),
                (
                    "Scene: 4 | 8.0 | End with the call to action from the script. | "
                    "Checklist with one recurring content task highlighted. | "
                    "Locked-off shot with caption emphasis. | Pick one task today | "
                    "Fade out"
                ),
            ],
        )
        return LLMResponse(
            content=content,
            model=self.model,
            provider=self.provider_id,
        )
