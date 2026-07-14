"""Tests for memory models."""

import unittest
from datetime import UTC

from engine.memory.models import MemoryEntry


def create_entry() -> MemoryEntry:
    """Create a valid memory entry."""
    return MemoryEntry(
        memory_id="memory-1",
        title="Trend Report",
        content="Content",
        category="trend",
        metadata={"source": "test"},
    )


class MemoryEntryTestCase(unittest.TestCase):
    """Tests for MemoryEntry behavior."""

    def test_valid_memory_entry_can_be_created(self) -> None:
        """A valid memory entry stores its values."""
        entry = create_entry()

        self.assertEqual(entry.memory_id, "memory-1")
        self.assertEqual(entry.title, "Trend Report")
        self.assertEqual(entry.content, "Content")
        self.assertEqual(entry.category, "trend")
        self.assertEqual(entry.metadata, {"source": "test"})

    def test_created_at_uses_utc_timezone(self) -> None:
        """created_at is generated in UTC."""
        entry = create_entry()

        self.assertIs(entry.created_at.tzinfo, UTC)

    def test_empty_title_raises_value_error(self) -> None:
        """An empty title is invalid."""
        with self.assertRaises(ValueError):
            MemoryEntry(
                memory_id="memory-1",
                title=" ",
                content="Content",
                category="trend",
                metadata={},
            )

    def test_empty_content_raises_value_error(self) -> None:
        """Empty content is invalid."""
        with self.assertRaises(ValueError):
            MemoryEntry(
                memory_id="memory-1",
                title="Trend Report",
                content=" ",
                category="trend",
                metadata={},
            )

    def test_empty_category_raises_value_error(self) -> None:
        """An empty category is invalid."""
        with self.assertRaises(ValueError):
            MemoryEntry(
                memory_id="memory-1",
                title="Trend Report",
                content="Content",
                category=" ",
                metadata={},
            )


if __name__ == "__main__":
    unittest.main()
