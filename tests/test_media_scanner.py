"""Tests for filesystem-backed local video discovery."""

from datetime import UTC
from hashlib import sha256
import json
import os
from pathlib import Path
import struct
from tempfile import TemporaryDirectory
import unittest

from engine.media.scanner import MediaStorageScanner


def mp4_bytes(duration_seconds: float = 12.5) -> bytes:
    """Create a minimal MP4 container with one movie header."""
    timescale = 1000
    duration = int(duration_seconds * timescale)
    mvhd_payload = b"\x00\x00\x00\x00" + struct.pack(
        ">IIII",
        0,
        0,
        timescale,
        duration,
    )
    mvhd = _box(b"mvhd", mvhd_payload)
    moov = _box(b"moov", mvhd)
    ftyp = _box(b"ftyp", b"isom\x00\x00\x00\x00")
    return ftyp + moov


def _box(box_type: bytes, payload: bytes) -> bytes:
    return struct.pack(">I4s", len(payload) + 8, box_type) + payload


class MediaStorageScannerTestCase(unittest.TestCase):
    """Tests for scanning MP4 files without persistence services."""

    def test_missing_directory_returns_empty_list(self) -> None:
        """An absent output directory represents an empty catalog."""
        with TemporaryDirectory() as directory:
            scanner = MediaStorageScanner(Path(directory) / "missing")

            self.assertEqual(scanner.scan(), [])

    def test_scan_reads_file_metadata_hash_duration_and_model(self) -> None:
        """A local MP4 becomes complete immutable scanner metadata."""
        with TemporaryDirectory() as directory:
            output = Path(directory)
            content = mp4_bytes(12.5)
            video_path = output / "gen45-product-launch.mp4"
            video_path.write_bytes(content)
            video_path.with_suffix(".json").write_text(
                json.dumps({"model": "gen4.5", "campaign": "launch"}),
                encoding="utf-8",
            )

            videos = MediaStorageScanner(output).scan()

            self.assertEqual(len(videos), 1)
            video = videos[0]
            self.assertEqual(video.filename, video_path.name)
            self.assertEqual(video.duration, 12.5)
            self.assertEqual(video.size_bytes, len(content))
            self.assertEqual(video.sha256, sha256(content).hexdigest())
            self.assertEqual(video.model, "gen4.5")
            self.assertEqual(video.metadata["campaign"], "launch")
            self.assertIs(video.created_at.tzinfo, UTC)
            self.assertEqual(video.path, video_path.resolve())

    def test_scan_orders_newest_video_first(self) -> None:
        """Catalog order is deterministic and optimized for recent work."""
        with TemporaryDirectory() as directory:
            output = Path(directory)
            older = output / "older.mp4"
            newer = output / "newer.mp4"
            older.write_bytes(mp4_bytes())
            newer.write_bytes(mp4_bytes())
            older.touch()
            newer.touch()
            older_stat = older.stat()
            newer_time = older_stat.st_mtime + 10
            newer.touch()
            os.utime(newer, (newer_time, newer_time))

            videos = MediaStorageScanner(output).scan()

            self.assertEqual(
                [video.filename for video in videos],
                ["newer.mp4", "older.mp4"],
            )

    def test_model_is_inferred_or_reported_unknown(self) -> None:
        """Scanner never invents unavailable provider metadata."""
        with TemporaryDirectory() as directory:
            output = Path(directory)
            (output / "gen45-demo.mp4").write_bytes(mp4_bytes())
            (output / "legacy-video.mp4").write_bytes(mp4_bytes())

            videos = {
                video.filename: video for video in MediaStorageScanner(output).scan()
            }

            self.assertEqual(videos["gen45-demo.mp4"].model, "gen4.5")
            self.assertEqual(videos["legacy-video.mp4"].model, "unknown")

    def test_sidecar_duration_is_used_for_non_parseable_mp4(self) -> None:
        """Filesystem metadata can enrich legacy video files."""
        with TemporaryDirectory() as directory:
            output = Path(directory)
            video = output / "legacy.mp4"
            video.write_bytes(b"not-a-parseable-mp4")
            video.with_suffix(".json").write_text(
                json.dumps({"duration": 8.25, "model": "legacy-model"}),
                encoding="utf-8",
            )

            scanned = MediaStorageScanner(output).scan()[0]

            self.assertEqual(scanned.duration, 8.25)
            self.assertEqual(scanned.model, "legacy-model")

    def test_non_mp4_files_and_symlinks_are_ignored(self) -> None:
        """Scanner does not expose unrelated files or symlink targets."""
        with TemporaryDirectory() as directory:
            output = Path(directory)
            (output / "notes.txt").write_text("ignore", encoding="utf-8")
            real_video = output / "real.mp4"
            real_video.write_bytes(mp4_bytes())
            symlink = output / "linked.mp4"
            try:
                symlink.symlink_to(real_video)
            except OSError:
                self.skipTest("symlinks are unavailable on this filesystem")

            videos = MediaStorageScanner(output).scan()

            self.assertEqual([video.filename for video in videos], ["real.mp4"])

    def test_empty_mp4_files_are_ignored(self) -> None:
        """Zero-byte files are excluded from the streamable catalog."""
        with TemporaryDirectory() as directory:
            output = Path(directory)
            (output / "empty.mp4").touch()

            videos = MediaStorageScanner(output).scan()

            self.assertEqual(videos, [])

    def test_video_ids_are_stable_and_url_safe(self) -> None:
        """Repeated scans produce the same hexadecimal public ID."""
        with TemporaryDirectory() as directory:
            output = Path(directory)
            (output / "Video With Spaces.mp4").write_bytes(mp4_bytes())
            scanner = MediaStorageScanner(output)

            first = scanner.scan()[0].video_id
            second = scanner.scan()[0].video_id

            self.assertEqual(first, second)
            self.assertRegex(first, r"^[0-9a-f]{16}$")


if __name__ == "__main__":
    unittest.main()
