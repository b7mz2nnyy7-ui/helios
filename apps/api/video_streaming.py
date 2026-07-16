"""HTTP byte-range helpers for local MP4 streaming."""

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Iterator

_STREAM_CHUNK_SIZE = 1024 * 1024
_RANGE_PATTERN = re.compile(r"^bytes=(\d*)-(\d*)$")


@dataclass(frozen=True)
class ByteRange:
    """Inclusive byte range for one HTTP response."""

    start: int
    end: int

    @property
    def length(self) -> int:
        """Return the number of bytes represented by this range."""
        return self.end - self.start + 1


def parse_range_header(value: str, file_size: int) -> ByteRange:
    """Parse one RFC 7233-style byte range for a known file size."""
    match = _RANGE_PATTERN.fullmatch(value.strip())
    if match is None or file_size <= 0:
        raise ValueError("Invalid Range header.")
    raw_start, raw_end = match.groups()
    if not raw_start and not raw_end:
        raise ValueError("Invalid Range header.")

    if not raw_start:
        suffix_length = int(raw_end)
        if suffix_length <= 0:
            raise ValueError("Invalid Range header.")
        start = max(0, file_size - suffix_length)
        return ByteRange(start, file_size - 1)

    start = int(raw_start)
    if start >= file_size:
        raise ValueError("Requested range starts beyond the file.")
    end = file_size - 1 if not raw_end else int(raw_end)
    if end < start:
        raise ValueError("Requested range end precedes its start.")
    return ByteRange(start, min(end, file_size - 1))


def iter_file_range(path: Path, byte_range: ByteRange) -> Iterator[bytes]:
    """Yield one local file range in bounded chunks."""
    remaining = byte_range.length
    with path.open("rb") as video_file:
        video_file.seek(byte_range.start)
        while remaining > 0:
            chunk = video_file.read(min(_STREAM_CHUNK_SIZE, remaining))
            if not chunk:
                return
            remaining -= len(chunk)
            yield chunk
