"""Runtime integration tests for Insight analytics agent."""

import unittest

from agents.analytics.agent import AnalyticsAgent
from agents.analytics.models import AnalyticsReport
from engine.media.render_job import RenderJob
from engine.media.render_plan import RenderScene, VideoProductionPlan
from engine.runtime.capability import AgentCapability
from engine.runtime.runtime import HeliosRuntime
from engine.tasks.priority import TaskPriority
from engine.tasks.status import TaskStatus
from engine.tasks.task import Task


def create_render_job() -> RenderJob:
    """Create a render job for runtime integration tests."""
    plan = VideoProductionPlan(
        plan_id="plan-1",
        title="AI Workflow Video",
        target_platform="Short-form vertical video",
        scenes=[
            RenderScene(
                scene_number=1,
                duration_seconds=10.0,
                camera_instruction="Push in",
                visual_instruction="Show UI",
                voice_instruction="Narrate clearly",
                music_instruction="Low pulse",
                transition="Cut",
            ),
        ],
        summary="Production plan.",
    )
    return RenderJob(job_id="render-1", plan=plan, provider="mock-render-provider")


def create_analytics_task(payload: dict[str, object] | None = None) -> Task:
    """Create an analytics task for runtime integration tests."""
    task_payload = {
        "video_id": "video-1",
        "render_job": create_render_job(),
    }
    return Task(
        task_id="analytics-task-1",
        title="Analytics",
        description="Analyze published content.",
        priority=TaskPriority.MEDIUM,
        required_capability=AgentCapability.ANALYTICS,
        payload=task_payload if payload is None else payload,
    )


class AnalyticsRuntimeIntegrationTestCase(unittest.TestCase):
    """Integration tests for Insight through HeliosRuntime."""

    def test_runtime_dispatches_analytics_task_to_insight(self) -> None:
        """Runtime can dispatch ANALYTICS tasks to Insight."""
        runtime = HeliosRuntime()
        insight = AnalyticsAgent()
        task = create_analytics_task()
        runtime.register(insight)

        result = runtime.submit_task(task)

        self.assertIsInstance(result, AnalyticsReport)
        self.assertIs(result, task.result)
        self.assertIs(task.status, TaskStatus.COMPLETED)
        self.assertIs(insight.last_report, result)

    def test_runtime_returns_analytics_report(self) -> None:
        """Runtime returns the AnalyticsReport from Insight."""
        runtime = HeliosRuntime()
        runtime.register(AnalyticsAgent())
        task = create_analytics_task()

        result = runtime.submit_task(task)

        self.assertIsInstance(result, AnalyticsReport)

    def test_runtime_propagates_insight_errors(self) -> None:
        """Runtime propagates Insight validation errors."""
        runtime = HeliosRuntime()
        runtime.register(AnalyticsAgent())
        task = create_analytics_task({"video_id": ""})

        with self.assertRaises(ValueError):
            runtime.submit_task(task)

        self.assertIs(task.status, TaskStatus.FAILED)


if __name__ == "__main__":
    unittest.main()
