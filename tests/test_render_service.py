"""Tests for synchronous media render orchestration."""

import socket
import unittest
from collections.abc import Mapping
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast
from unittest.mock import patch

from engine.media.asset import MediaAsset, MediaAssetType
from engine.media.providers.base import MediaProvider, MediaProviderError
from engine.media.providers.mock_provider import MockVideoProvider
from engine.media.providers.registry import MediaProviderRegistry
from engine.media.render_job import RenderJob, RenderJobStatus
from engine.media.render_plan import RenderScene, VideoProductionPlan
from engine.media.render_service import RenderService
from engine.media.storage import MediaStorage, MediaStorageError
from integrations.runway.http_transport import HTTPResponse


def create_render_job(provider: str = "mock-video") -> RenderJob:
    """Create a pending render job for service tests."""
    plan = VideoProductionPlan(
        plan_id="plan-service-test",
        title="Service Test Video",
        target_platform="YouTube Shorts",
        scenes=[
            RenderScene(
                scene_number=1,
                duration_seconds=10.0,
                camera_instruction="Push in",
                visual_instruction="Show the workflow",
                voice_instruction="Explain the workflow",
                music_instruction="Low pulse",
                transition="Cut",
            ),
            RenderScene(
                scene_number=2,
                duration_seconds=20.0,
                camera_instruction="Static close-up",
                visual_instruction="Show the outcome",
                voice_instruction="Explain the result",
                music_instruction="Build energy",
                transition="Fade",
            ),
        ],
        summary="A provider-neutral render service test plan.",
    )
    return RenderJob(
        job_id="render-service-test",
        plan=plan,
        provider=provider,
    )


def create_service(provider: MediaProvider | None = None) -> RenderService:
    """Create a service with one explicitly registered provider."""
    registry = MediaProviderRegistry()
    registry.register(provider or MockVideoProvider())
    return RenderService(registry)


class TrackingVideoProvider(MockVideoProvider):
    """Mock provider that records the status observed during rendering."""

    def __init__(self) -> None:
        """Create a tracking mock provider."""
        super().__init__()
        self.observed_statuses: list[RenderJobStatus] = []

    def _render(self, job: RenderJob) -> MediaAsset:
        """Record the job status and return the deterministic mock asset."""
        self.observed_statuses.append(job.status)
        return super()._render(job)


class UnsupportedProvider(MediaProvider):
    """Provider that does not support video assets."""

    def __init__(self) -> None:
        """Create an image-only provider."""
        super().__init__("image-only", (MediaAssetType.IMAGE,))

    def _render(self, job: RenderJob) -> MediaAsset:
        """Return an image asset if support validation is bypassed."""
        return create_image_asset(job, self.provider_id)


class WrongTypeProvider(MediaProvider):
    """Provider that returns an invalid runtime value."""

    def __init__(self) -> None:
        """Create an invalid result provider."""
        super().__init__("wrong-type", (MediaAssetType.VIDEO,))

    def _render(self, job: RenderJob) -> MediaAsset:
        """Return a value that is not a MediaAsset."""
        del job
        return cast(MediaAsset, object())


class NonVideoResultProvider(MediaProvider):
    """Video provider that incorrectly returns an image asset."""

    def __init__(self) -> None:
        """Create a provider with an invalid output asset type."""
        super().__init__("non-video-result", (MediaAssetType.VIDEO,))

    def _render(self, job: RenderJob) -> MediaAsset:
        """Return an image despite declaring video support."""
        return create_image_asset(job, self.provider_id)


class FailingProvider(MediaProvider):
    """Provider that fails during rendering."""

    def __init__(self) -> None:
        """Create a deterministic failing provider."""
        super().__init__("failing", (MediaAssetType.VIDEO,))

    def _render(self, job: RenderJob) -> MediaAsset:
        """Raise the original provider implementation error."""
        del job
        msg = "provider unavailable"
        raise RuntimeError(msg)


class DownloadableProvider(MockVideoProvider):
    """Mock provider exposing a deterministic downloadable MP4 URL."""

    def _render(self, job: RenderJob) -> MediaAsset:
        """Add a temporary provider URL to the mock video asset."""
        asset = super()._render(job)
        asset.metadata["output_url"] = "https://cdn.example/video.mp4"
        return asset


