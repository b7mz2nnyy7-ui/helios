"""Task status definitions."""

from enum import StrEnum


class TaskStatus(StrEnum):
    """Possible lifecycle states for a task."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
