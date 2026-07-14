"""Tests for the Mira audience research agent."""

import unittest
from typing import Any

from agents.audience_research.agent import AudienceResearchAgent
from agents.audience_research.mock_llm_provider import MockAudienceLLMProvider
from agents.audience_research.models import AudienceProfile
from engine.llm.base_provider import BaseLLMProvider
from engine.llm.models import LLMRequest, LLMResponse
from engine.runtime.capability import AgentCapability
from engine.tasks.priority import TaskPriority
from engine.tasks.status import TaskStatus
from engine.tasks.task import Task
from engine.tools.llm_tool import LLMTool


class RecordingAudienceLLMProvider(BaseLLMProvider):
    """LLM provider that records audience research requests."""

    def __init__(self) -> None:
        """Create a recording provider."""
        super().__init__(provider_id="recording", model="recording-audience-model")
        self.received_request: LLMRequest | None = None
        self.response = MockAudienceLLMProvider(
            provider_id=self.provider_id,
            model=self.model,
        ).generate(
            LLMRequest(
                system_prompt="recording",
                user_prompt="recording",
            ),
        )

    def generate(self, request: LLMRequest) -> LLMResponse:
        """Record the request and return a deterministic response."""
        self.received_request = request
        return self.response


class FailingAudienceLLMProvider(BaseLLMProvider):
    """LLM provider that always fails."""

    def __init__(self) -> None:
        """Create a failing provider."""
        super().__init__(provider_id="failing", model="failing-audience-model")

    def generate(self, request: LLMRequest) -> LLMResponse:
        """Raise a runtime error."""
        msg = "audience llm failed"
        raise RuntimeError(msg)


def create_audience_task(payload: dict[str, Any] | None = None) -> Task:
    """Create an audience research task."""
    task_payload = {"topic": "AI Agents"} if payload is None else payload
    return Task(
        task_id="audience-task-1",
        title="Audience Research",
        description="Create an audience profile.",
        priority=TaskPriority.MEDIUM,
        required_capability=AgentCapability.AUDIENCE_RESEARCH,
        payload=task_payload,
    )


