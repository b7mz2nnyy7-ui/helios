"""Pydantic contracts for the local Helios API."""

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
