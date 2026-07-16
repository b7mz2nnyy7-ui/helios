"""Immutable provider-neutral models for future content publishing."""

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Self


class PublishingTarget(StrEnum):
    """Platforms supported by the provider-neutral publishing contract."""

    TIKTOK = "TikTok"
    YOUTUBE = "YouTube"
    INSTAGRAM = "Instagram"
    X = "X"
    LINKEDIN = "LinkedIn"
    FACEBOOK = "Facebook"
    PINTEREST = "Pinterest"
    SNAPCHAT = "Snapchat"


class UploadStatus(StrEnum):
    """Lifecycle states for a future publishing job."""

    QUEUED = "QUEUED"
    WAITING = "WAITING"
    UPLOADING = "UPLOADING"
    PUBLISHED = "PUBLISHED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass(frozen=True)
class VideoMetadata:
    """Publication metadata independent of any platform provider."""

    title: str
    description: str
    hashtags: tuple[str, ...]
    language: str
    visibility: str
    category: str
    tags: tuple[str, ...]
    thumbnail: str | None = None
    scheduled_at: datetime | None = None

    def __post_init__(self) -> None:
        """Validate required text and protect collection fields."""
        for field_name, value in (
            ("title", self.title),
            ("description", self.description),
            ("language", self.language),
            ("visibility", self.visibility),
            ("category", self.category),
        ):
            _validate_text(value, field_name)
        object.__setattr__(self, "hashtags", tuple(self.hashtags))
        object.__setattr__(self, "tags", tuple(self.tags))
        _validate_datetime(self.scheduled_at, "scheduled_at", optional=True)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible representation."""
        return {
            "title": self.title,
            "description": self.description,
            "hashtags": list(self.hashtags),
            "language": self.language,
            "visibility": self.visibility,
            "category": self.category,
            "thumbnail": self.thumbnail,
            "tags": list(self.tags),
            "scheduled_at": _datetime_to_string(self.scheduled_at),
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> Self:
        """Reconstruct metadata from a JSON-compatible mapping."""
        return cls(
            title=_required_string(value.get("title")),
            description=_required_string(value.get("description")),
            hashtags=_string_tuple(value.get("hashtags")),
            language=_required_string(value.get("language")),
            visibility=_required_string(value.get("visibility")),
            category=_required_string(value.get("category")),
            thumbnail=_optional_string(value.get("thumbnail")),
            tags=_string_tuple(value.get("tags")),
            scheduled_at=_optional_datetime(value.get("scheduled_at")),
        )


@dataclass(frozen=True)
class PlatformConnection:
    """Secret-free description of one future platform connection."""

    connection_id: str
    platform: PublishingTarget
    display_name: str
    connected: bool
    created_at: datetime
    last_validated_at: datetime | None = None

    def __post_init__(self) -> None:
        """Validate identifiers and UTC timestamps."""
        _validate_text(self.connection_id, "connection_id")
        _validate_text(self.display_name, "display_name")
        _validate_datetime(self.created_at, "created_at")
        _validate_datetime(
            self.last_validated_at,
            "last_validated_at",
            optional=True,
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible representation without credentials."""
        return {
            "id": self.connection_id,
            "platform": self.platform.value,
            "display_name": self.display_name,
            "connected": self.connected,
            "created_at": self.created_at.isoformat(),
            "last_validated_at": _datetime_to_string(self.last_validated_at),
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> Self:
        """Reconstruct a secret-free platform connection."""
        return cls(
            connection_id=_required_string(value.get("id")),
            platform=PublishingTarget(_required_string(value.get("platform"))),
            display_name=_required_string(value.get("display_name")),
            connected=_required_bool(value.get("connected")),
            created_at=_required_datetime(value.get("created_at")),
            last_validated_at=_optional_datetime(
                value.get("last_validated_at"),
            ),
        )


@dataclass(frozen=True)
class PublishingJob:
    """Planned provider-neutral upload for one mission and target."""

    mission_id: str
    target: PublishingTarget
    status: UploadStatus
    created_at: datetime
    scheduled_at: datetime | None = None
    completed_at: datetime | None = None

    def __post_init__(self) -> None:
        """Validate mission identity and lifecycle timestamps."""
        _validate_text(self.mission_id, "mission_id")
        _validate_datetime(self.created_at, "created_at")
        _validate_datetime(self.scheduled_at, "scheduled_at", optional=True)
        _validate_datetime(self.completed_at, "completed_at", optional=True)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible job representation."""
        return {
            "mission_id": self.mission_id,
            "target": self.target.value,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "scheduled_at": _datetime_to_string(self.scheduled_at),
            "completed_at": _datetime_to_string(self.completed_at),
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> Self:
        """Reconstruct one publishing job from serialized values."""
        return cls(
            mission_id=_required_string(value.get("mission_id")),
            target=PublishingTarget(_required_string(value.get("target"))),
            status=UploadStatus(_required_string(value.get("status"))),
            created_at=_required_datetime(value.get("created_at")),
            scheduled_at=_optional_datetime(value.get("scheduled_at")),
            completed_at=_optional_datetime(value.get("completed_at")),
        )


def _validate_text(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        msg = f"{field_name} must not be empty."
        raise ValueError(msg)


def _validate_datetime(
    value: datetime | None,
    field_name: str,
    *,
    optional: bool = False,
) -> None:
    if value is None and optional:
        return
    if value is None or value.tzinfo is not UTC:
        msg = f"{field_name} must use UTC."
        raise ValueError(msg)


def _datetime_to_string(value: datetime | None) -> str | None:
    return None if value is None else value.isoformat()


def _required_string(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("serialized value must be a non-empty string.")
    return value


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    return _required_string(value)


def _string_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, list | tuple) or not all(
        isinstance(item, str) for item in value
    ):
        raise ValueError("serialized value must be a list of strings.")
    return tuple(value)


def _required_bool(value: object) -> bool:
    if not isinstance(value, bool):
        raise ValueError("serialized value must be a boolean.")
    return value


def _required_datetime(value: object) -> datetime:
    timestamp = datetime.fromisoformat(_required_string(value))
    _validate_datetime(timestamp, "serialized datetime")
    return timestamp


def _optional_datetime(value: object) -> datetime | None:
    if value is None:
        return None
    return _required_datetime(value)
