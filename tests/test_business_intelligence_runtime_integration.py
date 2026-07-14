"""Runtime integration tests for Athena business intelligence agent."""

import unittest

from agents.analytics.models import AnalyticsReport, PlatformMetrics
from agents.business_intelligence.agent import BusinessIntelligenceAgent
from agents.business_intelligence.models import BusinessIntelligenceReport
from agents.learning.models import LearningInsight, LearningReport
from agents.prediction.models import Prediction, PredictionReport
from engine.runtime.capability import AgentCapability
from engine.runtime.runtime import HeliosRuntime
from engine.tasks.priority import TaskPriority
from engine.tasks.status import TaskStatus
from engine.tasks.task import Task


def create_business_task(payload: dict[str, object] | None = None) -> Task:
    """Create a business intelligence task for runtime integration tests."""
    task_payload = {
        "analytics_report": AnalyticsReport(
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
        ),
        "learning_report": LearningReport(
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
        ),
        "prediction_report": PredictionReport(
            predictions=[
                Prediction(
                    title="Checklist CTA Lift",
                    probability=0.82,
                    reasoning="Repeated learnings favor checklists.",
                    recommendation="Prioritize checklist-led variants.",
                ),
            ],
            summary="Forecast based on learnings.",
            generated_by="mock:mock-prediction-model",
        ),
    }
    return Task(
        task_id="business-task-1",
        title="Business Intelligence",
        description="Create management report.",
        priority=TaskPriority.MEDIUM,
        required_capability=AgentCapability.BUSINESS_INTELLIGENCE,
        payload=task_payload if payload is None else payload,
    )


class BusinessIntelligenceRuntimeIntegrationTestCase(unittest.TestCase):
    """Integration tests for Athena through HeliosRuntime."""

    def test_runtime_dispatches_business_task_to_athena(self) -> None:
        """Runtime can dispatch BUSINESS_INTELLIGENCE tasks to Athena."""
        runtime = HeliosRuntime()
        athena = BusinessIntelligenceAgent()
        task = create_business_task()
        runtime.register(athena)

        result = runtime.submit_task(task)

        self.assertIsInstance(result, BusinessIntelligenceReport)
        self.assertIs(result, task.result)
        self.assertIs(task.status, TaskStatus.COMPLETED)
        self.assertIs(athena.last_report, result)

    def test_runtime_returns_business_intelligence_report(self) -> None:
        """Runtime returns the BusinessIntelligenceReport from Athena."""
        runtime = HeliosRuntime()
        runtime.register(BusinessIntelligenceAgent())
        task = create_business_task()

        result = runtime.submit_task(task)

        self.assertIsInstance(result, BusinessIntelligenceReport)

    def test_runtime_propagates_athena_errors(self) -> None:
        """Runtime propagates Athena validation errors."""
        runtime = HeliosRuntime()
        runtime.register(BusinessIntelligenceAgent())
        task = create_business_task({"analytics_report": "invalid"})

        with self.assertRaises(ValueError):
            runtime.submit_task(task)

        self.assertIs(task.status, TaskStatus.FAILED)


if __name__ == "__main__":
    unittest.main()
