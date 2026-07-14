"""Tests for the Obsidian memory store."""

import tempfile
import unittest
from pathlib import Path

from engine.memory.models import MemoryEntry
from integrations.obsidian.store import ObsidianMemoryStore


def create_entry(memory_id: str = "memory-1") -> MemoryEntry:
    """Create a memory entry for store tests."""
    return MemoryEntry(
        memory_id=memory_id,
        title="Trend Report",
        content="Content",
        category="trend",
        metadata={"source": "test", "score": 0.9},
    )


class ObsidianMemoryStoreTestCase(unittest.TestCase):
    """Tests for ObsidianMemoryStore behavior."""

    def test_vault_folder_is_created(self) -> None:
        """The store creates the vault folder if needed."""
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path = Path(temp_dir) / "vault"

            ObsidianMemoryStore(vault_path)

            self.assertTrue(vault_path.exists())

    def test_entry_can_be_saved_and_read(self) -> None:
        """A saved entry can be reconstructed from Markdown."""
        with tempfile.TemporaryDirectory() as temp_dir:
            store = ObsidianMemoryStore(Path(temp_dir))
            entry = create_entry()

            store.save(entry)
            result = store.get("memory-1")

            self.assertEqual(result, entry)

    def test_exists_returns_expected_values(self) -> None:
        """exists returns True only for stored entries."""
        with tempfile.TemporaryDirectory() as temp_dir:
            store = ObsidianMemoryStore(Path(temp_dir))
            store.save(create_entry())

            self.assertTrue(store.exists("memory-1"))
            self.assertFalse(store.exists("unknown"))

    def test_delete_removes_entry(self) -> None:
        """delete removes a stored entry."""
        with tempfile.TemporaryDirectory() as temp_dir:
            store = ObsidianMemoryStore(Path(temp_dir))
            store.save(create_entry())

            store.delete("memory-1")

            self.assertFalse(store.exists("memory-1"))

    def test_list_all_returns_entries(self) -> None:
        """list_all returns all stored entries."""
        with tempfile.TemporaryDirectory() as temp_dir:
            store = ObsidianMemoryStore(Path(temp_dir))
            first_entry = create_entry("memory-1")
            second_entry = create_entry("memory-2")
            store.save(first_entry)
            store.save(second_entry)

            result = store.list_all()

            self.assertEqual(result, [first_entry, second_entry])

    def test_duplicate_id_raises_value_error(self) -> None:
        """Saving a duplicate memory ID raises ValueError."""
        with tempfile.TemporaryDirectory() as temp_dir:
            store = ObsidianMemoryStore(Path(temp_dir))
            store.save(create_entry())

            with self.assertRaises(ValueError):
                store.save(create_entry())

    def test_get_unknown_id_raises_key_error(self) -> None:
        """Getting an unknown memory ID raises KeyError."""
        with tempfile.TemporaryDirectory() as temp_dir:
            store = ObsidianMemoryStore(Path(temp_dir))

            with self.assertRaises(KeyError):
                store.get("unknown")

    def test_delete_unknown_id_raises_key_error(self) -> None:
        """Deleting an unknown memory ID raises KeyError."""
        with tempfile.TemporaryDirectory() as temp_dir:
            store = ObsidianMemoryStore(Path(temp_dir))

            with self.assertRaises(KeyError):
                store.delete("unknown")

    def test_unicode_content_round_trips(self) -> None:
        """Unicode content is saved and read using UTF-8."""
        with tempfile.TemporaryDirectory() as temp_dir:
            store = ObsidianMemoryStore(Path(temp_dir))
            entry = MemoryEntry(
                memory_id="unicode",
                title="Überblick",
                content="Trend: Künstliche Intelligenz 🚀",
                category="trends",
                metadata={"sprache": "de"},
            )

            store.save(entry)
            result = store.get("unicode")

            self.assertEqual(result, entry)

    def test_multiple_entries_work(self) -> None:
        """Multiple entries can be stored and read individually."""
        with tempfile.TemporaryDirectory() as temp_dir:
            store = ObsidianMemoryStore(Path(temp_dir))
            first_entry = create_entry("memory-1")
            second_entry = create_entry("memory-2")

            store.save(first_entry)
            store.save(second_entry)

            self.assertEqual(store.get("memory-1"), first_entry)
            self.assertEqual(store.get("memory-2"), second_entry)

    def test_path_traversal_memory_id_is_rejected(self) -> None:
        """Path traversal IDs are rejected."""
        with tempfile.TemporaryDirectory() as temp_dir:
            store = ObsidianMemoryStore(Path(temp_dir))

            with self.assertRaises(ValueError):
                store.save(create_entry("../outside"))

    def test_invalid_memory_id_is_rejected(self) -> None:
        """Invalid memory IDs are rejected."""
        with tempfile.TemporaryDirectory() as temp_dir:
            store = ObsidianMemoryStore(Path(temp_dir))

            with self.assertRaises(ValueError):
                store.save(create_entry("invalid/id"))

    def test_different_store_instances_can_read_same_vault(self) -> None:
        """Different store instances can read entries from the same vault."""
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path = Path(temp_dir)
            first_store = ObsidianMemoryStore(vault_path)
            second_store = ObsidianMemoryStore(vault_path)
            entry = create_entry()

            first_store.save(entry)

            self.assertEqual(second_store.get("memory-1"), entry)


if __name__ == "__main__":
    unittest.main()
