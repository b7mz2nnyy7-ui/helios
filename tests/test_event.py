"""Tests for the event model."""

import unittest
from dataclasses import FrozenInstanceError
from datetime import UTC

from engine.events.event import Event


class EventTestCase(unittest.TestCase):
    """Tests for Event behavior."""

    def test_payload_defaults_to_empty_dictionary(self) -> None:
        """A new event has an empty payload by default."""
        event = Event(event_type="test.event")

        self.assertEqual(event.payload, {})

    def test_created_at_uses_utc_timezone(self) -> None:
        """A new event timestamp is created in UTC."""
        event = Event(event_type="test.event")

        self.assertIs(event.created_at.tzinfo, UTC)

    def test_source_defaults_to_none(self) -> None:
        """A new event has no source by default."""
        event = Event(event_type="test.event")

        self.assertIsNone(event.source)

    def test_event_is_immutable(self) -> None:
        """An event cannot be modified after creation."""
        event = Event(event_type="test.event")

        with self.assertRaises(FrozenInstanceError):
            event.source = "changed"  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()
