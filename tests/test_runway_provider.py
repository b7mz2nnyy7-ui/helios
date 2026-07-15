"""Tests for the structural Runway video provider adapter."""

import copy
import socket
import unittest
from pathlib import Path
from unittest.mock import patch

from engine.media.asset import MediaAsset, MediaAssetType
from engine.media.providers.base import MediaProviderError
from engine.media.providers.config import ProviderConfig
from engine.media.providers.registry import MediaProviderRegistry
from engine.media.render_job import RenderJob, RenderJobStatus
from engine.media.render_plan import RenderScene, VideoProductionPlan
from engine.media.render_service import RenderService
from integrations.runway.client import RunwayClient
from integrations.runway.models import RunwayGenerationRequest, RunwayTask
from integrations.runway.provider import RunwayVideoProvider, build_runway_prompt
from tests.test_runway_client import RecordingRunwayTransport


def create_plan() -> VideoProductionPlan:
    """Create a multi-scene production plan for Runway tests."""
    return VideoProductionPlan(
        plan_id="plan-runway",
        title="Runway Product Story",
        target_platform="TikTok",
        scenes=[
            RenderScene(
                scene_number=1,
                duration_seconds=5.0,
                camera_instruction="Slow push in",
                visual_instruction="Show the product dashboard",
                voice_instruction="Introduce the core problem",
                music_instruction="Minimal electronic pulse",
                transition="Hard cut",
            ),
            RenderScene(
                scene_number=2,
                duration_seconds=5.0,
                camera_instruction="Overhead tracking shot",
                visual_instruction="Show the automated workflow",
                voice_instruction="Explain the transformation",
                music_instruction="Build rhythmic energy",
                transition="Match cut",
            ),
        ],
        summary="A deterministic Runway production plan.",
    )


def create_job() -> RenderJob:
    """Create a pending Runway render job."""
    return RenderJob(
        job_id="render-runway",
        plan=create_plan(),
        provider="runway",
    )


def create_task(
    status: str = "SUCCEEDED",
    output_urls: tuple[str, ...] = ("https://example.invalid/runway.mp4",),
) -> RunwayTask:
    """Create a Runway task response."""
    return RunwayTask(
        task_id="runway-task-42",
        status=status,
        output_urls=output_urls,
    )


def create_provider(
    task: RunwayTask | None = None,
) -> tuple[RunwayVideoProvider, RecordingRunwayTransport]:
    """Create a provider with an in-memory recording transport."""
    transport = RecordingRunwayTransport(task or create_task())
    client = RunwayClient(
        ProviderConfig(
            provider_id="runway",
            api_key="runway-secret",
            model="gen4.5",
        ),
        transport,
    )
    return RunwayVideoProvider(client), transport


def create_asset() -> MediaAsset:
    """Create an asset for completed render-job validation."""
    return MediaAsset(
        asset_id="existing",
        asset_type=MediaAssetType.VIDEO,
        name="Existing",
        description="Existing asset.",
        provider="runway",
        format="mp4",
    )


