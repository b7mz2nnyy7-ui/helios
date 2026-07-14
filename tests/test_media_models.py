"""Tests for provider-neutral media models."""

import unittest
from datetime import UTC

from engine.media.asset import MediaAsset, MediaAssetType
from engine.media.render_job import RenderJob, RenderJobStatus
from engine.media.render_plan import RenderScene, VideoProductionPlan


def create_asset() -> MediaAsset:
    """Create a valid media asset for tests."""
    return MediaAsset(
        asset_id="asset-1",
        asset_type=MediaAssetType.VIDEO,
        name="Rendered Video",
        description="A rendered video asset.",
        provider="mock",
        format="mp4",
        metadata={"duration": 30},
    )


def create_scene(scene_number: int = 1, duration_seconds: float = 10.0) -> RenderScene:
    """Create a valid render scene for tests."""
    return RenderScene(
        scene_number=scene_number,
        duration_seconds=duration_seconds,
        camera_instruction="Push in",
        visual_instruction="Show product UI",
        voice_instruction="Narrate the key point",
        music_instruction="Low pulse",
        transition="Cut",
    )


def create_plan() -> VideoProductionPlan:
    """Create a valid production plan for tests."""
    return VideoProductionPlan(
        plan_id="plan-1",
        title="AI Workflow Video",
        target_platform="YouTube Shorts",
        scenes=[
            create_scene(1, 8.0),
            create_scene(2, 12.0),
            create_scene(3, 10.0),
        ],
        summary="A short-form production plan.",
    )


class MediaModelsTestCase(unittest.TestCase):
    """Tests for media asset, plan and render job models."""

    def test_asset_type_values(self) -> None:
        """MediaAssetType exposes the expected values."""
        self.assertEqual(MediaAssetType.IMAGE.value, "IMAGE")
        self.assertEqual(MediaAssetType.VIDEO.value, "VIDEO")
        self.assertEqual(MediaAssetType.AUDIO.value, "AUDIO")
        self.assertEqual(MediaAssetType.THUMBNAIL.value, "THUMBNAIL")
        self.assertEqual(MediaAssetType.SUBTITLE.value, "SUBTITLE")

    def test_asset_validation_accepts_valid_asset(self) -> None:
        """A valid asset is accepted."""
        asset = create_asset()

        self.assertEqual(asset.asset_id, "asset-1")
        self.assertEqual(asset.asset_type, MediaAssetType.VIDEO)

    def test_asset_validation_rejects_empty_required_fields(self) -> None:
        """MediaAsset rejects empty required values."""
        with self.assertRaises(ValueError):
            MediaAsset(
                asset_id="",
                asset_type=MediaAssetType.IMAGE,
                name="Image",
                description="Preview image.",
                provider="mock",
                format="png",
            )

        with self.assertRaises(ValueError):
            MediaAsset(
                asset_id="asset-1",
                asset_type=MediaAssetType.IMAGE,
                name="",
                description="Preview image.",
                provider="mock",
                format="png",
            )

        with self.assertRaises(ValueError):
            MediaAsset(
                asset_id="asset-1",
                asset_type=MediaAssetType.IMAGE,
                name="Image",
                description="Preview image.",
                provider="",
                format="png",
            )

        with self.assertRaises(ValueError):
            MediaAsset(
                asset_id="asset-1",
                asset_type=MediaAssetType.IMAGE,
                name="Image",
                description="Preview image.",
                provider="mock",
                format="",
            )

    def test_asset_validation_rejects_non_dictionary_metadata(self) -> None:
        """MediaAsset rejects non-dictionary metadata."""
        with self.assertRaises(ValueError):
            MediaAsset(
                asset_id="asset-1",
                asset_type=MediaAssetType.IMAGE,
                name="Image",
                description="Preview image.",
                provider="mock",
                format="png",
                metadata="invalid",  # type: ignore[arg-type]
            )

    def test_scene_validation_accepts_valid_scene(self) -> None:
        """A valid render scene is accepted."""
        scene = create_scene()

        self.assertEqual(scene.scene_number, 1)
        self.assertEqual(scene.duration_seconds, 10.0)

    def test_scene_validation_rejects_invalid_values(self) -> None:
        """RenderScene rejects invalid scene number and duration."""
        with self.assertRaises(ValueError):
            create_scene(scene_number=0)

        with self.assertRaises(ValueError):
            create_scene(duration_seconds=0.0)

    def test_plan_validation_accepts_valid_plan(self) -> None:
        """A valid production plan is accepted."""
        plan = create_plan()

        self.assertEqual(plan.plan_id, "plan-1")
        self.assertEqual(plan.total_duration_seconds, 30.0)

    def test_plan_validation_rejects_empty_scenes(self) -> None:
        """VideoProductionPlan requires at least one scene."""
        with self.assertRaises(ValueError):
            VideoProductionPlan(
                plan_id="plan-1",
                title="Invalid",
                target_platform="YouTube Shorts",
                scenes=[],
                summary="Invalid plan.",
            )

    def test_plan_to_markdown(self) -> None:
        """VideoProductionPlan can be rendered as Markdown."""
        plan = create_plan()

        markdown = plan.to_markdown()

        self.assertIn("# AI Workflow Video", markdown)
        self.assertIn("Scene 1", markdown)
        self.assertIn("Total Duration: 30.0s", markdown)

    def test_job_lifecycle(self) -> None:
        """RenderJob follows the expected lifecycle."""
        job = RenderJob(job_id="job-1", plan=create_plan(), provider="mock")

        self.assertEqual(job.status, RenderJobStatus.PENDING)
        job.start()
        self.assertEqual(job.status, RenderJobStatus.RUNNING)

    def test_invalid_transition(self) -> None:
        """RenderJob rejects invalid status transitions."""
        job = RenderJob(job_id="job-1", plan=create_plan(), provider="mock")

        with self.assertRaises(ValueError):
            job.complete(create_asset())

    def test_created_at_uses_utc(self) -> None:
        """RenderJob timestamps use UTC."""
        job = RenderJob(job_id="job-1", plan=create_plan(), provider="mock")

        self.assertEqual(job.created_at.tzinfo, UTC)

    def test_complete_stores_asset(self) -> None:
        """Completing a job stores the result asset."""
        job = RenderJob(job_id="job-1", plan=create_plan(), provider="mock")
        asset = create_asset()

        job.start()
        job.complete(asset)

        self.assertEqual(job.status, RenderJobStatus.COMPLETED)
        self.assertIs(job.result_asset, asset)
        self.assertIsNone(job.error_message)

    def test_failed_stores_error(self) -> None:
        """Failing a job stores the error message."""
        job = RenderJob(job_id="job-1", plan=create_plan(), provider="mock")

        job.start()
        job.fail("render failed")

        self.assertEqual(job.status, RenderJobStatus.FAILED)
        self.assertEqual(job.error_message, "render failed")


if __name__ == "__main__":
    unittest.main()
