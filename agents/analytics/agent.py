"""Insight analytics agent."""

from typing import Protocol

from agents.analytics.mock_provider import MockAnalyticsProvider
from agents.analytics.models import AnalyticsReport
from engine.llm.models import LLMRequest
from engine.media.render_job import RenderJob
from engine.runtime.base_agent import BaseAgent
from engine.runtime.capability import AgentCapability
from engine.tasks.status import TaskStatus
from engine.tasks.task import Task


class AnalyticsProvider(Protocol):
    """Provider protocol for analytics data."""

    provider_id: str
    model: str

    def analyze(
        self,
        request: LLMRequest,
        video_id: str,
        render_job: RenderJob,
        platforms: list[str],
    ) -> AnalyticsReport:
        """Return an analytics report for the given video."""


class AnalyticsAgent(BaseAgent):
    """Insight agent for creating provider-neutral analytics reports."""

    provider: AnalyticsProvider
    last_report: AnalyticsReport | None

    def __init__(self, provider: AnalyticsProvider | None = None) -> None:
        """Create the Insight analytics agent."""
        super().__init__(
            agent_id="analytics",
            name="Insight",
            capabilities={AgentCapability.ANALYTICS},
        )
        self.provider = provider or MockAnalyticsProvider()
        self.last_report = None

    def run(self, task: Task) -> AnalyticsReport:
        """Create an analytics report for published content."""
        if task.required_capability is not AgentCapability.ANALYTICS:
            msg = "AnalyticsAgent can only handle ANALYTICS tasks."
            raise ValueError(msg)

        task.start()
        try:
            video_id = self._get_video_id(task.payload.get("video_id"))
            render_job = self._get_render_job(task.payload.get("render_job"))
            platforms = self._get_platforms(task.payload.get("platforms"))
            request = self._create_request(video_id, render_job, platforms)
            report = self.provider.analyze(
                request,
                video_id,
                render_job,
                platforms,
            )
            self.last_report = report
            task.complete(report)
            return report
        except Exception as error:
            if task.status is TaskStatus.RUNNING:
                task.fail(str(error))
            raise

    def _get_video_id(self, value: object) -> str:
        if not isinstance(value, str) or not value.strip():
            msg = "video_id must be a non-empty string."
            raise ValueError(msg)

        return value.strip()

    def _get_render_job(self, value: object) -> RenderJob:
        if not isinstance(value, RenderJob):
            msg = "render_job must be a RenderJob."
            raise ValueError(msg)

        return value

    def _get_platforms(self, value: object) -> list[str]:
        if value is None:
            return ["TikTok", "YouTube"]

        if not isinstance(value, list) or not all(
            isinstance(platform, str) and platform.strip()
            for platform in value
        ):
            msg = "platforms must be a list of non-empty strings."
            raise ValueError(msg)

        return [platform.strip() for platform in value]

    def _create_request(
        self,
        video_id: str,
        render_job: RenderJob,
        platforms: list[str],
    ) -> LLMRequest:
        return LLMRequest(
            system_prompt="Insight analysiert die Performance veröffentlichter Inhalte.",
            user_prompt=(
                f"Video ID: {video_id}\n"
                f"Provider: {render_job.provider}\n"
                f"Target Platforms: {', '.join(platforms)}"
            ),
        )