class RunwayVideoProviderTestCase(unittest.TestCase):
    """Tests for RunwayVideoProvider prompt and asset mapping."""

    def test_provider_supports_video(self) -> None:
        """Runway declares its provider ID and video support."""
        provider, _ = create_provider()

        self.assertEqual(provider.provider_id, "runway")
        self.assertEqual(provider.supported_asset_types, (MediaAssetType.VIDEO,))

    def test_prompt_contains_plan_and_every_scene(self) -> None:
        """Prompt generation includes all plan and scene instructions."""
        prompt = build_runway_prompt(create_plan())

        for value in (
            "Runway Product Story",
            "TikTok",
            "A deterministic Runway production plan.",
            "Scene 1",
            "Scene 2",
            "Duration: 5.0s",
            "Slow push in",
            "Show the product dashboard",
            "Introduce the core problem",
            "Minimal electronic pulse",
            "Hard cut",
            "Overhead tracking shot",
            "Show the automated workflow",
            "Explain the transformation",
            "Build rhythmic energy",
            "Match cut",
        ):
            self.assertIn(value, prompt)

    def test_provider_does_not_mutate_render_job(self) -> None:
        """Direct provider rendering leaves the render job unchanged."""
        provider, _ = create_provider()
        job = create_job()
        original = copy.deepcopy(job)

        provider.render(job)

        self.assertEqual(job, original)

    def test_completed_task_creates_video_asset(self) -> None:
        """A completed task maps to a provider-neutral video asset."""
        provider, transport = create_provider()

        asset = provider.render(create_job())

        self.assertEqual(len(transport.create_calls), 1)
        self.assertEqual(transport.get_calls, [])
        self.assertEqual(asset.asset_id, "asset-runway-runway-task-42")
        self.assertIs(asset.asset_type, MediaAssetType.VIDEO)
        self.assertEqual(asset.provider, "runway")
        self.assertEqual(asset.format, "mp4")

    def test_asset_metadata_is_complete(self) -> None:
        """Runway assets retain all required task and plan metadata."""
        provider, _ = create_provider()

        asset = provider.render(create_job())

        self.assertEqual(
            asset.metadata,
            {
                "runway_task_id": "runway-task-42",
                "output_url": "https://example.invalid/runway.mp4",
                "plan_id": "plan-runway",
                "render_job_id": "render-runway",
                "target_platform": "TikTok",
                "total_duration_seconds": 10.0,
                "scene_count": 2,
                "model": "gen4.5",
                "poll_count": 0,
                "polling_elapsed_seconds": 0.0,
            },
        )

    def test_create_request_uses_deterministic_plan_values(self) -> None:
        """Provider forwards model, duration and generated prompt once."""
        provider, transport = create_provider()

        provider.render(create_job())

        request = transport.create_calls[0][0]
        self.assertIsInstance(request, RunwayGenerationRequest)
        self.assertEqual(request.model, "gen4.5")
        self.assertEqual(request.duration_seconds, 10.0)
        self.assertEqual(request.ratio, "768:1280")
        self.assertIsNone(request.seed)

    def test_unfinished_task_is_rejected(self) -> None:
        """Providers do not poll unfinished tasks."""
        provider, transport = create_provider(create_task(status="PENDING"))

        with self.assertRaises(MediaProviderError):
            provider.render(create_job())

        self.assertEqual(len(transport.create_calls), 1)
        self.assertEqual(transport.get_calls, [])

    def test_missing_output_url_is_rejected(self) -> None:
        """Completed tasks require exactly one output URL."""
        provider, _ = create_provider(create_task(output_urls=()))

        with self.assertRaises(MediaProviderError):
            provider.render(create_job())

    def test_multiple_output_urls_are_rejected(self) -> None:
        """Multiple outputs are rejected to keep asset mapping deterministic."""
        provider, _ = create_provider(
            create_task(
                output_urls=(
                    "https://example.invalid/first.mp4",
                    "https://example.invalid/second.mp4",
                ),
            ),
        )

        with self.assertRaises(MediaProviderError):
            provider.render(create_job())

    def test_finished_render_job_status_is_rejected(self) -> None:
        """Finished RenderJobs cannot be submitted directly to the provider."""
        provider, transport = create_provider()
        job = create_job()
        job.start()
        job.complete(create_asset())

        with self.assertRaises(MediaProviderError):
            provider.render(job)

        self.assertEqual(transport.create_calls, [])

    def test_provider_integrates_with_render_service(self) -> None:
        """RenderService alone controls the RenderJob lifecycle."""
        provider, _ = create_provider()
        registry = MediaProviderRegistry()
        registry.register(provider)
        job = create_job()

        asset = RenderService(registry).render(job)

        self.assertIs(job.status, RenderJobStatus.COMPLETED)
        self.assertIs(job.result_asset, asset)

    def test_provider_performs_no_file_network_polling_or_download(self) -> None:
        """Recording transport keeps provider rendering local and cost-free."""
        provider, transport = create_provider()

        with (
            patch.object(socket, "socket", side_effect=AssertionError("network")),
            patch.object(Path, "open", side_effect=AssertionError("file")),
            patch.object(Path, "write_bytes", side_effect=AssertionError("download")),
        ):
            asset = provider.render(create_job())

        self.assertIs(asset.asset_type, MediaAssetType.VIDEO)
        self.assertEqual(len(transport.create_calls), 1)
        self.assertEqual(transport.get_calls, [])


if __name__ == "__main__":
    unittest.main()
