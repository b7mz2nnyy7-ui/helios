"""Tests for the Mentor learning agent."""

import unittest

from agents.analytics.models import AnalyticsReport, PlatformMetrics
from agents.learning.agent import LearningAgent
from agents.learning.mock_llm_provider import MockLearningLLMProvider
from agents.learning.models import LearningInsight, LearningReport
from engine.llm.base_provider import BaseLLMProvider
from engine.llm.models import LLMRequest, LLMResponse
from engine.runtime.capability import AgentCapability
from engine.tasks.priority import TaskPriority
from engine.tasks.status import TaskStatus
from engine.tasks.task import Task
from engine.tools.llm_tool import LLMTool


class RecordingLearningLLMProvider(BaseLLMProvider):
    """LLM provider that records learning requests."""

    def __init__(self) -> None:
        """Create a recording provider."""
        super().__init__(provider_id="recording", model="recording-learning-model")
        self.received_request: LLMRequest | None = None
        self.response = MockLearningLLMProvider(
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


class FailingLearningLLMProvider(BaseLLMProvider):
    """LLM provider that always fails."""

    def __init__(self) -> None:
        """Create a failing provider."""
        super().__init__(provider_id="failing", model="failing-learning-model")

    def generate(self, request: LLMRequest) -> LLMResponse:
        """Raise a runtime error."""
        msg = "learning llm failed"
        raise RuntimeError(msg)


def create_analytics_report() -> AnalyticsReport:
    """Create an analytics report for learning tests."""
    return AnalyticsReport(
        report_id="analytics-video-1",
        video_id="video-1",
        metrics=[
            PlatformMetrics(
                platform="TikTok",
                views=1000,
                watch_time_seconds=2400.0,
                average_watch_percentage=72.0,
                likes=120,
                comments=18,
                shares=32,
                saves=44,
                followers_gained=26,
                ctr=0.12,
                engagement_rate=0.18,
            ),
            PlatformMetrics(
                platform="YouTube",
                views=750,
                watch_time_seconds=2100.0,
                average_watch_percentage=64.0,
                likes=100,
                comments=15,
                shares=27,
                saves=40,
                followers_gained=22,
                ctr=0.1,
                engagement_rate=0.15,
            ),
        ],
        total_views=1750,
        total_engagement=396,
        strongest_platform="TikTok",
        weakest_platform="YouTube",
        summary="Deterministic analytics.",
        generated_by="mock:mock-analytics",
    )


def create_learning_task(payload: dict[str, object] | None = None) -> Task:
    """Create a learning task."""
    return Task(
        task_id="learning-task-1",
        title="Learning",
        description="Create learning report from analytics.",
        priority=TaskPriority.MEDIUM,
        required_capability=AgentCapability.LEARNING,
        payload=(
            {"analytics_report": create_analytics_report()}
            if payload is None
            else payload
        ),
    )


class LearningAgentTestCase(unittest.TestCase):
    """Tests for LearningAgent behavior."""

    def test_agent_has_learning_capability(self) -> None:
        """Mentor declares the LEARNING capability."""
        agent = LearningAgent()

        self.assertTrue(agent.can_handle(AgentCapability.LEARNING))

    def test_agent_name_is_mentor(self) -> None:
        """Mentor has the expected display name."""
        agent = LearningAgent()

        self.assertEqual(agent.name, "Mentor")

    def test_default_llm_tool_exists(self) -> None:
        """Mentor has a default LLM tool."""
        agent = LearningAgent()

        self.assertIsInstance(agent.get_tool("llm"), LLMTool)

    def test_valid_analytics_report_completes_task(self) -> None:
        """A valid analytics report leads to COMPLETED."""
        agent = LearningAgent()
        task = create_learning_task()

        report = agent.run(task)

        self.assertIsInstance(report, LearningReport)
        self.assertIs(task.status, TaskStatus.COMPLETED)

    def test_missing_analytics_report_raises_value_error(self) -> None:
        """Mentor rejects missing analytics reports."""
        agent = LearningAgent()
        task = create_learning_task({})

        with self.assertRaises(ValueError):
            agent.run(task)

    def test_wrong_payload_type_raises_value_error(self) -> None:
        """Mentor rejects wrong analytics report payload types."""
        agent = LearningAgent()
        task = create_learning_task({"analytics_report": "invalid"})

        with self.assertRaises(ValueError):
            agent.run(task)

    def test_prompt_contains_video_id_and_platform_metrics(self) -> None:
        """Mentor prompt contains required analytics details."""
        provider = RecordingLearningLLMProvider()
        agent = LearningAgent(tools=[LLMTool(provider=provider)])
        task = create_learning_task()

        agent.run(task)

        request = provider.received_request
        assert request is not None
        self.assertIn("Video ID: video-1", request.user_prompt)
        self.assertIn("Gesamtviews: 1750", request.user_prompt)
        self.assertIn("Gesamtengagement: 396", request.user_prompt)
        self.assertIn("Stärkste Plattform: TikTok", request.user_prompt)
        self.assertIn("Schwächste Plattform: YouTube", request.user_prompt)
        self.assertIn("watch_percentage=72.0", request.user_prompt)
        self.assertIn("ctr=0.12", request.user_prompt)
        self.assertIn("engagement_rate=0.18", request.user_prompt)
        self.assertIn("shares=32", request.user_prompt)
        self.assertIn("saves=44", request.user_prompt)
        self.assertEqual(
            request.system_prompt,
            "Mentor analysiert Content-Performance und leitet belastbare "
            "Learnings und Experimente ab.",
        )

    def test_last_learning_report_and_task_result_are_identical(self) -> None:
        """Mentor stores the report and writes it to the task."""
        agent = LearningAgent()
        task = create_learning_task()

        report = agent.run(task)

        self.assertIs(task.result, report)
        self.assertIs(agent.last_learning_report, report)

    def test_mock_provider_is_deterministic(self) -> None:
        """MockLearningLLMProvider returns deterministic responses."""
        provider = MockLearningLLMProvider()
        request = LLMRequest(system_prompt="Mentor", user_prompt="Analytics data")

        first_response = provider.generate(request)
        second_response = provider.generate(request)

        self.assertEqual(first_response, second_response)
        self.assertEqual(first_response.provider, "mock")
        self.assertEqual(first_response.model, "mock-learning-model")

    def test_insight_confidence_is_validated(self) -> None:
        """LearningInsight validates confidence."""
        with self.assertRaises(ValueError):
            LearningInsight(
                category="Retention",
                observation="Strong retention.",
                evidence="Watch percentage.",
                recommendation="Repeat structure.",
                confidence=1.1,
            )

    def test_strength_or_weakness_is_required(self) -> None:
        """LearningReport requires at least one strength or weakness."""
        with self.assertRaises(ValueError):
            LearningReport(
                video_id="video-1",
                performance_summary="Summary.",
                strengths=[],
                weaknesses=[],
                experiments=["Experiment"],
                recommended_actions=["Action"],
                generated_by="mock",
            )

    def test_experiments_must_not_be_empty(self) -> None:
        """LearningReport requires experiments."""
        with self.assertRaises(ValueError):
            LearningReport(
                video_id="video-1",
                performance_summary="Summary.",
                strengths=[
                    LearningInsight(
                        "Retention",
                        "Strong retention.",
                        "Watch percentage.",
                        "Repeat structure.",
                        0.8,
                    ),
                ],
                weaknesses=[],
                experiments=[],
                recommended_actions=["Action"],
                generated_by="mock",
            )

    def test_recommended_actions_must_not_be_empty(self) -> None:
        """LearningReport requires recommended actions."""
        with self.assertRaises(ValueError):
            LearningReport(
                video_id="video-1",
                performance_summary="Summary.",
                strengths=[
                    LearningInsight(
                        "Retention",
                        "Strong retention.",
                        "Watch percentage.",
                        "Repeat structure.",
                        0.8,
                    ),
                ],
                weaknesses=[],
                experiments=["Experiment"],
                recommended_actions=[],
                generated_by="mock",
            )

    def test_learning_report_to_markdown(self) -> None:
        """LearningReport can be rendered as Markdown."""
        agent = LearningAgent()
        task = create_learning_task()

        report = agent.run(task)

        markdown = report.to_markdown()
        self.assertIn("# Learning Report: video-1", markdown)
        self.assertIn("Strengths", markdown)
        self.assertIn("Experiments", markdown)

    def test_llm_failure_sets_task_failed(self) -> None:
        """LLM errors move the task to FAILED."""
        agent = LearningAgent(tools=[LLMTool(provider=FailingLearningLLMProvider())])
        task = create_learning_task()

        with self.assertRaises(RuntimeError):
            agent.run(task)

        self.assertIs(task.status, TaskStatus.FAILED)
        self.assertEqual(task.error_message, "learning llm failed")

    def test_errors_are_propagated(self) -> None:
        """LLM errors are propagated unchanged."""
        agent = LearningAgent(tools=[LLMTool(provider=FailingLearningLLMProvider())])
        task = create_learning_task()

        with self.assertRaisesRegex(RuntimeError, "learning llm failed"):
            agent.run(task)


if __name__ == "__main__":
    unittest.main()
