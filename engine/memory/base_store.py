"""Base abstraction for memory stores."""

from abc import ABC, abstractmethod

from engine.memory.models import MemoryEntry


class BaseMemoryStore(ABC):
    """Abstract base class for memory storage backends."""

    @abstractmethod
    def save(self, entry: MemoryEntry) -> None:
        """Save a memory entry."""

    @abstractmethod
    def get(self, memory_id: str) -> MemoryEntry:
        """Return a memory entry by ID."""

    @abstractmethod
    def exists(self, memory_id: str) -> bool:
        """Return whether a memory entry exists."""

    @abstractmethod
    def delete(self, memory_id: str) -> None:
        """Delete a memory entry by ID."""

    @abstractmethod
    def list_all(self) -> list[MemoryEntry]:
        """Return all memory entries."""
