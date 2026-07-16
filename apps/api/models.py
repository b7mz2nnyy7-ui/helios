"""Pydantic contracts for the local Helios API."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


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
