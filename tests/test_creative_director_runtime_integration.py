"""Runtime integration tests for Aether creative director agent."""

import unittest

from agents.audience_research.models import AudiencePainPoint, AudienceProfile
from agents.creative_director.agent import CreativeDirectorAgent
from agents.creative_director.models import CreativeBrief
from agents.storyboard.models import Storyboard, StoryboardScene
from agents.strategy.models import ContentIdea, ContentStrategy
from engine.runtime.capability import AgentCapability
from engine.runtime.runtime import HeliosRuntime
from engine.tasks.priority import TaskPriority
from engine.tasks.status import TaskStatus
from engine.tasks.task import Task


def create_creative_task(payload: dict[str, object] | None = None) -> Task:
    """Create a creative direction task for runtime integration tests."""
    task_payload = {
        "storyboard": Storyboard(
            title="AI Agents Workflow Storyboard",
            selected_hook="The fastest AI win is a workflow you stop repeating.",
            scenes=[
                StoryboardScene(
                    1,
                    6.0,
                    "Open with the hook.",
                    "Creator at desk surrounded by tool tabs.",
                    "Fast push-in.",
                    "Stop repeating this task",
                    "Smash cut",
                ),
                StoryboardScene(
                    2,
                    8.0,
                    "Show manual work.",
                    "Split screen of planning and publishing.",
                    "Side-by-side tracking shot.",
                    "The old workflow",
                    "Match cut",
                ),
                StoryboardScene(
                    3,
                    8.0,
                    "Introduce the system.",
                    "Node diagram connecting inputs and output.",
                    "Slow zoom.",
                    "Build one useful loop",
                    "Swipe",
                ),
            ],
            visual_style="Clean kinetic captions",
            summary="Storyboard for practical AI workflow content.",
            generated_by="mock:mock-storyboard-model",
        ),
        "content_strategy": ContentStrategy(
            query="AI Agents",
            summary="Make practical AI workflows easy to understand.",
            ideas=[
                ContentIdea(
                    "Workflow Demo",
                    "Practical implementation",
                    "YouTube",
                    "Shows repeatable workflows.",
                ),
            ],
            generated_by="mock:mock-strategy-model",
        ),
        "audience_profile": AudienceProfile(
            topic="AI Agents",
            target_age_range="18-34",
            language="de",
            interests=["Automation"],
            pain_points=[AudiencePainPoint("Tool overload", 0.82, "Frustration")],
            preferred_tone="Clear",
            preferred_platforms=["YouTube"],
            summary="Creators want practical workflows.",
            generated_by="mock:mock-audience-model",
        ),
    }
    return Task(
        task_id="creative-task-1",
        title="Creative Direction",
        description="Create a creative production brief.",
        priority=TaskPriority.MEDIUM,
        required_capability=AgentCapability.CREATIVE_DIRECTION,
        payload=task_payload if payload is None else payload,
    )


class CreativeDirectorRuntimeIntegrationTestCase(unittest.TestCase):
    """Integration tests for Aether through HeliosRuntime."""

    def test_runtime_dispatches_creative_task_to_aether(self) -> None:
        """Runtime can dispatch CREATIVE_DIRECTION tasks to Aether."""
        runtime = HeliosRuntime()
        aether = CreativeDirectorAgent()
        task = create_creative_task()
        runtime.register(aether)

        result = runtime.submit_task(task)

        self.assertIsInstance(result, CreativeBrief)
        self.assertIs(result, task.result)
        self.assertIs(task.status, TaskStatus.COMPLETED)
        self.assertIs(aether.last_brief, result)

    def test_runtime_returns_creative_brief(self) -> None:
        """Runtime returns the CreativeBrief from Aether."""
        runtime = HeliosRuntime()
        runtime.register(CreativeDirectorAgent())
        task = create_creative_task()

        result = runtime.submit_task(task)

        self.assertIsInstance(result, CreativeBrief)

    def test_runtime_propagates_aether_errors(self) -> None:
        """Runtime propagates Aether validation errors."""
        runtime = HeliosRuntime()
        runtime.register(CreativeDirectorAgent())
        task = create_creative_task({"storyboard": "invalid"})

        with self.assertRaises(ValueError):
            runtime.submit_task(task)

        self.assertIs(task.status, TaskStatus.FAILED)


if __name__ == "__main__":
    unittest.main()
