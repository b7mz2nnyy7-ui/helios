"""Runtime integration tests for Mentor learning agent."""

import unittest

from agents.analytics.models import AnalyticsReport, PlatformMetrics
from agents.learning.agent import LearningAgent
from agents.learning.models import LearningReport
from engine.runtime.capability import AgentCapability
from engine.runtime.runtime import HeliosRuntime
from engine.tasks.priority import TaskPriority
from engine.tasks.status import TaskStatus
from engine.tasks.task import Task


def create_analytics_report() -> AnalyticsReport:
    """Create an analytics report for runtime integration tests."""
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
        total_views=1000,
        total_engagement=214,
        strongest_platform="TikTok",
        weakest_platform="TikTok",
        summary="Deterministic analytics.",
        generated_by="mock:mock-analytics",
    )


def create_learning_task(payload: dict[str, object] | None = None) -> Task:
    """Create a learning task for runtime integration tests."""
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


class LearningRuntimeIntegrationTestCase(unittest.TestCase):
    """Integration tests for Mentor through HeliosRuntime."""

    def test_runtime_dispatches_learning_task_to_mentor(self) -> None:
        """Runtime can dispatch LEARNING tasks to Mentor."""
        runtime = HeliosRuntime()
        mentor = LearningAgent()
        task = create_learning_task()
        runtime.register(mentor)

        result = runtime.submit_task(task)

        self.assertIsInstance(result, LearningReport)
        self.assertIs(result, task.result)
        self.assertIs(task.status, TaskStatus.COMPLETED)
        self.assertIs(mentor.last_learning_report, result)

    def test_runtime_returns_learning_report(self) -> None:
        """Runtime returns the LearningReport from Mentor."""
        runtime = HeliosRuntime()
        runtime.register(LearningAgent())
        task = create_learning_task()

        result = runtime.submit_task(task)

        self.assertIsInstance(result, LearningReport)

    def test_runtime_propagates_mentor_errors(self) -> None:
        """Runtime propagates Mentor validation errors."""
        runtime = HeliosRuntime()
        runtime.register(LearningAgent())
        task = create_learning_task({"analytics_report": "invalid"})

        with self.assertRaises(ValueError):
            runtime.submit_task(task)

        self.assertIs(task.status, TaskStatus.FAILED)


if __name__ == "__main__":
    unittest.main()
