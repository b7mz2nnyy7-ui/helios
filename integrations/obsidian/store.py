"""Obsidian-backed memory store."""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from engine.memory.base_store import BaseMemoryStore
from engine.memory.models import MemoryEntry


class ObsidianMemoryStore(BaseMemoryStore):
    """Memory store that writes entries as Markdown files in an Obsidian vault."""

    _SAFE_MEMORY_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")

    def __init__(self, vault_path: Path) -> None:
        """Create an Obsidian memory store for a vault path."""
        self.vault_path = vault_path
        self.vault_path.mkdir(parents=True, exist_ok=True)

    def save(self, entry: MemoryEntry) -> None:
        """Save a memory entry as a Markdown file.

        Raises:
            ValueError: If the memory ID is invalid or already exists.
        """
        path = self._path_for(entry.memory_id)
        if path.exists():
            msg = f"Memory entry '{entry.memory_id}' already exists."
            raise ValueError(msg)

        path.write_text(self._serialize(entry), encoding="utf-8")

    def get(self, memory_id: str) -> MemoryEntry:
        """Return a memory entry by ID.

        Raises:
            KeyError: If the entry does not exist.
        """
        path = self._path_for(memory_id)
        if not path.exists():
            raise KeyError(memory_id)

        return self._deserialize(path.read_text(encoding="utf-8"))

    def exists(self, memory_id: str) -> bool:
        """Return whether a memory entry exists."""
        return self._path_for(memory_id).exists()

    def delete(self, memory_id: str) -> None:
        """Delete a memory entry by ID.

        Raises:
            KeyError: If the entry does not exist.
        """
        path = self._path_for(memory_id)
        if not path.exists():
            raise KeyError(memory_id)

        path.unlink()

    def list_all(self) -> list[MemoryEntry]:
        """Return all memory entries in the vault."""
        return [
            self._deserialize(path.read_text(encoding="utf-8"))
            for path in sorted(self.vault_path.glob("*.md"))
        ]

    def _path_for(self, memory_id: str) -> Path:
        self._validate_memory_id(memory_id)
        return self.vault_path / f"{memory_id}.md"

    def _validate_memory_id(self, memory_id: str) -> None:
        if not self._SAFE_MEMORY_ID_PATTERN.fullmatch(memory_id):
            msg = f"Invalid memory_id: {memory_id}"
            raise ValueError(msg)

    def _serialize(self, entry: MemoryEntry) -> str:
        metadata = json.dumps(entry.metadata, ensure_ascii=False, sort_keys=True)
        return (
            "---\n"
            f"memory_id: {entry.memory_id}\n"
            f"title: {entry.title}\n"
            f"category: {entry.category}\n"
            f"created_at: {entry.created_at.isoformat()}\n"
            f"metadata: {metadata}\n"
            "---\n\n"
            f"# {entry.title}\n\n"
            f"{entry.content}\n"
        )

    def _deserialize(self, text: str) -> MemoryEntry:
        header, content = self._split_markdown(text)
        header_values = self._parse_header(header)
        body = self._parse_body(content, header_values["title"])
        metadata = json.loads(header_values["metadata"])

        return MemoryEntry(
            memory_id=header_values["memory_id"],
            title=header_values["title"],
            content=body,
            category=header_values["category"],
            metadata=self._ensure_metadata_dict(metadata),
            created_at=datetime.fromisoformat(header_values["created_at"]),
        )

    def _split_markdown(self, text: str) -> tuple[str, str]:
        parts = text.split("---", maxsplit=2)
        if len(parts) != 3 or parts[0] != "":
            msg = "Invalid memory markdown format."
            raise ValueError(msg)

        return parts[1].strip(), parts[2].lstrip()

    def _parse_header(self, header: str) -> dict[str, str]:
        values: dict[str, str] = {}
        for line in header.splitlines():
            key, separator, value = line.partition(": ")
            if not separator:
                msg = f"Invalid header line: {line}"
                raise ValueError(msg)
            values[key] = value

        return values

    def _parse_body(self, body: str, title: str) -> str:
        heading = f"# {title}\n\n"
        if not body.startswith(heading):
            msg = "Invalid memory markdown body."
            raise ValueError(msg)

        return body.removeprefix(heading).rstrip("\n")

    def _ensure_metadata_dict(self, metadata: Any) -> dict[str, Any]:
        if not isinstance(metadata, dict):
            msg = "metadata must be a dictionary."
            raise ValueError(msg)

        return metadata
