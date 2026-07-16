"""Application models for local Helios missions."""

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
import math


class MissionStatus(StrEnum):
    """Lifecycle states exposed by the local Mission API."""

    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class MissionPlatform(StrEnum):
    """Platforms supported by the Mission Studio MVP."""

    YOUTUBE = "YouTube"
    TIKTOK = "TikTok"
    INSTAGRAM = "Instagram"
    X = "X"


class MissionStage(StrEnum):
    """Observable stages derived from existing pipeline operations."""

    RESEARCH = "Research"
    SCRIPT = "Script"
    STORYBOARD = "Storyboard"
    RENDERING = "Rendering"
    DOWNLOAD = "Download"
    COMPLETED = "Completed"


@dataclass(frozen=True)
class MissionPipelineState:
    """Current mission progress without fabricated percentage values."""

    current_stage: MissionStage
    completed_stages: tuple[MissionStage, ...] = ()
    completed_task_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class Mission:
    """Immutable local representation of one Helios production mission."""

    mission_id: str
    title: str
    prompt: str
    platform: MissionPlatform
    duration: int
    render_model: str
    status: MissionStatus
    created_at: datetime
    updated_at: datetime
    pipeline_state: MissionPipelineState
    video_id: str | None = None
    render_job_id: str | None = None
    error_message: str | None = None

    def __post_init__(self) -> None:
        """Validate mission values and UTC timestamps."""
        for field_name, value in (
            ("mission_id", self.mission_id),
            ("title", self.title),
            ("prompt", self.prompt),
            ("render_model", self.render_model),
        ):
            if not value.strip():
                msg = f"{field_name} must not be empty."
                raise ValueError(msg)
        if self.duration not in {15, 30, 60}:
            msg = "duration must be one of 15, 30, or 60 seconds."
            raise ValueError(msg)
        for field_name, timestamp in (
            ("created_at", self.created_at),
            ("updated_at", self.updated_at),
        ):
            if timestamp.tzinfo is not UTC or not math.isfinite(timestamp.timestamp()):
                msg = f"{field_name} must use a finite UTC timestamp."
                raise ValueError(msg)
