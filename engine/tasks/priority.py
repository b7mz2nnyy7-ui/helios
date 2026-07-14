"""Task priority definitions."""

from enum import StrEnum


class TaskPriority(StrEnum):
    """Supported priority levels for a task."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"
