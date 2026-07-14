"""Task model for Helios."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from engine.runtime.capability import AgentCapability
from engine.tasks.priority import TaskPriority
from engine.tasks.status import TaskStatus


@dataclass
class Task:
    """A unit of work tracked by the Helios task system."""

    task_id: str
    title: str
    description: str
    priority: TaskPriority
    required_capability: AgentCapability
    payload: dict[str, Any]
    result: Any | None = None
    error_message: str | None = None
    status: TaskStatus = field(default=TaskStatus.PENDING, init=False)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC), init=False)

    def start(self) -> None:
        """Mark the task as running."""
        self._transition_to(TaskStatus.RUNNING)

    def complete(self, result: Any = None) -> None:
        """Mark the task as completed."""
        self._transition_to(TaskStatus.COMPLETED)
        self.result = result
        self.error_message = None

    def fail(self, error_message: str | None = None) -> None:
        """Mark the task as failed."""
        self._transition_to(TaskStatus.FAILED)
        self.error_message = error_message

    def is_finished(self) -> bool:
        """Return whether the task has reached a finished state."""
        return self.status in {TaskStatus.COMPLETED, TaskStatus.FAILED}

    def _transition_to(self, new_status: TaskStatus) -> None:
        valid_transitions = {
            (TaskStatus.PENDING, TaskStatus.RUNNING),
            (TaskStatus.RUNNING, TaskStatus.COMPLETED),
            (TaskStatus.RUNNING, TaskStatus.FAILED),
        }

        if (self.status, new_status) not in valid_transitions:
            msg = (
                f"Invalid task status transition from "
                f"{self.status.value} to {new_status.value}."
            )
            raise ValueError(msg)

        self.status = new_status
