"""Agent runtime status definitions."""

from enum import StrEnum


class AgentStatus(StrEnum):
    """Possible lifecycle states for an agent."""

    IDLE = "IDLE"
    RUNNING = "RUNNING"
    STOPPED = "STOPPED"
    FAILED = "FAILED"
