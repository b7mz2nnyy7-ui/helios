"""Tests for safe local media storage."""

from collections.abc import Mapping
from dataclasses import FrozenInstanceError
from hashlib import sha256
from pathlib import Path
import socket
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from engine.media.asset import MediaAsset, MediaAssetType
from engine.media.storage import MediaStorage, MediaStorageError
from integrations.runway.http_transport import HTTPResponse

VIDEO_BYTES = b"deterministic-mp4-content"
SECRET = "signed-download-secret"


class RecordingExecutor:
    """Return one deterministic response and record requests."""

    def __init__(self, response: HTTPResponse) -> None:
        """Create an executor with one fixed response."""
        self.response = response
        self.calls: list[tuple[str, str]] = []

    def execute(
        self,
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: bytes | None,
        timeout_seconds: float,
    ) -> HTTPResponse:
        """Record request method and URL without network access."""
        del headers, body, timeout_seconds
        self.calls.append((method, url))
        return self.response


class SequenceClock:
    """Return deterministic monotonic values."""

    def __init__(self, values: list[float]) -> None:
        """Create a clock with queued values."""
        self.values = list(values)

    def __call__(self) -> float:
        """Return the next queued timestamp."""
        return self.values.pop(0)


def video_asset(
    *,
    output_url: str = f"https://cdn.example/video.mp4?token={SECRET}",
    render_job_id: str = "render-job-1",
) -> MediaAsset:
    """Create a downloadable VIDEO asset."""
    return MediaAsset(
        asset_id="asset-video-1",
        asset_type=MediaAssetType.VIDEO,
        name="Stored Video",
        description="A completed video.",
        provider="runway",
        format="mp4",
        metadata={
            "output_url": output_url,
            "render_job_id": render_job_id,
        },
    )


def response(
    status_code: int = 200,
    content_type: str = "video/mp4",
    body: bytes = VIDEO_BYTES,
) -> HTTPResponse:
    """Create a deterministic download response."""
    return HTTPResponse(
        status_code=status_code,
        headers={"Content-Type": content_type},
        body=body,
    )


