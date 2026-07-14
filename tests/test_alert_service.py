"""Tests for the deterministic alert service."""

import unittest
from dataclasses import FrozenInstanceError
from datetime import UTC

from engine.alerts.models import Alert, AlertSeverity
from engine.alerts.service import AlertService
from engine.events.bus import EventBus
from engine.events.event import Event


def supervisor_event(event_type: str) -> Event:
    """Create a supervisor event for alert tests."""
    return Event(
        event_type=event_type,
        source="system_supervisor",
        payload={
            "status": "DEGRADED",
            "runtime_running": True,
            "total_agents": 2,
            "healthy_agents": 1,
            "unhealthy_agents": 1,
        },
    )


def task_failed_event() -> Event:
    """Create a task.failed event for alert tests."""
    return Event(
        event_type="task.failed",
        source="helios_runtime",
        payload={
            "task_id": "task-1",
            "required_capability": "TREND_RESEARCH",
            "priority": "MEDIUM",
            "error_message": "tool failed",
        },
    )


class AlertServiceTestCase(unittest.TestCase):
    """Tests for AlertService behavior."""

    def test_start_registers_required_subscribers(self) -> None:
        """start subscribes to all alert-producing event types."""
        event_bus = EventBus()
        service = AlertService(event_bus)

        service.start()

        self.assertEqual(event_bus.subscriber_count("supervisor.degraded"), 1)
        self.assertEqual(event_bus.subscriber_count("supervisor.unhealthy"), 1)
        self.assertEqual(event_bus.subscriber_count("task.failed"), 1)

    def test_start_is_idempotent(self) -> None:
        """Calling start multiple times does not duplicate subscriptions."""
        event_bus = EventBus()
        service = AlertService(event_bus)

        service.start()
        service.start()

        self.assertEqual(event_bus.subscriber_count("supervisor.degraded"), 1)
        self.assertEqual(event_bus.subscriber_count("supervisor.unhealthy"), 1)
        self.assertEqual(event_bus.subscriber_count("task.failed"), 1)

    def test_stop_removes_subscribers(self) -> None:
        """stop removes the alert service subscriptions."""
        event_bus = EventBus()
        service = AlertService(event_bus)
        service.start()

        service.stop()

        self.assertEqual(event_bus.subscriber_count("supervisor.degraded"), 0)
        self.assertEqual(event_bus.subscriber_count("supervisor.unhealthy"), 0)
        self.assertEqual(event_bus.subscriber_count("task.failed"), 0)

    def test_stop_is_idempotent(self) -> None:
        """Calling stop multiple times does not fail."""
        service = AlertService(EventBus())

        service.stop()
        service.start()
        service.stop()
        service.stop()

        self.assertEqual(service.count(), 0)

    def test_supervisor_degraded_creates_warning_alert(self) -> None:
        """supervisor.degraded creates a warning alert."""
        event_bus = EventBus()
        service = AlertService(event_bus)
        service.start()

        event_bus.publish(supervisor_event("supervisor.degraded"))

        alert = service.all()[0]
        self.assertIs(alert.severity, AlertSeverity.WARNING)
        self.assertEqual(alert.title, "System degraded")

    def test_supervisor_unhealthy_creates_critical_alert(self) -> None:
        """supervisor.unhealthy creates a critical alert."""
        event_bus = EventBus()
        service = AlertService(event_bus)
        service.start()

        event_bus.publish(supervisor_event("supervisor.unhealthy"))

        alert = service.all()[0]
        self.assertIs(alert.severity, AlertSeverity.CRITICAL)
        self.assertEqual(alert.title, "System unhealthy")

    def test_task_failed_creates_warning_alert(self) -> None:
        """task.failed creates a warning alert."""
        event_bus = EventBus()
        service = AlertService(event_bus)
        service.start()

        event_bus.publish(task_failed_event())

        alert = service.all()[0]
        self.assertIs(alert.severity, AlertSeverity.WARNING)
        self.assertEqual(alert.title, "Task failed")
        self.assertIn("task-1", alert.message)
        self.assertIn("tool failed", alert.message)

    def test_supervisor_healthy_creates_no_alert(self) -> None:
        """supervisor.healthy does not create an alert."""
        event_bus = EventBus()
        service = AlertService(event_bus)
        service.start()

        event_bus.publish(supervisor_event("supervisor.healthy"))

        self.assertEqual(service.count(), 0)

    def test_event_source_is_copied_to_alert(self) -> None:
        """Alert source is copied from the event."""
        event_bus = EventBus()
        service = AlertService(event_bus)
        service.start()

        event_bus.publish(task_failed_event())

        self.assertEqual(service.all()[0].source, "helios_runtime")

    def test_payload_is_copied_to_independent_metadata(self) -> None:
        """Alert metadata is a copy of the event payload."""
        event_bus = EventBus()
        service = AlertService(event_bus)
        service.start()
        event = task_failed_event()

        event_bus.publish(event)

        alert = service.all()[0]
        self.assertEqual(alert.metadata, event.payload)
        self.assertIsNot(alert.metadata, event.payload)

    def test_multiple_events_create_alerts_in_order(self) -> None:
        """Alerts are stored in event creation order."""
        event_bus = EventBus()
        service = AlertService(event_bus)
        service.start()

        event_bus.publish(supervisor_event("supervisor.degraded"))
        event_bus.publish(task_failed_event())
        event_bus.publish(supervisor_event("supervisor.unhealthy"))

        self.assertEqual(
            [alert.event_type for alert in service.all()],
            ["supervisor.degraded", "task.failed", "supervisor.unhealthy"],
        )

    def test_all_returns_a_new_list(self) -> None:
        """all protects the internal alert storage list."""
        event_bus = EventBus()
        service = AlertService(event_bus)
        service.start()
        event_bus.publish(task_failed_event())

        alerts = service.all()
        alerts.clear()

        self.assertEqual(service.count(), 1)

    def test_count_and_clear_work(self) -> None:
        """count and clear expose and reset stored alert count."""
        event_bus = EventBus()
        service = AlertService(event_bus)
        service.start()
        event_bus.publish(task_failed_event())

        self.assertEqual(service.count(), 1)

        service.clear()

        self.assertEqual(service.count(), 0)

    def test_events_after_stop_create_no_alerts(self) -> None:
        """Events published after stop are ignored."""
        event_bus = EventBus()
        service = AlertService(event_bus)
        service.start()
        service.stop()

        event_bus.publish(task_failed_event())

        self.assertEqual(service.count(), 0)

    def test_alert_created_at_uses_utc(self) -> None:
        """Alert created_at is timezone-aware UTC."""
        event_bus = EventBus()
        service = AlertService(event_bus)
        service.start()

        event_bus.publish(task_failed_event())

        self.assertIs(service.all()[0].created_at.tzinfo, UTC)

    def test_alert_is_immutable(self) -> None:
        """Alert dataclass is immutable."""
        alert = Alert(
            alert_id="alert-1",
            event_type="task.failed",
            severity=AlertSeverity.WARNING,
            title="Task failed",
            message="Task failed.",
            source="test",
            metadata={},
        )

        with self.assertRaises(FrozenInstanceError):
            setattr(alert, "title", "Changed")


if __name__ == "__main__":
    unittest.main()
