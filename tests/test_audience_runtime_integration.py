"""Runtime integration tests for Mira audience research agent."""

import unittest

from agents.audience_research.agent import AudienceResearchAgent
from agents.audience_research.models import AudienceProfile
from engine.runtime.capability import AgentCapability
from engine.runtime.runtime import HeliosRuntime
from engine.tasks.priority import TaskPriority
from engine.tasks.status import TaskStatus
from engine.tasks.task import Task


def create_audience_task(payload: dict[str, object] | None = None) -> Task:
    """Create an audience research task for runtime integration tests."""
    task_payload = {"topic": "AI Agents"} if payload is None else payload
    return Task(
        task_id="audience-task-1",
        title="Audience Research",
        description="Create an audience profile.",
        priority=TaskPriority.MEDIUM,
        required_capability=AgentCapability.AUDIENCE_RESEARCH,
        payload=task_payload,
    )


class AudienceRuntimeIntegrationTestCase(unittest.TestCase):
    """Integration tests for Mira through HeliosRuntime."""

    def test_runtime_dispatches_audience_task_to_mira(self) -> None:
        """Runtime can dispatch AUDIENCE_RESEARCH tasks to Mira."""
        runtime = HeliosRuntime()
        mira = AudienceResearchAgent()
        task = create_audience_task()
        runtime.register(mira)

        result = runtime.submit_task(task)

        self.assertIsInstance(result, AudienceProfile)
        self.assertIs(result, task.result)
        self.assertIs(task.status, TaskStatus.COMPLETED)
        self.assertIs(mira.last_profile, result)
        self.assertEqual(result.topic, "AI Agents")

    def test_runtime_returns_audience_profile(self) -> None:
        """Runtime returns the AudienceProfile from Mira."""
        runtime = HeliosRuntime()
        runtime.register(AudienceResearchAgent())
        task = create_audience_task()

        result = runtime.submit_task(task)

        self.assertIsInstance(result, AudienceProfile)

    def test_runtime_propagates_mira_errors(self) -> None:
        """Runtime propagates Mira validation errors."""
        runtime = HeliosRuntime()
        runtime.register(AudienceResearchAgent())
        task = create_audience_task({"topic": ""})

        with self.assertRaises(ValueError):
            runtime.submit_task(task)

        self.assertIs(task.status, TaskStatus.FAILED)


if __name__ == "__main__":
    unittest.main()
