"""Tests for the Sage knowledge agent."""

import unittest

from agents.knowledge.agent import KnowledgeAgent
from agents.knowledge.mock_provider import MockKnowledgeProvider
from agents.knowledge.models import (
    KnowledgeCategory,
    KnowledgeItem,
    KnowledgeResponse,
)
from engine.llm.models import LLMRequest
from engine.runtime.capability import AgentCapability
from engine.tasks.priority import TaskPriority
from engine.tasks.status import TaskStatus
from engine.tasks.task import Task


class RecordingKnowledgeProvider(MockKnowledgeProvider):
    """Knowledge provider that records requests."""

    def __init__(self) -> None:
        """Create a recording provider."""
        super().__init__(provider_id="recording", model="recording-knowledge-model")
        self.received_request: LLMRequest | None = None

    def search(self, request: LLMRequest) -> list[KnowledgeItem]:
        """Record the request and return deterministic items."""
        self.received_request = request
        return super().search(request)


class FailingKnowledgeProvider(MockKnowledgeProvider):
    """Knowledge provider that always fails."""

    def search(self, request: LLMRequest) -> list[KnowledgeItem]:
        """Raise a runtime error."""
        msg = "knowledge provider failed"
        raise RuntimeError(msg)


def create_knowledge_task(query: object = "AI content strategy") -> Task:
    """Create a knowledge task."""
    return Task(
        task_id="knowledge-task-1",
        title="Knowledge",
        description="Retrieve structured knowledge.",
        priority=TaskPriority.MEDIUM,
        required_capability=AgentCapability.KNOWLEDGE,
        payload={"query": query},
    )


class KnowledgeAgentTestCase(unittest.TestCase):
    """Tests for KnowledgeAgent behavior."""

    def test_agent_has_knowledge_capability(self) -> None:
        """Sage declares the KNOWLEDGE capability."""
        agent = KnowledgeAgent()

        self.assertTrue(agent.can_handle(AgentCapability.KNOWLEDGE))

    def test_agent_name_is_sage(self) -> None:
        """Sage has the expected display name."""
        agent = KnowledgeAgent()

        self.assertEqual(agent.name, "Sage")

    def test_default_provider_exists(self) -> None:
        """Sage has a default provider."""
        agent = KnowledgeAgent()

        self.assertIsInstance(agent.provider, MockKnowledgeProvider)

    def test_query_is_validated(self) -> None:
        """Sage accepts a valid query."""
        agent = KnowledgeAgent()
        task = create_knowledge_task("Storytelling hooks")

        response = agent.run(task)

        self.assertEqual(response.query, "Storytelling hooks")

    def test_empty_query_raises_value_error(self) -> None:
        """Sage rejects empty queries."""
        agent = KnowledgeAgent()
        task = create_knowledge_task("")

        with self.assertRaises(ValueError):
            agent.run(task)

    def test_task_completed_after_success(self) -> None:
        """Successful knowledge retrieval completes the task."""
        agent = KnowledgeAgent()
        task = create_knowledge_task()

        agent.run(task)

        self.assertIs(task.status, TaskStatus.COMPLETED)

    def test_last_response_is_stored_and_task_result_matches(self) -> None:
        """Sage stores the response and writes it to the task."""
        agent = KnowledgeAgent()
        task = create_knowledge_task()

        response = agent.run(task)

        self.assertIs(agent.last_response, response)
        self.assertIs(task.result, response)

    def test_provider_is_deterministic(self) -> None:
        """MockKnowledgeProvider returns deterministic items."""
        provider = MockKnowledgeProvider()
        request = LLMRequest(system_prompt="Sage", user_prompt="Query: hooks")

        first_items = provider.search(request)
        second_items = provider.search(request)

        self.assertEqual(first_items, second_items)
        self.assertGreaterEqual(len(first_items), 5)

    def test_confidence_is_validated(self) -> None:
        """KnowledgeItem validates confidence values."""
        with self.assertRaises(ValueError):
            KnowledgeItem(
                title="Invalid",
                category=KnowledgeCategory.MARKETING,
                content="Invalid confidence.",
                source="test",
                confidence=1.1,
            )

    def test_prompt_contains_query_and_categories(self) -> None:
        """Sage prompt contains the query and requested categories."""
        provider = RecordingKnowledgeProvider()
        agent = KnowledgeAgent(provider=provider)
        task = create_knowledge_task("AI hooks")

        agent.run(task)

        request = provider.received_request
        assert request is not None
        self.assertIn("Query: AI hooks", request.user_prompt)
        self.assertIn("Marketing", request.user_prompt)
        self.assertIn("Storytelling", request.user_prompt)
        self.assertIn("Copywriting", request.user_prompt)
        self.assertIn("Psychologie", request.user_prompt)
        self.assertIn("Frameworks", request.user_prompt)
        self.assertIn(KnowledgeCategory.SOCIAL_MEDIA.value, request.user_prompt)
        self.assertEqual(
            request.system_prompt,
            "Sage verwaltet das Unternehmenswissen der AI Content Company.",
        )

    def test_response_contains_structured_knowledge(self) -> None:
        """Sage returns structured knowledge data."""
        agent = KnowledgeAgent()
        task = create_knowledge_task()

        response = agent.run(task)

        self.assertIsInstance(response, KnowledgeResponse)
        self.assertEqual(response.generated_by, "mock:mock-knowledge-model")
        self.assertGreaterEqual(len(response.items), 5)
        self.assertTrue(all(isinstance(item, KnowledgeItem) for item in response.items))

    def test_provider_failure_sets_task_failed(self) -> None:
        """Provider errors move the task to FAILED."""
        agent = KnowledgeAgent(provider=FailingKnowledgeProvider())
        task = create_knowledge_task()

        with self.assertRaises(RuntimeError):
            agent.run(task)

        self.assertIs(task.status, TaskStatus.FAILED)
        self.assertEqual(task.error_message, "knowledge provider failed")

    def test_errors_are_propagated(self) -> None:
        """Provider errors are propagated unchanged."""
        agent = KnowledgeAgent(provider=FailingKnowledgeProvider())
        task = create_knowledge_task()

        with self.assertRaisesRegex(RuntimeError, "knowledge provider failed"):
            agent.run(task)


if __name__ == "__main__":
    unittest.main()
