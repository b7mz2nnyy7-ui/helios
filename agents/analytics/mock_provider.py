"""Mock analytics provider for Insight."""

from dataclasses import dataclass

from agents.analytics.models import AnalyticsReport, PlatformMetrics
from engine.llm.models import LLMRequest
from engine.media.render_job import RenderJob


@dataclass
class MockAnalyticsProvider:
    """Deterministic analytics provider for tests."""

    provider_id: str = "mock"
    model: str = "mock-analytics"

    def analyze(
        self,
        request: LLMRequest,
        video_id: str,
        render_job: RenderJob,
        platforms: list[str],
    ) -> AnalyticsReport:
        """Return deterministic analytics for the requested platforms."""
        metrics = [
            self._create_metrics(platform, index)
            for index, platform in enumerate(platforms)
        ]
        total_views = sum(metric.views for metric in metrics)
        total_engagement = sum(metric.engagement_total for metric in metrics)
        strongest_platform = max(metrics, key=lambda metric: metric.views).platform
        weakest_platform = min(metrics, key=lambda metric: metric.views).platform
        return AnalyticsReport(
            report_id=f"analytics-{video_id}",
            video_id=video_id,
            metrics=metrics,
            total_views=total_views,
            total_engagement=total_engagement,
            strongest_platform=strongest_platform,
            weakest_platform=weakest_platform,
            summary=(
                f"Deterministic analytics for {video_id} from "
                f"{render_job.provider}: {request.user_prompt}"
            ),
            generated_by=f"{self.provider_id}:{self.model}",
        )

    def _create_metrics(self, platform: str, index: int) -> PlatformMetrics:
        views = 1000 - (index * 250)
        likes = 120 - (index * 20)
        comments = 18 - (index * 3)
        shares = 32 - (index * 5)
        saves = 44 - (index * 4)
        return PlatformMetrics(
            platform=platform,
            views=max(views, 100),
            watch_time_seconds=2400.0 - (index * 300.0),
            average_watch_percentage=max(72.0 - (index * 8.0), 20.0),
            likes=max(likes, 10),
            comments=max(comments, 1),
            shares=max(shares, 1),
            saves=max(saves, 1),
            followers_gained=max(26 - (index * 4), 1),
            ctr=max(0.12 - (index * 0.02), 0.01),
            engagement_rate=max(0.18 - (index * 0.03), 0.01),
        )
