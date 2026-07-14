"""Runtime integration tests for Sage knowledge agent."""

import unittest

from agents.knowledge.agent import KnowledgeAgent
from agents.knowledge.models import KnowledgeResponse
from engine.runtime.capability import AgentCapability
from engine.runtime.runtime import HeliosRuntime
from engine.tasks.priority import TaskPriority
from engine.tasks.status import TaskStatus
from engine.tasks.task import Task


def create_knowledge_task(query: object = "AI content strategy") -> Task:
    """Create a knowledge task for runtime integration tests."""
    return Task(
        task_id="knowledge-task-1",
        title="Knowledge",
        description="Retrieve structured knowledge.",
        priority=TaskPriority.MEDIUM,
        required_capability=AgentCapability.KNOWLEDGE,
        payload={"query": query},
    )


class KnowledgeRuntimeIntegrationTestCase(unittest.TestCase):
    """Integration tests for Sage through HeliosRuntime."""

    def test_runtime_dispatches_knowledge_task_to_sage(self) -> None:
        """Runtime can dispatch KNOWLEDGE tasks to Sage."""
        runtime = HeliosRuntime()
        sage = KnowledgeAgent()
        task = create_knowledge_task()
        runtime.register(sage)

        result = runtime.submit_task(task)

        self.assertIsInstance(result, KnowledgeResponse)
        self.assertIs(result, task.result)
        self.assertIs(task.status, TaskStatus.COMPLETED)
        self.assertIs(sage.last_response, result)
        self.assertEqual(result.query, "AI content strategy")

    def test_runtime_returns_knowledge_response(self) -> None:
        """Runtime returns the KnowledgeResponse from Sage."""
        runtime = HeliosRuntime()
        runtime.register(KnowledgeAgent())
        task = create_knowledge_task()

        result = runtime.submit_task(task)

        self.assertIsInstance(result, KnowledgeResponse)

    def test_runtime_propagates_sage_errors(self) -> None:
        """Runtime propagates Sage validation errors."""
        runtime = HeliosRuntime()
        runtime.register(KnowledgeAgent())
        task = create_knowledge_task("")

        with self.assertRaises(ValueError):
            runtime.submit_task(task)

        self.assertIs(task.status, TaskStatus.FAILED)


if __name__ == "__main__":
    unittest.main()
