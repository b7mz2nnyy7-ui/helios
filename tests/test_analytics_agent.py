"""Tests for the Insight analytics agent."""

import unittest

from agents.analytics.agent import AnalyticsAgent
from agents.analytics.mock_provider import MockAnalyticsProvider
from agents.analytics.models import AnalyticsReport, PlatformMetrics
from engine.llm.models import LLMRequest
from engine.media.render_job import RenderJob
from engine.media.render_plan import RenderScene, VideoProductionPlan
from engine.runtime.capability import AgentCapability
from engine.tasks.priority import TaskPriority
from engine.tasks.status import TaskStatus
from engine.tasks.task import Task


class RecordingAnalyticsProvider(MockAnalyticsProvider):
    """Analytics provider that records requests."""

    def __init__(self) -> None:
        """Create a recording provider."""
        super().__init__(provider_id="recording", model="recording-analytics")
        self.received_request: LLMRequest | None = None

    def analyze(
        self,
        request: LLMRequest,
        video_id: str,
        render_job: RenderJob,
        platforms: list[str],
    ) -> AnalyticsReport:
        """Record the request and return deterministic analytics."""
        self.received_request = request
        return super().analyze(request, video_id, render_job, platforms)


class FailingAnalyticsProvider(MockAnalyticsProvider):
    """Analytics provider that always fails."""

    def analyze(
        self,
        request: LLMRequest,
        video_id: str,
        render_job: RenderJob,
        platforms: list[str],
    ) -> AnalyticsReport:
        """Raise a runtime error."""
        msg = "analytics provider failed"
        raise RuntimeError(msg)


def create_render_job() -> RenderJob:
    """Create a render job for analytics tests."""
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


def create_analytics_task(
    video_id: object = "video-1",
    render_job: object | None = None,
    platforms: object | None = None,
) -> Task:
    """Create an analytics task."""
    payload: dict[str, object] = {
        "video_id": video_id,
        "render_job": create_render_job() if render_job is None else render_job,
    }
    if platforms is not None:
        payload["platforms"] = platforms

    return Task(
        task_id="analytics-task-1",
        title="Analytics",
        description="Analyze published content.",
        priority=TaskPriority.MEDIUM,
        required_capability=AgentCapability.ANALYTICS,
        payload=payload,
    )


