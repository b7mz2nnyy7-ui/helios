"""Synchronous event bus implementation."""

from engine.events.event import Event, EventHandler


class EventBus:
    """Synchronous event bus for publishing and subscribing to events."""

    def __init__(self) -> None:
        """Create an empty event bus."""
        self._subscribers: dict[str, list[EventHandler]] = {}

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """Subscribe a handler to an event type.

        Raises:
            ValueError: If the handler is already subscribed to the event type.
        """
        handlers = self._subscribers.setdefault(event_type, [])
        if handler in handlers:
            msg = f"Handler is already subscribed to event type '{event_type}'."
            raise ValueError(msg)

        handlers.append(handler)

    def unsubscribe(self, event_type: str, handler: EventHandler) -> None:
        """Unsubscribe a handler from an event type.

        Raises:
            KeyError: If the event type or handler is not registered.
        """
        if event_type not in self._subscribers:
            raise KeyError(event_type)

        handlers = self._subscribers[event_type]
        if handler not in handlers:
            raise KeyError(event_type)

        handlers.remove(handler)
        if not handlers:
            del self._subscribers[event_type]

    def publish(self, event: Event) -> None:
        """Publish an event to all matching subscribers."""
        for handler in self._subscribers.get(event.event_type, []):
            handler(event)

    def subscriber_count(self, event_type: str) -> int:
        """Return the number of subscribers for an event type."""
        return len(self._subscribers.get(event_type, []))

    def clear(self) -> None:
        """Remove all subscriptions."""
        self._subscribers.clear()
