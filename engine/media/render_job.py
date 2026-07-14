"""Provider-neutral render job models."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from engine.media.asset import MediaAsset
from engine.media.render_plan import VideoProductionPlan


class RenderJobStatus(StrEnum):
    """Lifecycle states for a render job."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass
class RenderJob:
    """A provider-neutral media render job."""

    job_id: str
    plan: VideoProductionPlan
    provider: str
    status: RenderJobStatus = field(default=RenderJobStatus.PENDING, init=False)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC), init=False)
    result_asset: MediaAsset | None = None
    error_message: str | None = None

    def start(self) -> None:
        """Mark the render job as running."""
        self._transition_to(RenderJobStatus.RUNNING)

    def complete(self, asset: MediaAsset) -> None:
        """Mark the render job as completed and store the result asset."""
        self._transition_to(RenderJobStatus.COMPLETED)
        self.result_asset = asset
        self.error_message = None

    def fail(self, message: str) -> None:
        """Mark the render job as failed and store the error message."""
        self._transition_to(RenderJobStatus.FAILED)
        self.error_message = message

    def _transition_to(self, new_status: RenderJobStatus) -> None:
        valid_transitions = {
            (RenderJobStatus.PENDING, RenderJobStatus.RUNNING),
            (RenderJobStatus.RUNNING, RenderJobStatus.COMPLETED),
            (RenderJobStatus.RUNNING, RenderJobStatus.FAILED),
        }

        if (self.status, new_status) not in valid_transitions:
            msg = (
                f"Invalid render job status transition from "
                f"{self.status.value} to {new_status.value}."
            )
            raise ValueError(msg)

        self.status = new_status