class AudienceResearchAgentTestCase(unittest.TestCase):
    """Tests for AudienceResearchAgent behavior."""

    def test_agent_has_audience_research_capability(self) -> None:
        """Mira declares the AUDIENCE_RESEARCH capability."""
        agent = AudienceResearchAgent()

        self.assertTrue(agent.can_handle(AgentCapability.AUDIENCE_RESEARCH))

    def test_agent_name_is_mira(self) -> None:
        """Mira has the expected display name."""
        agent = AudienceResearchAgent()

        self.assertEqual(agent.name, "Mira")

    def test_default_llm_tool_exists(self) -> None:
        """Mira has a default LLM tool."""
        agent = AudienceResearchAgent()

        self.assertIsInstance(agent.get_tool("llm"), LLMTool)

    def test_valid_task_completes(self) -> None:
        """A valid audience task ends as COMPLETED."""
        agent = AudienceResearchAgent()
        task = create_audience_task()

        agent.run(task)

        self.assertIs(task.status, TaskStatus.COMPLETED)

    def test_topic_is_validated(self) -> None:
        """Mira accepts a valid topic payload."""
        agent = AudienceResearchAgent()
        task = create_audience_task({"topic": "Creator Economy"})

        result = agent.run(task)

        self.assertEqual(result.topic, "Creator Economy")

    def test_empty_topic_raises_value_error(self) -> None:
        """Mira rejects empty topics."""
        agent = AudienceResearchAgent()
        task = create_audience_task({"topic": ""})

        with self.assertRaises(ValueError):
            agent.run(task)

    def test_language_default_is_de(self) -> None:
        """Mira defaults language to German."""
        agent = AudienceResearchAgent()
        task = create_audience_task()

        profile = agent.run(task)

        self.assertEqual(profile.language, "de")

    def test_target_age_range_default_is_18_to_34(self) -> None:
        """Mira defaults the target age range."""
        agent = AudienceResearchAgent()
        task = create_audience_task()

        profile = agent.run(task)

        self.assertEqual(profile.target_age_range, "18-34")

    def test_llm_receives_llm_request(self) -> None:
        """Mira sends an LLMRequest to the LLM tool."""
        provider = RecordingAudienceLLMProvider()
        agent = AudienceResearchAgent(tools=[LLMTool(provider=provider)])
        task = create_audience_task()

        agent.run(task)

        self.assertIsInstance(provider.received_request, LLMRequest)

    def test_prompt_contains_topic_language_and_age_range(self) -> None:
        """Mira prompt contains topic, language and age range."""
        provider = RecordingAudienceLLMProvider()
        agent = AudienceResearchAgent(tools=[LLMTool(provider=provider)])
        task = create_audience_task(
            {
                "topic": "AI Agents",
                "language": "en",
                "target_age_range": "25-44",
            },
        )

        agent.run(task)

        request = provider.received_request
        assert request is not None
        self.assertIn("Topic: AI Agents", request.user_prompt)
        self.assertIn("Language: en", request.user_prompt)
        self.assertIn("Target Age Range: 25-44", request.user_prompt)
        self.assertIn("Interessen", request.user_prompt)
        self.assertIn("Probleme", request.user_prompt)
        self.assertIn("Emotionen", request.user_prompt)
        self.assertIn("Tonalität", request.user_prompt)
        self.assertIn("Plattformpräferenzen", request.user_prompt)
        self.assertEqual(
            request.system_prompt,
            "Mira analysiert Zielgruppen für Social-Media-Content sachlich, "
            "datenorientiert und ohne stereotype Annahmen.",
        )

    def test_last_profile_is_stored_and_task_result_matches(self) -> None:
        """Mira stores the generated profile and writes it to the task."""
        agent = AudienceResearchAgent()
        task = create_audience_task()

        profile = agent.run(task)

        self.assertIs(agent.last_profile, profile)
        self.assertIs(task.result, profile)

    def test_mock_provider_is_deterministic(self) -> None:
        """MockAudienceLLMProvider returns deterministic content."""
        provider = MockAudienceLLMProvider()
        request = LLMRequest(system_prompt="Mira", user_prompt="Topic: AI Agents")

        first_response = provider.generate(request)
        second_response = provider.generate(request)

        self.assertEqual(first_response, second_response)
        self.assertEqual(first_response.provider, "mock")
        self.assertEqual(first_response.model, "mock-audience-model")

    def test_profile_contains_structured_audience_data(self) -> None:
        """Mira creates structured audience research output."""
        agent = AudienceResearchAgent()
        task = create_audience_task()

        profile = agent.run(task)

        self.assertIsInstance(profile, AudienceProfile)
        self.assertEqual(profile.generated_by, "mock:mock-audience-model")
        self.assertGreater(len(profile.interests), 0)
        self.assertGreater(len(profile.pain_points), 0)
        self.assertGreater(len(profile.preferred_platforms), 0)

    def test_llm_failure_sets_task_failed(self) -> None:
        """LLM errors move the task to FAILED."""
        agent = AudienceResearchAgent(
            tools=[LLMTool(provider=FailingAudienceLLMProvider())],
        )
        task = create_audience_task()

        with self.assertRaises(RuntimeError):
            agent.run(task)

        self.assertIs(task.status, TaskStatus.FAILED)
        self.assertEqual(task.error_message, "audience llm failed")

    def test_errors_are_propagated(self) -> None:
        """LLM errors are propagated unchanged."""
        agent = AudienceResearchAgent(
            tools=[LLMTool(provider=FailingAudienceLLMProvider())],
        )
        task = create_audience_task()

        with self.assertRaisesRegex(RuntimeError, "audience llm failed"):
            agent.run(task)


if __name__ == "__main__":
    unittest.main()
