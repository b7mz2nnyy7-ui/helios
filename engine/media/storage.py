"""Local storage for downloaded provider-neutral media assets."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
import re
import time
from typing import Protocol
from urllib.parse import urlsplit

from engine.media.asset import MediaAsset, MediaAssetType

DEFAULT_MEDIA_OUTPUT_DIRECTORY = Path("output/videos")
_DOWNLOAD_CHUNK_SIZE = 64 * 1024


class MediaStorageError(Exception):
    """Raised when a media asset cannot be downloaded or stored safely."""


class DownloadHTTPExecutor(Protocol):
    """Structural HTTP executor contract used for media downloads."""

    def execute(
        self,
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: bytes | None,
        timeout_seconds: float,
    ) -> object:
        """Execute one HTTP request and return its response."""


@dataclass(frozen=True)
class StoredMediaAsset:
    """Immutable metadata for one locally stored media asset."""

    local_path: Path
    size_bytes: int
    download_duration_seconds: float
    sha256: str
    mime_type: str
    created_at: datetime
    original_asset: MediaAsset = field(repr=False)

    def __post_init__(self) -> None:
        """Validate stored media metadata."""
        if self.local_path.suffix.lower() != ".mp4":
            msg = "local_path must use the .mp4 extension."
            raise ValueError(msg)
        if self.size_bytes <= 0:
            msg = "size_bytes must be greater than 0."
            raise ValueError(msg)
        if self.download_duration_seconds < 0:
            msg = "download_duration_seconds must not be negative."
            raise ValueError(msg)
        if re.fullmatch(r"[0-9a-f]{64}", self.sha256) is None:
            msg = "sha256 must be a lowercase SHA-256 digest."
            raise ValueError(msg)
        if not self.mime_type.lower().startswith("video/"):
            msg = "mime_type must describe video content."
            raise ValueError(msg)
        if self.created_at.tzinfo is not UTC:
            msg = "created_at must use UTC."
            raise ValueError(msg)


class MediaStorage:
    """Download video assets into a safe local output directory."""

    def __init__(
        self,
        output_directory: Path = DEFAULT_MEDIA_OUTPUT_DIRECTORY,
        *,
        executor: DownloadHTTPExecutor | None = None,
        timeout_seconds: float = 120.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """Create local storage backed by an injected HTTP executor."""
        if not isinstance(output_directory, Path):
            msg = "output_directory must be a Path."
            raise ValueError(msg)
        if timeout_seconds <= 0:
            msg = "timeout_seconds must be greater than 0."
            raise ValueError(msg)

        self.output_directory = output_directory
        self.executor = executor
        self.timeout_seconds = timeout_seconds
        self._clock = clock
        self.output_directory.mkdir(parents=True, exist_ok=True)

    def download_asset(self, asset: MediaAsset) -> StoredMediaAsset:
        """Download and store one VIDEO asset without overwriting files."""
        source_url = self._validate_asset(asset)
        if self.executor is None:
            msg = "MediaStorage requires an HTTP executor for downloads."
            raise MediaStorageError(msg)

        started_at = self._clock()
        try:
            response = self.executor.execute(
                "GET",
                source_url,
                {"Accept": "video/*"},
                None,
                self.timeout_seconds,
            )
        except Exception as error:
            msg = "Media asset download failed."
            raise MediaStorageError(msg) from error

        mime_type, body = self._validate_response(response)
        local_path, digest = self._write_unique(asset, body)
        elapsed = max(0.0, self._clock() - started_at)
        return StoredMediaAsset(
            local_path=local_path,
            size_bytes=len(body),
            download_duration_seconds=elapsed,
            sha256=digest,
            mime_type=mime_type,
            created_at=datetime.now(UTC),
            original_asset=asset,
        )

    def _validate_asset(self, asset: MediaAsset) -> str:
        if not isinstance(asset, MediaAsset):
            msg = "asset must be a MediaAsset."
            raise MediaStorageError(msg)
        if asset.asset_type is not MediaAssetType.VIDEO:
            msg = "MediaStorage only supports VIDEO assets."
            raise MediaStorageError(msg)
        if asset.format.strip().lower() != "mp4":
            msg = "MediaStorage only supports the mp4 format."
            raise MediaStorageError(msg)

        source_url = asset.metadata.get("output_url")
        if not isinstance(source_url, str) or not source_url.strip():
            msg = "VIDEO asset metadata requires an output_url."
            raise MediaStorageError(msg)
        parsed_url = urlsplit(source_url)
        if (
            parsed_url.scheme not in {"http", "https"}
            or not parsed_url.netloc
            or Path(parsed_url.path).suffix.lower() != ".mp4"
        ):
            msg = "VIDEO asset output_url must reference an HTTP(S) .mp4 file."
            raise MediaStorageError(msg)
        _safe_asset_stem(asset)
        return source_url

    def _validate_response(
        self,
        response: object,
    ) -> tuple[str, bytes]:
        status_code = getattr(response, "status_code", None)
        headers = getattr(response, "headers", None)
        body = getattr(response, "body", None)
        if isinstance(status_code, bool) or not isinstance(status_code, int):
            msg = "Media download returned an invalid HTTP status."
            raise MediaStorageError(msg)
        if not isinstance(headers, Mapping):
            msg = "Media download returned invalid HTTP headers."
            raise MediaStorageError(msg)
        if status_code != 200:
            msg = f"Media download returned HTTP {status_code}."
            raise MediaStorageError(msg)

        if not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in headers.items()
        ):
            msg = "Media download returned invalid HTTP headers."
            raise MediaStorageError(msg)
        mime_type = _header_value(headers, "Content-Type")
        normalized_mime_type = mime_type.split(";", maxsplit=1)[0].strip().lower()
        if not normalized_mime_type.startswith("video/"):
            msg = "Media download did not return video content."
            raise MediaStorageError(msg)
        if not isinstance(body, bytes) or not body:
            msg = "Media download returned an empty body."
            raise MediaStorageError(msg)
        return normalized_mime_type, body

    def _write_unique(
        self,
        asset: MediaAsset,
        body: bytes,
    ) -> tuple[Path, str]:
        stem = _safe_asset_stem(asset)
        suffix = 1
        while True:
            candidate_stem = stem if suffix == 1 else f"{stem}-{suffix}"
            candidate = self.output_directory / f"{candidate_stem}.mp4"
            digest = sha256()
            try:
                with candidate.open("xb") as output:
                    body_view = memoryview(body)
                    for offset in range(0, len(body), _DOWNLOAD_CHUNK_SIZE):
                        chunk = body_view[offset : offset + _DOWNLOAD_CHUNK_SIZE]
                        digest.update(chunk)
                        output.write(chunk)
            except FileExistsError:
                suffix += 1
                continue
            except OSError as error:
                candidate.unlink(missing_ok=True)
                msg = "Media asset could not be written to local storage."
                raise MediaStorageError(msg) from error
            return candidate.resolve(), digest.hexdigest()


def _header_value(headers: Mapping[str, str], name: str) -> str:
    for key, value in headers.items():
        if key.lower() == name.lower():
            return value
    return ""


def _safe_asset_stem(asset: MediaAsset) -> str:
    raw_stem = asset.metadata.get("render_job_id", asset.asset_id)
    if not isinstance(raw_stem, str):
        raw_stem = asset.asset_id
    safe_stem = re.sub(r"[^A-Za-z0-9_-]+", "-", raw_stem).strip("-_")
    if not safe_stem:
        msg = "Media asset does not provide a safe local filename."
        raise MediaStorageError(msg)
    return safe_stem
