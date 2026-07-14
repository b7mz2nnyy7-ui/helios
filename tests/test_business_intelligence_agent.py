"""Tests for the Athena business intelligence agent."""

import unittest

from agents.analytics.models import AnalyticsReport, PlatformMetrics
from agents.business_intelligence.agent import BusinessIntelligenceAgent
from agents.business_intelligence.mock_llm_provider import MockBusinessLLMProvider
from agents.business_intelligence.models import (
    BusinessIntelligenceReport,
    BusinessOpportunity,
)
from agents.learning.models import LearningInsight, LearningReport
from agents.prediction.models import Prediction, PredictionReport
from engine.llm.base_provider import BaseLLMProvider
from engine.llm.models import LLMRequest, LLMResponse
from engine.runtime.capability import AgentCapability
from engine.tasks.priority import TaskPriority
from engine.tasks.status import TaskStatus
from engine.tasks.task import Task
from engine.tools.llm_tool import LLMTool


class RecordingBusinessLLMProvider(BaseLLMProvider):
    """LLM provider that records business intelligence requests."""

    def __init__(self) -> None:
        """Create a recording provider."""
        super().__init__(provider_id="recording", model="recording-business-model")
        self.received_request: LLMRequest | None = None
        self.response = MockBusinessLLMProvider(
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


class FailingBusinessLLMProvider(BaseLLMProvider):
    """LLM provider that always fails."""

    def __init__(self) -> None:
        """Create a failing provider."""
        super().__init__(provider_id="failing", model="failing-business-model")

    def generate(self, request: LLMRequest) -> LLMResponse:
        """Raise a runtime error."""
        msg = "business llm failed"
        raise RuntimeError(msg)


def create_analytics_report() -> AnalyticsReport:
    """Create an analytics report for business intelligence tests."""
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
        ],
        total_views=1750,
        total_engagement=396,
        strongest_platform="TikTok",
        weakest_platform="YouTube",
        summary="Deterministic analytics.",
        generated_by="mock:mock-analytics",
    )


def create_learning_report() -> LearningReport:
    """Create a learning report for business intelligence tests."""
    return LearningReport(
        video_id="video-1",
        performance_summary="Strong retention with platform variance.",
        strengths=[
            LearningInsight(
                category="Retention",
                observation="Opening structure held attention.",
                evidence="Watch percentage remained high.",
                recommendation="Reuse the hook structure.",
                confidence=0.86,
            ),
        ],
        weaknesses=[
            LearningInsight(
                category="Engagement Depth",
                observation="Saves and shares lagged.",
                evidence="Weakest platform engagement was lower.",
                recommendation="Add a save-worthy checklist.",
                confidence=0.79,
            ),
        ],
        experiments=["Test a checklist CTA against a question-led CTA."],
        recommended_actions=["Keep the current hook structure."],
        generated_by="mock:mock-learning-model",
    )


def create_prediction_report() -> PredictionReport:
    """Create a prediction report for business intelligence tests."""
    return PredictionReport(
        predictions=[
            Prediction(
                title="Checklist CTA Lift",
                probability=0.82,
                reasoning="Repeated learnings favor checklists.",
                recommendation="Prioritize checklist-led variants.",
            ),
            Prediction(
                title="Hook Contrast Improvement",
                probability=0.76,
                reasoning="Contrast improves retention.",
                recommendation="Test sharper opening contrast.",
            ),
        ],
        summary="Forecast based on learnings.",
        generated_by="mock:mock-prediction-model",
    )


def create_business_task(payload: dict[str, object] | None = None) -> Task:
    """Create a business intelligence task."""
    return Task(
        task_id="business-task-1",
        title="Business Intelligence",
        description="Create management report.",
        priority=TaskPriority.MEDIUM,
        required_capability=AgentCapability.BUSINESS_INTELLIGENCE,
        payload=(
            {
                "analytics_report": create_analytics_report(),
                "learning_report": create_learning_report(),
                "prediction_report": create_prediction_report(),
            }
            if payload is None
            else payload
        ),
    )


