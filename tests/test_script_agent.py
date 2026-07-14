"""Tests for the Orion script agent."""

import unittest
from typing import Any

from agents.audience_research.models import AudiencePainPoint, AudienceProfile
from agents.knowledge.models import (
    KnowledgeCategory,
    KnowledgeItem,
    KnowledgeResponse,
)
from agents.script.agent import ScriptAgent
from agents.script.mock_llm_provider import MockScriptLLMProvider
from agents.script.models import VideoScript
from agents.strategy.models import ContentIdea, ContentStrategy
from agents.trend_research.models import TrendResult
from agents.trend_research.report import TrendReport
from engine.llm.base_provider import BaseLLMProvider
from engine.llm.models import LLMRequest, LLMResponse
from engine.runtime.capability import AgentCapability
from engine.tasks.priority import TaskPriority
from engine.tasks.status import TaskStatus
from engine.tasks.task import Task
from engine.tools.llm_tool import LLMTool


class RecordingScriptLLMProvider(BaseLLMProvider):
    """LLM provider that records script requests."""

    def __init__(self) -> None:
        """Create a recording provider."""
        super().__init__(provider_id="recording", model="recording-script-model")
        self.received_request: LLMRequest | None = None
        self.response = MockScriptLLMProvider(
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


class FailingScriptLLMProvider(BaseLLMProvider):
    """LLM provider that always fails."""

    def __init__(self) -> None:
        """Create a failing provider."""
        super().__init__(provider_id="failing", model="failing-script-model")

    def generate(self, request: LLMRequest) -> LLMResponse:
        """Raise a runtime error."""
        msg = "script llm failed"
        raise RuntimeError(msg)


def create_trend_report() -> TrendReport:
    """Create a trend report for script tests."""
    return TrendReport(
        query="AI Agents",
        summary="AI agents are becoming practical workflow tools.",
        trends=[
            TrendResult("AI workflow automation", 0.92, "mock", "High demand."),
            TrendResult("Agent productivity", 0.84, "mock", "Strong interest."),
        ],
        generated_by="mock:mock-trend-model",
    )


def create_audience_profile() -> AudienceProfile:
    """Create an audience profile for script tests."""
    return AudienceProfile(
        topic="AI Agents",
        target_age_range="18-34",
        language="de",
        interests=["Automation", "Creator productivity"],
        pain_points=[
            AudiencePainPoint("Tool overload", 0.82, "Frustration"),
            AudiencePainPoint("Unclear ROI", 0.76, "Uncertainty"),
        ],
        preferred_tone="Clear and practical",
        preferred_platforms=["YouTube", "LinkedIn"],
        summary="Creators want practical AI workflows.",
        generated_by="mock:mock-audience-model",
    )


def create_knowledge_response() -> KnowledgeResponse:
    """Create a knowledge response for script tests."""
    return KnowledgeResponse(
        query="AI content strategy",
        summary="Use specificity and narrative tension.",
        items=[
            KnowledgeItem(
                "Audience Promise",
                KnowledgeCategory.MARKETING,
                "Clarify the promise.",
                "internal",
                0.91,
            ),
            KnowledgeItem(
                "Narrative Tension",
                KnowledgeCategory.STORYTELLING,
                "Contrast pain with a better state.",
                "internal",
                0.88,
            ),
        ],
        generated_by="mock:mock-knowledge-model",
    )


def create_content_strategy() -> ContentStrategy:
    """Create a content strategy for script tests."""
    return ContentStrategy(
        query="AI Agents",
        summary="Make practical AI workflows easy to understand.",
        ideas=[
            ContentIdea(
                "Workflow Demo",
                "Practical implementation",
                "YouTube",
                "Shows the trend as a repeatable workflow.",
            ),
            ContentIdea(
                "Founder POV",
                "Opinion-led narrative",
                "LinkedIn",
                "Turns evidence into executive relevance.",
            ),
        ],
        generated_by="mock:mock-strategy-model",
    )


def create_script_payload() -> dict[str, Any]:
    """Create a valid script payload."""
    return {
        "trend_report": create_trend_report(),
        "audience_profile": create_audience_profile(),
        "knowledge_response": create_knowledge_response(),
        "content_strategy": create_content_strategy(),
    }


def create_script_task(payload: dict[str, Any] | None = None) -> Task:
    """Create a script task."""
    return Task(
        task_id="script-task-1",
        title="Script",
        description="Create video script from company intelligence.",
        priority=TaskPriority.MEDIUM,
        required_capability=AgentCapability.SCRIPT,
        payload=create_script_payload() if payload is None else payload,
    )


class ScriptAgentTestCase(unittest.TestCase):
    """Tests for ScriptAgent behavior."""

    def test_agent_has_script_capability(self) -> None:
        """Orion declares the SCRIPT capability."""
        agent = ScriptAgent()

        self.assertTrue(agent.can_handle(AgentCapability.SCRIPT))

    def test_agent_name_is_orion(self) -> None:
        """Orion has the expected display name."""
        agent = ScriptAgent()

        self.assertEqual(agent.name, "Orion")

    def test_default_llm_tool_exists(self) -> None:
        """Orion has a default LLM tool."""
        agent = ScriptAgent()

        self.assertIsInstance(agent.get_tool("llm"), LLMTool)

    def test_all_inputs_are_validated(self) -> None:
        """Orion accepts all required model inputs."""
        agent = ScriptAgent()
        task = create_script_task()

        result = agent.run(task)

        self.assertIsInstance(result, VideoScript)

    def test_missing_models_raise_value_error(self) -> None:
        """Orion rejects payloads missing required models."""
        required_fields = [
            "trend_report",
            "audience_profile",
            "knowledge_response",
            "content_strategy",
        ]
        for field in required_fields:
            with self.subTest(field=field):
                payload = create_script_payload()
                payload[field] = "invalid"
                agent = ScriptAgent()
                task = create_script_task(payload)

                with self.assertRaises(ValueError):
                    agent.run(task)

    def test_task_completed_after_success(self) -> None:
        """Successful script generation completes the task."""
        agent = ScriptAgent()
        task = create_script_task()

        agent.run(task)

        self.assertIs(task.status, TaskStatus.COMPLETED)

    def test_task_result_and_last_script_are_identical(self) -> None:
        """Orion stores the generated script and writes it to the task."""
        agent = ScriptAgent()
        task = create_script_task()

        script = agent.run(task)

        self.assertIs(task.result, script)
        self.assertIs(agent.last_script, script)

    def test_prompt_contains_all_required_inputs(self) -> None:
        """Orion prompt contains trend, audience, knowledge and strategy data."""
        provider = RecordingScriptLLMProvider()
        agent = ScriptAgent(tools=[LLMTool(provider=provider)])
        task = create_script_task()

        agent.run(task)

        request = provider.received_request
        assert request is not None
        self.assertIn("Query: AI Agents", request.user_prompt)
        self.assertIn("Zielgruppe: AI Agents", request.user_prompt)
        self.assertIn(KnowledgeCategory.MARKETING.value, request.user_prompt)
        self.assertIn(KnowledgeCategory.STORYTELLING.value, request.user_prompt)
        self.assertIn(
            "Zusammenfassung: Make practical AI workflows easy to understand.",
            request.user_prompt,
        )
        self.assertEqual(
            request.system_prompt,
            "Orion schreibt hochwertige Social-Media-Skripte auf Basis "
            "aller Unternehmensdaten.",
        )

    def test_mock_provider_is_deterministic(self) -> None:
        """MockScriptLLMProvider returns deterministic content."""
        provider = MockScriptLLMProvider()
        request = LLMRequest(system_prompt="Orion", user_prompt="Script data")

        first_response = provider.generate(request)
        second_response = provider.generate(request)

        self.assertEqual(first_response, second_response)
        self.assertEqual(first_response.provider, "mock")
        self.assertEqual(first_response.model, "mock-script-model")

    def test_script_contains_required_parts(self) -> None:
        """Orion creates a complete VideoScript."""
        agent = ScriptAgent()
        task = create_script_task()

        script = agent.run(task)

        self.assertTrue(script.title)
        self.assertTrue(script.hook)
        self.assertGreaterEqual(len(script.sections), 3)
        self.assertTrue(script.call_to_action)
        self.assertTrue(script.summary)
        self.assertIn("# ", script.to_markdown())

    def test_llm_failure_sets_task_failed(self) -> None:
        """LLM errors move the task to FAILED."""
        agent = ScriptAgent(tools=[LLMTool(provider=FailingScriptLLMProvider())])
        task = create_script_task()

        with self.assertRaises(RuntimeError):
            agent.run(task)

        self.assertIs(task.status, TaskStatus.FAILED)
        self.assertEqual(task.error_message, "script llm failed")

    def test_errors_are_propagated(self) -> None:
        """LLM errors are propagated unchanged."""
        agent = ScriptAgent(tools=[LLMTool(provider=FailingScriptLLMProvider())])
        task = create_script_task()

        with self.assertRaisesRegex(RuntimeError, "script llm failed"):
            agent.run(task)


if __name__ == "__main__":
    unittest.main()
