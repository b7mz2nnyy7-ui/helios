"""Provider-neutral media asset models."""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class MediaAssetType(StrEnum):
    """Supported media asset types."""

    IMAGE = "IMAGE"
    VIDEO = "VIDEO"
    AUDIO = "AUDIO"
    THUMBNAIL = "THUMBNAIL"
    SUBTITLE = "SUBTITLE"


@dataclass
class MediaAsset:
    """A media asset produced or referenced by Helios."""

    asset_id: str
    asset_type: MediaAssetType
    name: str
    description: str
    provider: str
    format: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate media asset values."""
        if not self.asset_id.strip():
            msg = "asset_id must not be empty."
            raise ValueError(msg)

        if not self.name.strip():
            msg = "name must not be empty."
            raise ValueError(msg)

        if not self.provider.strip():
            msg = "provider must not be empty."
            raise ValueError(msg)

        if not self.format.strip():
            msg = "format must not be empty."
            raise ValueError(msg)

        if not isinstance(self.metadata, dict):
            msg = "metadata must be a dictionary."
            raise ValueError(msg)
