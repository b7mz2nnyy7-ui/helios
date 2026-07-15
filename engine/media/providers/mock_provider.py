"""Deterministic mock media provider for local development."""

from engine.media.asset import MediaAsset, MediaAssetType
from engine.media.providers.base import MediaProvider
from engine.media.render_job import RenderJob


class MockVideoProvider(MediaProvider):
    """Create deterministic video assets without rendering or I/O."""

    def __init__(self) -> None:
        """Create the local mock video provider."""
        super().__init__(
            provider_id="mock-video",
            supported_asset_types=(MediaAssetType.VIDEO,),
        )

    def _render(self, job: RenderJob) -> MediaAsset:
        """Return a deterministic asset describing the render job."""
        plan = job.plan
        return MediaAsset(
            asset_id=f"asset-{job.job_id}",
            asset_type=MediaAssetType.VIDEO,
            name=plan.title,
            description=plan.summary,
            provider=self.provider_id,
            format="mp4",
            metadata={
                "render_job_id": job.job_id,
                "plan_id": plan.plan_id,
                "target_platform": plan.target_platform,
                "total_duration_seconds": plan.total_duration_seconds,
                "scene_count": len(plan.scenes),
            },
        )
