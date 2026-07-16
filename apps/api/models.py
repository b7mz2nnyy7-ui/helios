"""Pydantic contracts for the local Helios API."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from apps.api.mission_models import MissionPlatform


class ContentPipelineRequest(BaseModel):
    """Input contract for a local content pipeline execution."""

    model_config = ConfigDict(str_strip_whitespace=True)

    query: str = Field(min_length=1)
    language: str = Field(default="de", min_length=1)
    target_age_range: str = Field(default="18-34", min_length=1)
    target_duration_seconds: float = Field(default=30.0, gt=0)

    @field_validator("query", "language", "target_age_range")
    @classmethod
    def validate_text(cls, value: str) -> str:
        """Reject values that contain only whitespace."""
        if not value:
            msg = "value must be a non-empty string."
            raise ValueError(msg)

        return value


class ContentPipelineResponse(BaseModel):
    """Structured result returned after a successful pipeline execution."""

    status: str
    query: str
    completed_task_ids: list[str]
    script_title: str
    selected_hook: str
    storyboard_scene_count: int
    target_platform: str
    total_duration_seconds: float
    render_job_id: str
    render_job_status: str
    report_markdown: str


class HealthResponse(BaseModel):
    """Health response for the local API process."""

    status: str


class MissionCreateRequest(BaseModel):
    """Validated input for creating one local production mission."""

    model_config = ConfigDict(str_strip_whitespace=True)

    prompt: str = Field(min_length=1)
    platform: MissionPlatform
    duration: Literal[15, 30, 60] = 30
    render_model: str = Field(default="gen4.5", min_length=1)

    @field_validator("prompt", "render_model")
    @classmethod
    def validate_mission_text(cls, value: str) -> str:
        """Reject mission values containing only whitespace."""
        if not value:
            msg = "value must be a non-empty string."
            raise ValueError(msg)
        return value


class MissionPipelineStateResponse(BaseModel):
    """Observable progress derived from real pipeline steps."""

    current_stage: str
    completed_stages: list[str]
    completed_task_ids: list[str]


class MissionResponse(BaseModel):
    """Public representation of one local Helios mission."""

    id: str
    title: str
    prompt: str
    platform: str
    duration: int
    render_model: str
    status: str
    created_at: datetime
    updated_at: datetime
    video_id: str | None
    render_job_id: str | None
    pipeline_state: MissionPipelineStateResponse
    error_message: str | None


class VideoSummaryResponse(BaseModel):
    """Summary metadata for one locally stored video."""

    id: str
    filename: str
    created_at: datetime
    duration: float
    size_bytes: int
    sha256: str
    model: str


class VideoDetailResponse(VideoSummaryResponse):
    """Complete public metadata for one locally stored video."""

    mime_type: str
    metadata: dict[str, Any]


class SystemCheckResponse(BaseModel):
    """Public API representation of one ARGUS system check."""

    id: str
    name: str
    severity: str
    status: str
    summary: str
    details: dict[str, Any]
    checked_at: datetime
    duration_seconds: float


class SystemHealthResponse(BaseModel):
    """Public API representation of one complete ARGUS report."""

    created_at: datetime
    guardian_version: str
    overall_status: str
    checks: list[SystemCheckResponse]
    counters: dict[str, int]
    summary: str
    generated_by: str
