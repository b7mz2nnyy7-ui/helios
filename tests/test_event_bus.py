"""Tests for the synchronous event bus."""

import unittest

from engine.events.bus import EventBus
from engine.events.event import Event


class EventBusTestCase(unittest.TestCase):
    """Tests for EventBus behavior."""

    def test_handler_can_be_subscribed(self) -> None:
        """A handler can be subscribed to an event type."""
        bus = EventBus()

        def handler(event: Event) -> None:
            pass

        bus.subscribe("test.event", handler)

        self.assertEqual(bus.subscriber_count("test.event"), 1)

    def test_publish_reaches_matching_handler(self) -> None:
        """Publishing an event calls a matching handler."""
        bus = EventBus()
        received_events: list[Event] = []

        def handler(event: Event) -> None:
            received_events.append(event)

        event = Event(event_type="test.event")
        bus.subscribe("test.event", handler)

        bus.publish(event)

        self.assertEqual(received_events, [event])

    def test_publish_passes_same_event_object(self) -> None:
        """Publishing passes the original event object to the handler."""
        bus = EventBus()
        received_event: list[Event] = []

        def handler(event: Event) -> None:
            received_event.append(event)

        event = Event(event_type="test.event")
        bus.subscribe("test.event", handler)

        bus.publish(event)

        self.assertIs(received_event[0], event)

    def test_multiple_handlers_receive_same_event(self) -> None:
        """Multiple handlers receive the same published event."""
        bus = EventBus()
        received_events: list[Event] = []

        def first_handler(event: Event) -> None:
            received_events.append(event)

        def second_handler(event: Event) -> None:
            received_events.append(event)

        event = Event(event_type="test.event")
        bus.subscribe("test.event", first_handler)
        bus.subscribe("test.event", second_handler)

        bus.publish(event)

        self.assertEqual(received_events, [event, event])

    def test_handlers_are_called_in_registration_order(self) -> None:
        """Handlers are called in the order they were registered."""
        bus = EventBus()
        calls: list[str] = []

        def first_handler(event: Event) -> None:
            calls.append("first")

        def second_handler(event: Event) -> None:
            calls.append("second")

        bus.subscribe("test.event", first_handler)
        bus.subscribe("test.event", second_handler)

        bus.publish(Event(event_type="test.event"))

        self.assertEqual(calls, ["first", "second"])

    def test_handler_for_other_event_type_is_not_called(self) -> None:
        """A handler for another event type is not called."""
        bus = EventBus()
        calls: list[str] = []

        def handler(event: Event) -> None:
            calls.append(event.event_type)

        bus.subscribe("other.event", handler)

        bus.publish(Event(event_type="test.event"))

        self.assertEqual(calls, [])

    def test_publish_without_subscribers_does_not_fail(self) -> None:
        """Publishing without subscribers does nothing."""
        bus = EventBus()

        bus.publish(Event(event_type="test.event"))

        self.assertEqual(bus.subscriber_count("test.event"), 0)

    def test_duplicate_handler_registration_raises_value_error(self) -> None:
        """Subscribing the same handler twice raises ValueError."""
        bus = EventBus()

        def handler(event: Event) -> None:
            pass

        bus.subscribe("test.event", handler)

        with self.assertRaises(ValueError):
            bus.subscribe("test.event", handler)

    def test_handler_can_be_unsubscribed(self) -> None:
        """A subscribed handler can be removed."""
        bus = EventBus()

        def handler(event: Event) -> None:
            pass

        bus.subscribe("test.event", handler)
        bus.unsubscribe("test.event", handler)

        self.assertEqual(bus.subscriber_count("test.event"), 0)

    def test_unsubscribe_unknown_event_type_raises_key_error(self) -> None:
        """Unsubscribing from an unknown event type raises KeyError."""
        bus = EventBus()

        def handler(event: Event) -> None:
            pass

        with self.assertRaises(KeyError):
            bus.unsubscribe("unknown.event", handler)

    def test_unsubscribe_unknown_handler_raises_key_error(self) -> None:
        """Unsubscribing an unknown handler raises KeyError."""
        bus = EventBus()

        def subscribed_handler(event: Event) -> None:
            pass

        def unknown_handler(event: Event) -> None:
            pass

        bus.subscribe("test.event", subscribed_handler)

        with self.assertRaises(KeyError):
            bus.unsubscribe("test.event", unknown_handler)

    def test_subscriber_count_returns_correct_values(self) -> None:
        """subscriber_count returns the number of handlers for an event type."""
        bus = EventBus()

        def first_handler(event: Event) -> None:
            pass

        def second_handler(event: Event) -> None:
            pass

        bus.subscribe("test.event", first_handler)
        bus.subscribe("test.event", second_handler)

        self.assertEqual(bus.subscriber_count("test.event"), 2)
        self.assertEqual(bus.subscriber_count("unknown.event"), 0)

    def test_clear_removes_all_subscriptions(self) -> None:
        """clear removes all subscriptions."""
        bus = EventBus()

        def handler(event: Event) -> None:
            pass

        bus.subscribe("test.event", handler)
        bus.subscribe("other.event", handler)

        bus.clear()

        self.assertEqual(bus.subscriber_count("test.event"), 0)
        self.assertEqual(bus.subscriber_count("other.event"), 0)

    def test_handler_exception_is_propagated(self) -> None:
        """Exceptions raised by handlers are propagated to the caller."""
        bus = EventBus()

        def handler(event: Event) -> None:
            msg = "handler failed"
            raise RuntimeError(msg)

        bus.subscribe("test.event", handler)

        with self.assertRaises(RuntimeError):
            bus.publish(Event(event_type="test.event"))


if __name__ == "__main__":
    unittest.main()
