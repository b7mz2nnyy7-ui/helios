"""Deterministic alert service for Helios system events."""

import uuid
from typing import Any

from engine.alerts.models import Alert, AlertSeverity
from engine.events.bus import EventBus
from engine.events.event import Event


class AlertService:
    """Creates in-memory alerts from subscribed system events."""

    _EVENT_MAPPINGS = {
        "supervisor.degraded": (
            AlertSeverity.WARNING,
            "System degraded",
        ),
        "supervisor.unhealthy": (
            AlertSeverity.CRITICAL,
            "System unhealthy",
        ),
        "task.failed": (
            AlertSeverity.WARNING,
            "Task failed",
        ),
    }

    def __init__(self, event_bus: EventBus) -> None:
        """Create an alert service for an event bus."""
        self.event_bus = event_bus
        self._alerts: list[Alert] = []
        self._started = False

    def start(self) -> None:
        """Subscribe the service to alert-producing event types."""
        if self._started:
            return

        for event_type in self._EVENT_MAPPINGS:
            self.event_bus.subscribe(event_type, self._handle_event)

        self._started = True

    def stop(self) -> None:
        """Remove the service subscriptions from the event bus."""
        if not self._started:
            return

        for event_type in self._EVENT_MAPPINGS:
            self.event_bus.unsubscribe(event_type, self._handle_event)

        self._started = False

    def all(self) -> list[Alert]:
        """Return all alerts in creation order."""
        return list(self._alerts)

    def count(self) -> int:
        """Return the number of stored alerts."""
        return len(self._alerts)

    def clear(self) -> None:
        """Remove all stored alerts."""
        self._alerts.clear()

    def _handle_event(self, event: Event) -> None:
        severity, title = self._EVENT_MAPPINGS[event.event_type]
        self._alerts.append(
            Alert(
                alert_id=uuid.uuid4().hex,
                event_type=event.event_type,
                severity=severity,
                title=title,
                message=self._message_for(event),
                source=event.source,
                metadata=dict(event.payload),
            ),
        )

    def _message_for(self, event: Event) -> str:
        payload = event.payload
        if event.event_type.startswith("supervisor."):
            return self._supervisor_message(payload)

        if event.event_type == "task.failed":
            return self._task_failed_message(payload)

        return f"Event {event.event_type} created an alert."

    def _supervisor_message(self, payload: dict[str, Any]) -> str:
        status = payload.get("status", "UNKNOWN")
        total_agents = payload.get("total_agents", 0)
        healthy_agents = payload.get("healthy_agents", 0)
        unhealthy_agents = payload.get("unhealthy_agents", 0)
        return (
            f"Supervisor status {status}: {healthy_agents}/{total_agents} "
            f"agents healthy, {unhealthy_agents} unhealthy."
        )

    def _task_failed_message(self, payload: dict[str, Any]) -> str:
        task_id = payload.get("task_id", "unknown")
        error_message = payload.get("error_message", "No error message provided.")
        return f"Task {task_id} failed: {error_message}"

