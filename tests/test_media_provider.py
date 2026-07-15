"""Tests for media provider contracts and the deterministic mock provider."""

import copy
import unittest

from engine.media.asset import MediaAsset, MediaAssetType
from engine.media.providers.base import MediaProvider, MediaProviderError
from engine.media.providers.mock_provider import MockVideoProvider
from engine.media.render_job import RenderJob
from engine.media.render_plan import RenderScene, VideoProductionPlan


def create_render_job() -> RenderJob:
    """Create a pending render job for provider tests."""
    scenes = [
        RenderScene(
            scene_number=1,
            duration_seconds=12.0,
            camera_instruction="Push in",
            visual_instruction="Show the workflow",
            voice_instruction="Explain the problem",
            music_instruction="Low pulse",
            transition="Cut",
        ),
        RenderScene(
            scene_number=2,
            duration_seconds=18.0,
            camera_instruction="Static close-up",
            visual_instruction="Show the result",
            voice_instruction="Explain the outcome",
            music_instruction="Build energy",
            transition="Fade",
        ),
    ]
    plan = VideoProductionPlan(
        plan_id="plan-ai-agents",
        title="AI Agents Workflow",
        target_platform="YouTube Shorts",
        scenes=scenes,
        summary="A deterministic short-form production plan.",
    )
    return RenderJob(
        job_id="render-ai-agents",
        plan=plan,
        provider="mock-video",
    )


def create_asset() -> MediaAsset:
    """Create a valid asset for render job transitions."""
    return MediaAsset(
        asset_id="asset-existing",
        asset_type=MediaAssetType.VIDEO,
        name="Existing video",
        description="Existing rendered asset.",
        provider="test",
        format="mp4",
    )


class BrokenMediaProvider(MediaProvider):
    """Provider that exposes deterministic internal failures."""

    def __init__(self) -> None:
        """Create a broken video provider."""
        super().__init__("broken", (MediaAssetType.VIDEO,))

    def _render(self, job: RenderJob) -> MediaAsset:
        """Raise a provider implementation failure."""
        del job
        msg = "render implementation failed"
        raise RuntimeError(msg)


class UnsupportedMediaProvider(MediaProvider):
    """Provider without video support for validation tests."""

    def __init__(self, provider_id: str = "image-only") -> None:
        """Create an image-only provider."""
        super().__init__(provider_id, (MediaAssetType.IMAGE,))

    def _render(self, job: RenderJob) -> MediaAsset:
        """Return an image asset if validation were bypassed."""
        return MediaAsset(
            asset_id=f"image-{job.job_id}",
            asset_type=MediaAssetType.IMAGE,
            name=job.plan.title,
            description=job.plan.summary,
            provider=self.provider_id,
            format="png",
        )


class MediaProviderTestCase(unittest.TestCase):
    """Tests for MediaProvider and MockVideoProvider."""

    def test_provider_id_must_not_be_empty(self) -> None:
        """Providers reject empty IDs."""
        with self.assertRaises(ValueError):
            UnsupportedMediaProvider("   ")

    def test_mock_provider_supports_video(self) -> None:
        """The mock provider declares video support only."""
        provider = MockVideoProvider()

        self.assertEqual(provider.provider_id, "mock-video")
        self.assertEqual(
            provider.supported_asset_types,
            (MediaAssetType.VIDEO,),
        )

    def test_pending_render_job_is_accepted(self) -> None:
        """A pending render job produces a video asset."""
        asset = MockVideoProvider().render(create_render_job())

        self.assertIs(asset.asset_type, MediaAssetType.VIDEO)

    def test_running_render_job_is_accepted_for_render_service_use(self) -> None:
        """A running job can be rendered after a service starts it."""
        running_job = create_render_job()
        running_job.start()

        asset = MockVideoProvider().render(running_job)

        self.assertIs(asset.asset_type, MediaAssetType.VIDEO)

    def test_finished_render_jobs_are_rejected(self) -> None:
        """Completed and failed jobs cannot be rendered."""

        completed_job = create_render_job()
        completed_job.start()
        completed_job.complete(create_asset())

        failed_job = create_render_job()
        failed_job.start()
        failed_job.fail("render failed")

        provider = MockVideoProvider()
        for job in (completed_job, failed_job):
            with self.subTest(status=job.status):
                with self.assertRaises(MediaProviderError):
                    provider.render(job)

    def test_provider_must_support_video(self) -> None:
        """Image-only providers cannot render video jobs."""
        with self.assertRaises(MediaProviderError):
            UnsupportedMediaProvider().render(create_render_job())

    def test_mock_output_is_deterministic(self) -> None:
        """Equivalent jobs produce equivalent assets."""
        provider = MockVideoProvider()

        first = provider.render(create_render_job())
        second = provider.render(create_render_job())

        self.assertEqual(first, second)

    def test_mock_asset_contains_render_metadata(self) -> None:
        """The mock asset records the required job and plan metadata."""
        asset = MockVideoProvider().render(create_render_job())

        self.assertEqual(asset.asset_id, "asset-render-ai-agents")
        self.assertEqual(asset.name, "AI Agents Workflow")
        self.assertEqual(asset.description, "A deterministic short-form production plan.")
        self.assertEqual(asset.provider, "mock-video")
        self.assertEqual(asset.format, "mp4")
        self.assertEqual(
            asset.metadata,
            {
                "render_job_id": "render-ai-agents",
                "plan_id": "plan-ai-agents",
                "target_platform": "YouTube Shorts",
                "total_duration_seconds": 30.0,
                "scene_count": 2,
            },
        )

    def test_mock_provider_does_not_mutate_render_job(self) -> None:
        """Rendering leaves the original render job unchanged."""
        job = create_render_job()
        original = copy.deepcopy(job)

        MockVideoProvider().render(job)

        self.assertEqual(job, original)

    def test_provider_errors_are_wrapped_with_original_cause(self) -> None:
        """Provider implementation errors retain their original cause."""
        with self.assertRaises(MediaProviderError) as context:
            BrokenMediaProvider().render(create_render_job())

        self.assertIsInstance(context.exception.__cause__, RuntimeError)
        self.assertEqual(
            str(context.exception.__cause__),
            "render implementation failed",
        )


if __name__ == "__main__":
    unittest.main()