class BusinessIntelligenceAgentTestCase(unittest.TestCase):
    """Tests for BusinessIntelligenceAgent behavior."""

    def test_agent_has_business_intelligence_capability(self) -> None:
        """Athena declares the BUSINESS_INTELLIGENCE capability."""
        agent = BusinessIntelligenceAgent()

        self.assertTrue(agent.can_handle(AgentCapability.BUSINESS_INTELLIGENCE))

    def test_agent_name_is_athena(self) -> None:
        """Athena has the expected display name."""
        agent = BusinessIntelligenceAgent()

        self.assertEqual(agent.name, "Athena")

    def test_default_provider_exists(self) -> None:
        """Athena has a default LLM tool."""
        agent = BusinessIntelligenceAgent()

        self.assertIsInstance(agent.get_tool("llm"), LLMTool)

    def test_payload_validated_and_task_completed(self) -> None:
        """Valid business intelligence inputs complete the task."""
        agent = BusinessIntelligenceAgent()
        task = create_business_task()

        report = agent.run(task)

        self.assertIsInstance(report, BusinessIntelligenceReport)
        self.assertIs(task.status, TaskStatus.COMPLETED)

    def test_missing_analytics_report_raises_value_error(self) -> None:
        """Athena rejects missing AnalyticsReport payloads."""
        self._assert_missing_model_raises("analytics_report")

    def test_missing_learning_report_raises_value_error(self) -> None:
        """Athena rejects missing LearningReport payloads."""
        self._assert_missing_model_raises("learning_report")

    def test_missing_prediction_report_raises_value_error(self) -> None:
        """Athena rejects missing PredictionReport payloads."""
        self._assert_missing_model_raises("prediction_report")

    def test_task_result_and_last_report_are_identical(self) -> None:
        """Athena stores the report and writes it to the task."""
        agent = BusinessIntelligenceAgent()
        task = create_business_task()

        report = agent.run(task)

        self.assertIs(task.result, report)
        self.assertIs(agent.last_report, report)

    def test_report_contains_required_management_sections(self) -> None:
        """Athena creates all required business report sections."""
        agent = BusinessIntelligenceAgent()
        task = create_business_task()

        report = agent.run(task)

        self.assertGreaterEqual(len(report.kpis), 1)
        self.assertGreaterEqual(len(report.opportunities), 1)
        self.assertGreaterEqual(len(report.risks), 1)
        self.assertGreaterEqual(len(report.priorities), 1)

    def test_strongest_prediction_appears_in_executive_summary(self) -> None:
        """Athena references the strongest prediction in the executive summary."""
        agent = BusinessIntelligenceAgent()
        task = create_business_task()

        report = agent.run(task)

        self.assertIn("Checklist CTA Lift", report.executive_summary)

    def test_prompt_contains_analytics_learning_and_prediction(self) -> None:
        """Athena prompt contains all required management inputs."""
        provider = RecordingBusinessLLMProvider()
        agent = BusinessIntelligenceAgent(tools=[LLMTool(provider=provider)])
        task = create_business_task()

        agent.run(task)

        request = provider.received_request
        assert request is not None
        self.assertIn("Analytics", request.user_prompt)
        self.assertIn("Gesamtviews: 1750", request.user_prompt)
        self.assertIn("Engagement: 396", request.user_prompt)
        self.assertIn("Stärkste Plattform: TikTok", request.user_prompt)
        self.assertIn("Learning", request.user_prompt)
        self.assertIn("Strengths:", request.user_prompt)
        self.assertIn("Weaknesses:", request.user_prompt)
        self.assertIn("Recommendations:", request.user_prompt)
        self.assertIn("Prediction", request.user_prompt)
        self.assertIn("Checklist CTA Lift", request.user_prompt)
        self.assertIn("probability=0.82", request.user_prompt)
        self.assertIn("strongest_prediction: Checklist CTA Lift", request.user_prompt)
        self.assertEqual(
            request.system_prompt,
            "Athena erstellt Management-Reports für den CEO.",
        )

    def test_mock_provider_is_deterministic(self) -> None:
        """MockBusinessLLMProvider returns deterministic responses."""
        provider = MockBusinessLLMProvider()
        request = LLMRequest(system_prompt="Athena", user_prompt="Business data")

        first_response = provider.generate(request)
        second_response = provider.generate(request)

        self.assertEqual(first_response, second_response)
        self.assertEqual(first_response.provider, "mock")
        self.assertEqual(first_response.model, "mock-business-model")

    def test_probability_is_validated(self) -> None:
        """BusinessOpportunity validates probability."""
        with self.assertRaises(ValueError):
            BusinessOpportunity(
                title="Invalid",
                probability=1.1,
                impact="Too high.",
                recommendation="Reject.",
            )

    def test_report_to_markdown(self) -> None:
        """BusinessIntelligenceReport can be rendered as Markdown."""
        agent = BusinessIntelligenceAgent()
        task = create_business_task()

        report = agent.run(task)

        markdown = report.to_markdown()
        self.assertIn("# Business Intelligence Report", markdown)
        self.assertIn("Executive Summary", markdown)
        self.assertIn("Checklist CTA Lift", markdown)

    def test_llm_failure_sets_task_failed(self) -> None:
        """LLM errors move the task to FAILED."""
        agent = BusinessIntelligenceAgent(
            tools=[LLMTool(provider=FailingBusinessLLMProvider())],
        )
        task = create_business_task()

        with self.assertRaises(RuntimeError):
            agent.run(task)

        self.assertIs(task.status, TaskStatus.FAILED)
        self.assertEqual(task.error_message, "business llm failed")

    def test_errors_are_propagated(self) -> None:
        """LLM errors are propagated unchanged."""
        agent = BusinessIntelligenceAgent(
            tools=[LLMTool(provider=FailingBusinessLLMProvider())],
        )
        task = create_business_task()

        with self.assertRaisesRegex(RuntimeError, "business llm failed"):
            agent.run(task)

    def _assert_missing_model_raises(self, field_name: str) -> None:
        payload = {
            "analytics_report": create_analytics_report(),
            "learning_report": create_learning_report(),
            "prediction_report": create_prediction_report(),
        }
        payload[field_name] = "invalid"
        agent = BusinessIntelligenceAgent()
        task = create_business_task(payload)

        with self.assertRaises(ValueError):
            agent.run(task)


if __name__ == "__main__":
    unittest.main()
