"""Runtime integration tests for Apollo hook agent."""

import unittest

from agents.hook.agent import HookAgent
from agents.hook.models import OptimizedHook
from agents.script.models import ScriptSection, VideoScript
from engine.runtime.capability import AgentCapability
from engine.runtime.runtime import HeliosRuntime
from engine.tasks.priority import TaskPriority
from engine.tasks.status import TaskStatus
from engine.tasks.task import Task


def create_hook_task(payload: dict[str, object] | None = None) -> Task:
    """Create a hook task for runtime integration tests."""
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
    }
    return Task(
        task_id="hook-task-1",
        title="Hook",
        description="Optimize video hook.",
        priority=TaskPriority.MEDIUM,
        required_capability=AgentCapability.HOOK,
        payload=task_payload if payload is None else payload,
    )


class HookRuntimeIntegrationTestCase(unittest.TestCase):
    """Integration tests for Apollo through HeliosRuntime."""

    def test_runtime_dispatches_hook_task_to_apollo(self) -> None:
        """Runtime can dispatch HOOK tasks to Apollo."""
        runtime = HeliosRuntime()
        apollo = HookAgent()
        task = create_hook_task()
        runtime.register(apollo)

        result = runtime.submit_task(task)

        self.assertIsInstance(result, OptimizedHook)
        self.assertIs(result, task.result)
        self.assertIs(task.status, TaskStatus.COMPLETED)
        self.assertIs(apollo.last_hook, result)

    def test_runtime_returns_optimized_hook(self) -> None:
        """Runtime returns the OptimizedHook from Apollo."""
        runtime = HeliosRuntime()
        runtime.register(HookAgent())
        task = create_hook_task()

        result = runtime.submit_task(task)

        self.assertIsInstance(result, OptimizedHook)

    def test_runtime_propagates_apollo_errors(self) -> None:
        """Runtime propagates Apollo validation errors."""
        runtime = HeliosRuntime()
        runtime.register(HookAgent())
        task = create_hook_task({"video_script": "invalid"})

        with self.assertRaises(ValueError):
            runtime.submit_task(task)

        self.assertIs(task.status, TaskStatus.FAILED)


if __name__ == "__main__":
    unittest.main()