class MediaStorageTestCase(unittest.TestCase):
    """Tests for validated, non-overwriting MP4 downloads."""

    def test_successful_download_uses_existing_executor_contract(self) -> None:
        """A valid VIDEO response is stored through the injected executor."""
        with TemporaryDirectory() as directory:
            executor = RecordingExecutor(response())
            storage = MediaStorage(
                Path(directory) / "videos",
                executor=executor,
                clock=SequenceClock([10.0, 12.5]),
            )

            stored = storage.download_asset(video_asset())

            self.assertEqual(executor.calls[0][0], "GET")
            self.assertEqual(stored.local_path.read_bytes(), VIDEO_BYTES)
            self.assertEqual(stored.download_duration_seconds, 2.5)
            self.assertEqual(stored.mime_type, "video/mp4")

    def test_output_directory_is_created(self) -> None:
        """Construction creates missing output directories."""
        with TemporaryDirectory() as directory:
            output = Path(directory) / "nested" / "videos"

            MediaStorage(output)

            self.assertTrue(output.is_dir())

    def test_http_errors_are_rejected_without_writing(self) -> None:
        """HTTP 404 and 500 responses never create local assets."""
        for status_code in (404, 500):
            with self.subTest(status_code=status_code):
                with TemporaryDirectory() as directory:
                    output = Path(directory) / "videos"
                    storage = MediaStorage(
                        output,
                        executor=RecordingExecutor(response(status_code=status_code)),
                    )

                    with self.assertRaises(MediaStorageError):
                        storage.download_asset(video_asset())

                    self.assertEqual(list(output.iterdir()), [])

    def test_non_video_content_type_is_rejected(self) -> None:
        """Only video MIME types may be stored."""
        with TemporaryDirectory() as directory:
            storage = MediaStorage(
                Path(directory),
                executor=RecordingExecutor(response(content_type="text/html")),
            )

            with self.assertRaises(MediaStorageError):
                storage.download_asset(video_asset())

    def test_empty_download_is_rejected(self) -> None:
        """A zero-byte response cannot become a stored asset."""
        with TemporaryDirectory() as directory:
            storage = MediaStorage(
                Path(directory),
                executor=RecordingExecutor(response(body=b"")),
            )

            with self.assertRaises(MediaStorageError):
                storage.download_asset(video_asset())

    def test_hash_and_size_match_written_bytes(self) -> None:
        """Stored metadata describes the exact downloaded byte sequence."""
        with TemporaryDirectory() as directory:
            storage = MediaStorage(
                Path(directory),
                executor=RecordingExecutor(response()),
            )

            stored = storage.download_asset(video_asset())

            self.assertEqual(stored.size_bytes, len(VIDEO_BYTES))
            self.assertEqual(stored.sha256, sha256(VIDEO_BYTES).hexdigest())

    def test_existing_file_gets_unique_suffix_without_overwrite(self) -> None:
        """Repeated asset IDs create deterministic suffixes."""
        with TemporaryDirectory() as directory:
            output = Path(directory)
            existing = output / "render-job-1.mp4"
            existing.write_bytes(b"existing-content")
            storage = MediaStorage(
                output,
                executor=RecordingExecutor(response()),
            )

            first = storage.download_asset(video_asset())
            second = storage.download_asset(video_asset())

            self.assertEqual(first.local_path.name, "render-job-1-2.mp4")
            self.assertEqual(second.local_path.name, "render-job-1-3.mp4")
            self.assertEqual(existing.read_bytes(), b"existing-content")
            self.assertEqual(first.local_path.read_bytes(), VIDEO_BYTES)
            self.assertEqual(second.local_path.read_bytes(), VIDEO_BYTES)

    def test_path_traversal_cannot_escape_output_directory(self) -> None:
        """Unsafe render IDs are reduced to a safe filename."""
        with TemporaryDirectory() as directory:
            output = Path(directory) / "videos"
            storage = MediaStorage(
                output,
                executor=RecordingExecutor(response()),
            )

            stored = storage.download_asset(
                video_asset(render_job_id="../../outside folder"),
            )

            self.assertEqual(stored.local_path.parent, output.resolve())
            self.assertEqual(stored.local_path.name, "outside-folder.mp4")
            self.assertNotIn("..", stored.local_path.name)

    def test_invalid_filename_is_rejected(self) -> None:
        """An ID without any safe characters cannot produce a file."""
        with TemporaryDirectory() as directory:
            executor = RecordingExecutor(response())
            storage = MediaStorage(
                Path(directory),
                executor=executor,
            )

            with self.assertRaises(MediaStorageError):
                storage.download_asset(video_asset(render_job_id="../.."))
            self.assertEqual(executor.calls, [])

    def test_non_video_assets_are_rejected_before_download(self) -> None:
        """MediaStorage accepts only provider-neutral VIDEO assets."""
        executor = RecordingExecutor(response())
        asset = video_asset()
        asset.asset_type = MediaAssetType.AUDIO
        with TemporaryDirectory() as directory:
            storage = MediaStorage(Path(directory), executor=executor)

            with self.assertRaises(MediaStorageError):
                storage.download_asset(asset)

        self.assertEqual(executor.calls, [])

    def test_signed_url_is_absent_from_repr_and_errors(self) -> None:
        """Stored metadata and download failures never expose signed URLs."""
        with TemporaryDirectory() as directory:
            storage = MediaStorage(
                Path(directory),
                executor=RecordingExecutor(response()),
            )
            stored = storage.download_asset(video_asset())

            self.assertNotIn(SECRET, repr(stored))
            failing = MediaStorage(
                Path(directory),
                executor=RecordingExecutor(response(status_code=500)),
            )
            with self.assertRaises(MediaStorageError) as context:
                failing.download_asset(video_asset())
            self.assertNotIn(SECRET, str(context.exception))

    def test_stored_asset_is_immutable(self) -> None:
        """StoredMediaAsset fields cannot be reassigned."""
        with TemporaryDirectory() as directory:
            stored = MediaStorage(
                Path(directory),
                executor=RecordingExecutor(response()),
            ).download_asset(video_asset())

            with self.assertRaises(FrozenInstanceError):
                stored.size_bytes = 0  # type: ignore[misc]

    def test_no_network_is_used_by_storage_tests(self) -> None:
        """Injected executors keep all tests offline."""
        with TemporaryDirectory() as directory:
            storage = MediaStorage(
                Path(directory),
                executor=RecordingExecutor(response()),
            )

            with patch.object(
                socket,
                "socket",
                side_effect=AssertionError("network used"),
            ):
                stored = storage.download_asset(video_asset())

            self.assertTrue(stored.local_path.exists())


if __name__ == "__main__":
    unittest.main()
