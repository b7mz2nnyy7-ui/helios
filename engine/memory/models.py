"""Memory model definitions."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class MemoryEntry:
    """A memory entry that can be stored by a memory backend."""

    memory_id: str
    title: str
    content: str
    category: str
    metadata: dict[str, Any]
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        """Validate required memory fields."""
        if not self.title.strip():
            msg = "title must not be empty."
            raise ValueError(msg)

        if not self.content.strip():
            msg = "content must not be empty."
            raise ValueError(msg)

        if not self.category.strip():
            msg = "category must not be empty."
            raise ValueError(msg)
