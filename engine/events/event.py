"""Event model definitions."""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True)
class Event:
    """Immutable event published through the Helios event bus."""

    event_type: str
    payload: dict[str, Any] = field(default_factory=dict)
    source: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


EventHandler = Callable[[Event], None]
