"""Models for deterministic Helios alerts."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class AlertSeverity(StrEnum):
    """Severity values for deterministic alerts."""

    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class Alert:
    """A structured alert derived from a system event."""

    alert_id: str
    event_type: str
    severity: AlertSeverity
    title: str
    message: str
    source: str | None
    metadata: dict[str, Any]
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

