"""Runtime integration tests for Lumen storyboard agent."""

import unittest

from agents.hook.models import HookCandidate, OptimizedHook
from agents.script.models import ScriptSection, VideoScript
from agents.storyboard.agent import StoryboardAgent
from agents.storyboard.models import Storyboard
from engine.runtime.capability import AgentCapability
from engine.runtime.runtime import HeliosRuntime
from engine.tasks.priority import TaskPriority
from engine.tasks.status import TaskStatus
from engine.tasks.task import Task


def create_storyboard_task(payload: dict[str, object] | None = None) -> Task:
    """Create a storyboard task for runtime integration tests."""
    selected_hook = HookCandidate(
        text="The fastest AI win is a workflow you stop repeating.",
        score=0.95,
        reason="Highest clarity and novelty.",
    )
    task_payload = {
        "video_script": VideoScript(
            title="AI Agents That Actually Save Time",
            hook="Most AI agent content sounds futuristic.",
            sections=[
                ScriptSection("Problem", "Teams are overwhelmed by tools."),
                ScriptSection("Insight", "Automation removes repeated work."),
                ScriptSection("Action", "Start with one pain point."),
            ],
            call_to_action="Pick one recurring content task.",
            summary="A practical script about AI workflows.",
            generated_by="mock:mock-script-model",
        ),
        "optimized_hook": OptimizedHook(
            original_hook="Most AI agent content sounds futuristic.",
            selected_hook=selected_hook,
            candidates=[selected_hook],
            summary="Optimized for clarity.",
            generated_by="mock:mock-hook-model",
        ),
    }
    return Task(
        task_id="storyboard-task-1",
        title="Storyboard",
        description="Create a short-form video storyboard.",
        priority=TaskPriority.MEDIUM,
        required_capability=AgentCapability.STORYBOARD,
        payload=task_payload if payload is None else payload,
    )


class StoryboardRuntimeIntegrationTestCase(unittest.TestCase):
    """Integration tests for Lumen through HeliosRuntime."""

    def test_runtime_dispatches_storyboard_task_to_lumen(self) -> None:
        """Runtime can dispatch STORYBOARD tasks to Lumen."""
        runtime = HeliosRuntime()
        lumen = StoryboardAgent()
        task = create_storyboard_task()
        runtime.register(lumen)

        result = runtime.submit_task(task)

        self.assertIsInstance(result, Storyboard)
        self.assertIs(result, task.result)
        self.assertIs(task.status, TaskStatus.COMPLETED)
        self.assertIs(lumen.last_storyboard, result)

    def test_runtime_returns_storyboard(self) -> None:
        """Runtime returns the Storyboard from Lumen."""
        runtime = HeliosRuntime()
        runtime.register(StoryboardAgent())
        task = create_storyboard_task()

        result = runtime.submit_task(task)

        self.assertIsInstance(result, Storyboard)

    def test_runtime_propagates_lumen_errors(self) -> None:
        """Runtime propagates Lumen validation errors."""
        runtime = HeliosRuntime()
        runtime.register(StoryboardAgent())
        task = create_storyboard_task({"video_script": "invalid"})

        with self.assertRaises(ValueError):
            runtime.submit_task(task)

        self.assertIs(task.status, TaskStatus.FAILED)


if __name__ == "__main__":
    unittest.main()