class AnalyticsAgentTestCase(unittest.TestCase):
    """Tests for AnalyticsAgent behavior."""

    def test_agent_has_analytics_capability(self) -> None:
        """Insight declares the ANALYTICS capability."""
        agent = AnalyticsAgent()

        self.assertTrue(agent.can_handle(AgentCapability.ANALYTICS))

    def test_agent_name_is_insight(self) -> None:
        """Insight has the expected display name."""
        agent = AnalyticsAgent()

        self.assertEqual(agent.name, "Insight")

    def test_default_provider_exists(self) -> None:
        """Insight has a default provider."""
        agent = AnalyticsAgent()

        self.assertIsInstance(agent.provider, MockAnalyticsProvider)

    def test_payload_validated_and_task_completed(self) -> None:
        """Valid analytics payloads complete the task."""
        agent = AnalyticsAgent()
        task = create_analytics_task()

        report = agent.run(task)

        self.assertIsInstance(report, AnalyticsReport)
        self.assertIs(task.status, TaskStatus.COMPLETED)

    def test_missing_video_id_raises_value_error(self) -> None:
        """Insight rejects missing video IDs."""
        agent = AnalyticsAgent()
        task = create_analytics_task(video_id="")

        with self.assertRaises(ValueError):
            agent.run(task)

    def test_missing_render_job_raises_value_error(self) -> None:
        """Insight rejects missing RenderJob payloads."""
        agent = AnalyticsAgent()
        task = create_analytics_task(render_job="invalid")

        with self.assertRaises(ValueError):
            agent.run(task)

    def test_task_result_and_last_report_are_identical(self) -> None:
        """Insight stores the report and writes it to the task."""
        agent = AnalyticsAgent()
        task = create_analytics_task()

        report = agent.run(task)

        self.assertIs(task.result, report)
        self.assertIs(agent.last_report, report)

    def test_total_views_and_platform_ranking_are_correct(self) -> None:
        """Insight reports deterministic totals and platform ranking."""
        agent = AnalyticsAgent()
        task = create_analytics_task(platforms=["TikTok", "YouTube"])

        report = agent.run(task)

        self.assertEqual(report.total_views, 1750)
        self.assertEqual(report.strongest_platform, "TikTok")
        self.assertEqual(report.weakest_platform, "YouTube")
        self.assertEqual(report.total_engagement, 396)

    def test_prompt_contains_video_provider_and_platforms(self) -> None:
        """Insight prompt contains video ID, provider and platforms."""
        provider = RecordingAnalyticsProvider()
        agent = AnalyticsAgent(provider=provider)
        task = create_analytics_task(platforms=["TikTok", "YouTube", "Instagram"])

        agent.run(task)

        request = provider.received_request
        assert request is not None
        self.assertIn("Video ID: video-1", request.user_prompt)
        self.assertIn("Provider: mock-render-provider", request.user_prompt)
        self.assertIn("Target Platforms: TikTok, YouTube, Instagram", request.user_prompt)
        self.assertEqual(
            request.system_prompt,
            "Insight analysiert die Performance veröffentlichter Inhalte.",
        )

    def test_runtime_defaults_platforms(self) -> None:
        """Insight defaults platforms when none are provided."""
        agent = AnalyticsAgent()
        task = create_analytics_task()

        report = agent.run(task)

        self.assertEqual([metric.platform for metric in report.metrics], ["TikTok", "YouTube"])

    def test_mock_provider_is_deterministic(self) -> None:
        """MockAnalyticsProvider returns deterministic reports."""
        provider = MockAnalyticsProvider()
        request = LLMRequest(system_prompt="Insight", user_prompt="Video ID: video-1")
        render_job = create_render_job()

        first_report = provider.analyze(request, "video-1", render_job, ["TikTok"])
        second_report = provider.analyze(request, "video-1", render_job, ["TikTok"])

        self.assertEqual(first_report.video_id, second_report.video_id)
        self.assertEqual(first_report.metrics, second_report.metrics)
        self.assertEqual(first_report.total_views, second_report.total_views)

    def test_validation_works(self) -> None:
        """Analytics models validate invalid values."""
        with self.assertRaises(ValueError):
            PlatformMetrics(
                platform="TikTok",
                views=-1,
                watch_time_seconds=0.0,
                average_watch_percentage=0.0,
                likes=0,
                comments=0,
                shares=0,
                saves=0,
                followers_gained=0,
                ctr=0.0,
                engagement_rate=0.0,
            )

        with self.assertRaises(ValueError):
            PlatformMetrics(
                platform="TikTok",
                views=1,
                watch_time_seconds=0.0,
                average_watch_percentage=101.0,
                likes=0,
                comments=0,
                shares=0,
                saves=0,
                followers_gained=0,
                ctr=0.0,
                engagement_rate=0.0,
            )

        with self.assertRaises(ValueError):
            AnalyticsReport(
                report_id="report-1",
                video_id="video-1",
                metrics=[],
                total_views=0,
                total_engagement=0,
                strongest_platform="",
                weakest_platform="",
                summary="Invalid.",
                generated_by="mock",
            )

    def test_report_to_markdown(self) -> None:
        """AnalyticsReport can be rendered as Markdown."""
        agent = AnalyticsAgent()
        task = create_analytics_task()

        report = agent.run(task)

        markdown = report.to_markdown()
        self.assertIn("# Analytics Report: video-1", markdown)
        self.assertIn("Total Views: 1750", markdown)
        self.assertIn("TikTok", markdown)

    def test_provider_failure_sets_task_failed(self) -> None:
        """Provider errors move the task to FAILED."""
        agent = AnalyticsAgent(provider=FailingAnalyticsProvider())
        task = create_analytics_task()

        with self.assertRaises(RuntimeError):
            agent.run(task)

        self.assertIs(task.status, TaskStatus.FAILED)
        self.assertEqual(task.error_message, "analytics provider failed")

    def test_errors_are_propagated(self) -> None:
        """Provider errors are propagated unchanged."""
        agent = AnalyticsAgent(provider=FailingAnalyticsProvider())
        task = create_analytics_task()

        with self.assertRaisesRegex(RuntimeError, "analytics provider failed"):
            agent.run(task)


if __name__ == "__main__":
    unittest.main()
