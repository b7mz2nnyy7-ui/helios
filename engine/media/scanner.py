"""Filesystem-backed discovery of locally stored MP4 videos."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from hashlib import sha256
import json
from pathlib import Path
import re
import struct
from typing import Any, BinaryIO, Iterator

from engine.media.storage import DEFAULT_MEDIA_OUTPUT_DIRECTORY

_HASH_CHUNK_SIZE = 1024 * 1024
_SAFE_MODEL_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")


@dataclass(frozen=True)
class ScannedVideo:
    """Immutable metadata for one discovered local video."""

    video_id: str
    filename: str
    created_at: datetime
    duration: float
    size_bytes: int
    sha256: str
    model: str
    mime_type: str
    metadata: dict[str, Any] = field(default_factory=dict)
    path: Path = field(repr=False, compare=False, default=Path())


class MediaStorageScanner:
    """Scan one local media directory without a database or global state."""

    def __init__(
        self,
        output_directory: Path = DEFAULT_MEDIA_OUTPUT_DIRECTORY,
    ) -> None:
        """Create a scanner for a local video output directory."""
        if not isinstance(output_directory, Path):
            msg = "output_directory must be a Path."
            raise ValueError(msg)
        self.output_directory = output_directory

    def scan(self) -> list[ScannedVideo]:
        """Return all safe local MP4 files ordered newest first."""
        if not self.output_directory.exists():
            return []
        if not self.output_directory.is_dir():
            msg = "output_directory must reference a directory."
            raise ValueError(msg)

        videos: list[ScannedVideo] = []
        for path in sorted(self.output_directory.glob("*.mp4")):
            if path.is_symlink() or not path.is_file():
                continue
            try:
                if path.stat().st_size == 0:
                    continue
                videos.append(self._scan_file(path))
            except OSError:
                continue
        return sorted(
            videos,
            key=lambda video: (video.created_at, video.filename),
            reverse=True,
        )

    def _scan_file(self, path: Path) -> ScannedVideo:
        stat = path.stat()
        sidecar = _read_sidecar(path)
        duration = _read_mp4_duration(path)
        if duration == 0.0:
            duration = _sidecar_duration(sidecar)
        model = _sidecar_model(sidecar) or _infer_model(path.name)
        return ScannedVideo(
            video_id=sha256(path.name.encode("utf-8")).hexdigest()[:16],
            filename=path.name,
            created_at=datetime.fromtimestamp(stat.st_mtime, UTC),
            duration=duration,
            size_bytes=stat.st_size,
            sha256=_hash_file(path),
            model=model,
            mime_type="video/mp4",
            metadata=sidecar,
            path=path.resolve(),
        )


def _hash_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as video_file:
        while chunk := video_file.read(_HASH_CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


def _read_sidecar(path: Path) -> dict[str, Any]:
    candidates = (
        path.with_suffix(".json"),
        path.with_name(f"{path.name}.metadata.json"),
    )
    for candidate in candidates:
        if candidate.is_symlink() or not candidate.is_file():
            continue
        try:
            payload: object = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict) and all(
            isinstance(key, str) for key in payload
        ):
            return dict(payload)
    return {}


def _sidecar_duration(metadata: dict[str, Any]) -> float:
    raw_duration = metadata.get(
        "duration",
        metadata.get("total_duration_seconds", 0.0),
    )
    if isinstance(raw_duration, bool) or not isinstance(raw_duration, (int, float)):
        return 0.0
    return max(0.0, float(raw_duration))


def _sidecar_model(metadata: dict[str, Any]) -> str | None:
    raw_model = metadata.get("model")
    if (
        not isinstance(raw_model, str)
        or not raw_model.strip()
        or _SAFE_MODEL_PATTERN.fullmatch(raw_model.strip()) is None
    ):
        return None
    return raw_model.strip()


def _infer_model(filename: str) -> str:
    normalized = filename.lower().replace("_", "-")
    if re.search(r"(?:gen-?4-?5|gen45)", normalized):
        return "gen4.5"
    return "unknown"


def _read_mp4_duration(path: Path) -> float:
    try:
        with path.open("rb") as video_file:
            file_size = path.stat().st_size
            for box_type, payload_start, box_end in _iter_boxes(
                video_file,
                0,
                file_size,
            ):
                if box_type != b"moov":
                    continue
                for child_type, child_start, child_end in _iter_boxes(
                    video_file,
                    payload_start,
                    box_end,
                ):
                    if child_type == b"mvhd":
                        return _read_mvhd_duration(
                            video_file,
                            child_start,
                            child_end,
                        )
    except (OSError, ValueError, struct.error):
        return 0.0
    return 0.0


def _iter_boxes(
    video_file: BinaryIO,
    start: int,
    end: int,
) -> Iterator[tuple[bytes, int, int]]:
    position = start
    while position + 8 <= end:
        video_file.seek(position)
        header = video_file.read(8)
        if len(header) != 8:
            return
        size, box_type = struct.unpack(">I4s", header)
        header_size = 8
        if size == 1:
            extended = video_file.read(8)
            if len(extended) != 8:
                return
            size = struct.unpack(">Q", extended)[0]
            header_size = 16
        elif size == 0:
            size = end - position
        if size < header_size or position + size > end:
            raise ValueError("Invalid MP4 box size.")
        box_end = position + size
        yield box_type, position + header_size, box_end
        position = box_end


def _read_mvhd_duration(
    video_file: BinaryIO,
    payload_start: int,
    payload_end: int,
) -> float:
    video_file.seek(payload_start)
    version_flags = video_file.read(4)
    if len(version_flags) != 4:
        return 0.0
    version = version_flags[0]
    if version == 0:
        values = video_file.read(16)
        if len(values) != 16:
            return 0.0
        _, _, timescale, duration = struct.unpack(">IIII", values)
    elif version == 1:
        values = video_file.read(28)
        if len(values) != 28:
            return 0.0
        _, _, timescale, duration = struct.unpack(">QQIQ", values)
    else:
        return 0.0
    if video_file.tell() > payload_end or timescale == 0:
        return 0.0
    return duration / timescale