class DownloadExecutor:
    """Return deterministic MP4 bytes without network access."""

    def __init__(self, status_code: int = 200) -> None:
        """Create a fake download executor."""
        self.status_code = status_code
        self.calls = 0

    def execute(
        self,
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: bytes | None,
        timeout_seconds: float,
    ) -> HTTPResponse:
        """Return one in-memory response."""
        del method, url, headers, body, timeout_seconds
        self.calls += 1
        return HTTPResponse(
            status_code=self.status_code,
            headers={"Content-Type": "video/mp4"},
            body=b"rendered-video" if self.status_code == 200 else b"error",
        )


def create_image_asset(job: RenderJob, provider_id: str) -> MediaAsset:
    """Create an image asset for invalid-provider tests."""
    return MediaAsset(
        asset_id=f"image-{job.job_id}",
        asset_type=MediaAssetType.IMAGE,
        name=job.plan.title,
        description=job.plan.summary,
        provider=provider_id,
        format="png",
    )


class RenderServiceTestCase(unittest.TestCase):
    """Tests for RenderService lifecycle coordination."""

    def test_successful_render_with_explicit_provider_id(self) -> None:
        """An explicit provider ID selects the registered provider."""
        service = create_service()
        job = create_render_job(provider="unused")

        asset = service.render(job, provider_id="mock-video")

        self.assertEqual(asset.provider, "mock-video")
        self.assertIs(job.status, RenderJobStatus.COMPLETED)

    def test_successful_render_uses_job_provider(self) -> None:
        """The job provider is used when no override is supplied."""
        service = create_service()
        job = create_render_job()

        asset = service.render(job)

        self.assertEqual(asset.asset_id, "asset-render-service-test")

    def test_successful_lifecycle_sets_and_returns_result_asset(self) -> None:
        """The service drives PENDING through RUNNING to COMPLETED."""
        provider = TrackingVideoProvider()
        service = create_service(provider)
        job = create_render_job()

        asset = service.render(job)

        self.assertEqual(provider.observed_statuses, [RenderJobStatus.RUNNING])
        self.assertIs(job.status, RenderJobStatus.COMPLETED)
        self.assertIs(job.result_asset, asset)
        self.assertIs(asset, job.result_asset)
        self.assertIsNone(job.error_message)

    def test_unknown_provider_is_propagated_before_start(self) -> None:
        """Unknown provider IDs remain KeyError and leave jobs pending."""
        service = RenderService(MediaProviderRegistry())
        job = create_render_job(provider="unknown")

        with self.assertRaises(KeyError):
            service.render(job)

        self.assertIs(job.status, RenderJobStatus.PENDING)

    def test_empty_job_provider_is_rejected_before_start(self) -> None:
        """An omitted provider requires a non-empty job provider."""
        service = RenderService(MediaProviderRegistry())
        job = create_render_job(provider="")

        with self.assertRaises(ValueError):
            service.render(job)

        self.assertIs(job.status, RenderJobStatus.PENDING)

    def test_unsupported_provider_is_rejected_before_start(self) -> None:
        """Providers without video support leave the job pending."""
        service = create_service(UnsupportedProvider())
        job = create_render_job(provider="image-only")

        with self.assertRaises(MediaProviderError):
            service.render(job)

        self.assertIs(job.status, RenderJobStatus.PENDING)

    def test_wrong_provider_return_type_fails_job(self) -> None:
        """Invalid provider return values fail the running job."""
        service = create_service(WrongTypeProvider())
        job = create_render_job(provider="wrong-type")

        with self.assertRaises(MediaProviderError):
            service.render(job)

        self.assertIs(job.status, RenderJobStatus.FAILED)

    def test_non_video_asset_fails_job(self) -> None:
        """A non-video provider result fails the running job."""
        service = create_service(NonVideoResultProvider())
        job = create_render_job(provider="non-video-result")

        with self.assertRaises(MediaProviderError):
            service.render(job)

        self.assertIs(job.status, RenderJobStatus.FAILED)

    def test_provider_error_sets_failed_status_and_message(self) -> None:
        """Provider errors fail the job and preserve their cause chain."""
        service = create_service(FailingProvider())
        job = create_render_job(provider="failing")

        with self.assertRaises(MediaProviderError) as context:
            service.render(job)

        self.assertIs(job.status, RenderJobStatus.FAILED)
        self.assertEqual(job.error_message, str(context.exception))
        self.assertIsInstance(context.exception.__cause__, RuntimeError)
        self.assertEqual(str(context.exception.__cause__), "provider unavailable")

    def test_fail_transition_error_does_not_hide_original_error(self) -> None:
        """A secondary job.fail error cannot replace the provider error."""
        service = create_service(FailingProvider())
        job = create_render_job(provider="failing")

        with patch.object(job, "fail", side_effect=RuntimeError("fail broke")):
            with self.assertRaises(MediaProviderError) as context:
                service.render(job)

        self.assertIsInstance(context.exception.__cause__, RuntimeError)
        self.assertEqual(str(context.exception.__cause__), "provider unavailable")

    def test_non_pending_jobs_are_rejected(self) -> None:
        """Running, completed and failed jobs cannot enter the service."""
        running_job = create_render_job()
        running_job.start()

        completed_job = create_render_job()
        completed_job.start()
        completed_job.complete(MockVideoProvider().render(completed_job))

        failed_job = create_render_job()
        failed_job.start()
        failed_job.fail("failed earlier")

        service = create_service()
        for job in (running_job, completed_job, failed_job):
            original_status = job.status
            with self.subTest(status=original_status):
                with self.assertRaises(ValueError):
                    service.render(job)
                self.assertIs(job.status, original_status)

    def test_registry_is_not_mutated(self) -> None:
        """Rendering leaves provider registration unchanged."""
        registry = MediaProviderRegistry()
        provider = MockVideoProvider()
        registry.register(provider)
        service = RenderService(registry)

        service.render(create_render_job())

        self.assertEqual(registry.all(), [provider])

    def test_service_instances_share_no_state(self) -> None:
        """Services retain only their explicitly supplied registries."""
        first_registry = MediaProviderRegistry()
        first_registry.register(MockVideoProvider())
        first = RenderService(first_registry)
        second = RenderService(MediaProviderRegistry())

        first.render(create_render_job())

        with self.assertRaises(KeyError):
            second.render(create_render_job())

    def test_render_uses_no_file_or_network_io(self) -> None:
        """Mock rendering completes with file and network access disabled."""
        service = create_service()
        job = create_render_job()

        with (
            patch.object(socket, "socket", side_effect=AssertionError("network used")),
            patch.object(Path, "write_text", side_effect=AssertionError("file used")),
        ):
            asset = service.render(job)

        self.assertIs(asset.asset_type, MediaAssetType.VIDEO)

    def test_optional_storage_completes_after_successful_download(self) -> None:
        """Storage metadata is registered before the job completes."""
        with TemporaryDirectory() as directory:
            registry = MediaProviderRegistry()
            registry.register(DownloadableProvider())
            executor = DownloadExecutor()
            storage = MediaStorage(Path(directory), executor=executor)
            service = RenderService(registry, storage, store_output=True)
            job = create_render_job()

            asset = service.render(job)

            self.assertIs(job.status, RenderJobStatus.COMPLETED)
            self.assertIs(job.result_asset, asset)
            self.assertEqual(executor.calls, 1)
            self.assertIsNotNone(service.last_stored_asset)
            stored = service.last_stored_asset
            if stored is None:
                self.fail("stored asset was not retained")
            self.assertTrue(stored.local_path.exists())
            self.assertEqual(asset.metadata["local_path"], str(stored.local_path))
            self.assertEqual(asset.metadata["sha256"], stored.sha256)

    def test_storage_failure_fails_running_job(self) -> None:
        """A failed download prevents a false COMPLETED render job."""
        with TemporaryDirectory() as directory:
            registry = MediaProviderRegistry()
            registry.register(DownloadableProvider())
            storage = MediaStorage(
                Path(directory),
                executor=DownloadExecutor(status_code=500),
            )
            service = RenderService(registry, storage, store_output=True)
            job = create_render_job()

            with self.assertRaises(MediaStorageError):
                service.render(job)

            self.assertIs(job.status, RenderJobStatus.FAILED)
            self.assertIsNone(job.result_asset)
            self.assertIsNone(service.last_stored_asset)

    def test_storage_mode_requires_explicit_storage(self) -> None:
        """Storage cannot be enabled without a configured local store."""
        with self.assertRaises(ValueError):
            RenderService(MediaProviderRegistry(), store_output=True)


if __name__ == "__main__":
    unittest.main()
