"""Tests for the deterministic operations monitor."""

import unittest
from typing import Any

from engine.alerts.models import AlertSeverity
from engine.alerts.service import AlertService
from engine.events.bus import EventBus
from engine.events.event import Event
from engine.operations.monitor import OperationsMonitor
from engine.retries.coordinator import RetryCoordinator
from engine.retries.policy import RetryPolicy
from engine.runtime.base_agent import BaseAgent
from engine.runtime.capability import AgentCapability
from engine.runtime.runtime import HeliosRuntime
from engine.runtime.status import AgentStatus
from engine.tasks.priority import TaskPriority
from engine.tasks.status import TaskStatus
from engine.supervision.models import SupervisorReport, SupervisorStatus
from engine.supervision.supervisor import SystemSupervisor
from engine.tasks.task import Task


class TestAgent(BaseAgent):
    """Agent implementation used for operations monitor tests."""

    def __init__(
        self,
        agent_id: str = "agent-1",
        name: str = "Test Agent",
        healthy: bool = True,
        should_fail: bool = False,
        result: str = "retry-result",
    ) -> None:
        """Create a configurable test agent."""
        super().__init__(
            agent_id=agent_id,
            name=name,
            capabilities={AgentCapability.STRATEGY},
        )
        self.healthy = healthy
        self.should_fail = should_fail
        self.result = result
        self.health_check_calls = 0
        self.run_calls = 0

    def run(self, task: Task) -> Any:
        """Complete or fail a task based on configuration."""
        self.run_calls += 1
        task.start()
        if self.should_fail:
            task.fail("RuntimeError: retry failed")
            msg = "retry failed"
            raise RuntimeError(msg)

        task.complete(self.result)
        return self.result

    def health_check(self) -> bool:
        """Return the configured health state."""
        self.health_check_calls += 1
        return self.healthy


def create_monitor(
    runtime: HeliosRuntime | None = None,
    retry_coordinator: RetryCoordinator | None = None,
) -> OperationsMonitor:
    """Create a monitor with consistent runtime, supervisor and alert service."""
    selected_runtime = runtime or HeliosRuntime()
    supervisor = SystemSupervisor(
        selected_runtime,
        event_bus=selected_runtime.event_bus,
    )
    alert_service = AlertService(selected_runtime.event_bus)
    return OperationsMonitor(
        selected_runtime,
        supervisor,
        alert_service,
        retry_coordinator=retry_coordinator,
    )


def create_failed_task(error_message: str = "RuntimeError: failed") -> Task:
    """Create a failed task for retry monitor tests."""
    task = Task(
        task_id="task-1",
        title="Retry Task",
        description="A task used for retry monitor tests.",
        priority=TaskPriority.MEDIUM,
        required_capability=AgentCapability.STRATEGY,
        payload={},
    )
    task.start()
    task.fail(error_message)
    return task


class OperationsMonitorTestCase(unittest.TestCase):
    """Tests for OperationsMonitor behavior."""

    def test_constructs_with_shared_instances(self) -> None:
        """Monitor can be constructed when dependencies share runtime services."""
        runtime = HeliosRuntime()
        supervisor = SystemSupervisor(runtime, event_bus=runtime.event_bus)
        alert_service = AlertService(runtime.event_bus)

        monitor = OperationsMonitor(runtime, supervisor, alert_service)

        self.assertIs(monitor.runtime, runtime)
        self.assertIs(monitor.supervisor, supervisor)
        self.assertIs(monitor.alert_service, alert_service)
        self.assertFalse(monitor.running)

    def test_constructs_without_retry_coordinator(self) -> None:
        """RetryCoordinator is optional."""
        monitor = create_monitor()

        self.assertIsNone(monitor.retry_coordinator)

    def test_different_supervisor_runtime_raises_value_error(self) -> None:
        """Supervisor must reference the same runtime as the monitor."""
        runtime = HeliosRuntime()
        other_runtime = HeliosRuntime()
        supervisor = SystemSupervisor(other_runtime, event_bus=runtime.event_bus)
        alert_service = AlertService(runtime.event_bus)

        with self.assertRaisesRegex(ValueError, "same runtime"):
            OperationsMonitor(runtime, supervisor, alert_service)

    def test_different_supervisor_event_bus_raises_value_error(self) -> None:
        """Supervisor must share the runtime event bus."""
        runtime = HeliosRuntime()
        supervisor = SystemSupervisor(runtime, event_bus=EventBus())
        alert_service = AlertService(runtime.event_bus)

        with self.assertRaisesRegex(ValueError, "runtime event bus"):
            OperationsMonitor(runtime, supervisor, alert_service)

    def test_different_alert_service_event_bus_raises_value_error(self) -> None:
        """AlertService must share the runtime event bus."""
        runtime = HeliosRuntime()
        supervisor = SystemSupervisor(runtime, event_bus=runtime.event_bus)
        alert_service = AlertService(EventBus())

        with self.assertRaisesRegex(ValueError, "runtime event bus"):
            OperationsMonitor(runtime, supervisor, alert_service)

    def test_different_retry_coordinator_runtime_raises_value_error(self) -> None:
        """RetryCoordinator must share the runtime instance."""
        runtime = HeliosRuntime()
        other_runtime = HeliosRuntime()
        supervisor = SystemSupervisor(runtime, event_bus=runtime.event_bus)
        alert_service = AlertService(runtime.event_bus)
        retry_coordinator = RetryCoordinator(other_runtime, RetryPolicy())

        with self.assertRaisesRegex(ValueError, "same runtime"):
            OperationsMonitor(
                runtime,
                supervisor,
                alert_service,
                retry_coordinator=retry_coordinator,
            )

    def test_start_starts_alert_service_and_runtime(self) -> None:
        """start first subscribes alerts and starts the runtime."""
        monitor = create_monitor()

        monitor.start()

        self.assertTrue(monitor.running)
        self.assertTrue(monitor.runtime.running)
        self.assertEqual(
            monitor.runtime.event_bus.subscriber_count("supervisor.degraded"),
            1,
        )
        self.assertEqual(
            monitor.runtime.event_bus.subscriber_count("supervisor.unhealthy"),
            1,
        )
        self.assertEqual(monitor.runtime.event_bus.subscriber_count("task.failed"), 1)

    def test_start_is_idempotent(self) -> None:
        """Calling start multiple times does not duplicate subscriptions."""
        monitor = create_monitor()

        monitor.start()
        monitor.start()

        self.assertTrue(monitor.running)
        self.assertTrue(monitor.runtime.running)
        self.assertEqual(
            monitor.runtime.event_bus.subscriber_count("supervisor.degraded"),
            1,
        )

    def test_inspect_before_start_raises_runtime_error(self) -> None:
        """inspect cannot run before the monitor is started."""
        monitor = create_monitor()

        with self.assertRaises(RuntimeError):
            monitor.inspect()

    def test_retry_task_before_start_raises_runtime_error(self) -> None:
        """retry_task cannot run before the monitor is started."""
        runtime = HeliosRuntime()
        monitor = create_monitor(
            runtime,
            retry_coordinator=RetryCoordinator(runtime, RetryPolicy()),
        )

        with self.assertRaises(RuntimeError):
            monitor.retry_task(create_failed_task())

    def test_retry_task_without_coordinator_raises_runtime_error(self) -> None:
        """retry_task requires a configured RetryCoordinator."""
        monitor = create_monitor()
        monitor.start()

        with self.assertRaises(RuntimeError):
            monitor.retry_task(create_failed_task())

    def test_inspect_returns_supervisor_report(self) -> None:
        """inspect returns the SupervisorReport from the supervisor."""
        monitor = create_monitor()
        monitor.start()

        report = monitor.inspect()

        self.assertIsInstance(report, SupervisorReport)
        self.assertIs(report.status, SupervisorStatus.HEALTHY)

    def test_degraded_supervisor_report_creates_alert(self) -> None:
        """A degraded supervisor inspection creates a warning alert."""
        runtime = HeliosRuntime()
        runtime.register(TestAgent(healthy=False))
        monitor = create_monitor(runtime)
        monitor.start()

        report = monitor.inspect()

        self.assertIs(report.status, SupervisorStatus.DEGRADED)
        self.assertEqual(monitor.alert_service.count(), 1)
        self.assertIs(monitor.alert_service.all()[0].severity, AlertSeverity.WARNING)

    def test_unhealthy_supervisor_report_creates_critical_alert(self) -> None:
        """An unhealthy supervisor inspection creates a critical alert."""
        monitor = create_monitor()
        monitor.start()
        monitor.runtime.stop()

        report = monitor.inspect()

        self.assertIs(report.status, SupervisorStatus.UNHEALTHY)
        self.assertEqual(monitor.alert_service.count(), 1)
        self.assertIs(monitor.alert_service.all()[0].severity, AlertSeverity.CRITICAL)

    def test_successful_retry_task_returns_result(self) -> None:
        """retry_task delegates to the coordinator and returns its result."""
        runtime = HeliosRuntime()
        runtime.register(TestAgent(result="ok"))
        retry_coordinator = RetryCoordinator(runtime, RetryPolicy())
        monitor = create_monitor(runtime, retry_coordinator=retry_coordinator)
        task = create_failed_task()
        monitor.start()

        result = monitor.retry_task(task)

        self.assertEqual(result, "ok")
        self.assertIs(task.status, TaskStatus.COMPLETED)

    def test_failed_retry_task_propagates_original_exception(self) -> None:
        """retry_task propagates retry execution errors unchanged."""
        runtime = HeliosRuntime()
        runtime.register(TestAgent(should_fail=True))
        retry_coordinator = RetryCoordinator(runtime, RetryPolicy())
        monitor = create_monitor(runtime, retry_coordinator=retry_coordinator)
        task = create_failed_task()
        monitor.start()

        with self.assertRaisesRegex(RuntimeError, "retry failed"):
            monitor.retry_task(task)

    def test_retry_limit_is_respected(self) -> None:
        """retry_task respects the configured RetryPolicy limit."""
        runtime = HeliosRuntime()
        agent = TestAgent()
        runtime.register(agent)
        retry_coordinator = RetryCoordinator(runtime, RetryPolicy(max_attempts=1))
        monitor = create_monitor(runtime, retry_coordinator=retry_coordinator)
        task = create_failed_task()
        monitor.start()

        with self.assertRaises(RuntimeError):
            monitor.retry_task(task)

        self.assertEqual(agent.run_calls, 0)

    def test_monitor_does_not_modify_retry_policy(self) -> None:
        """retry_task does not mutate the configured RetryPolicy."""
        runtime = HeliosRuntime()
        runtime.register(TestAgent())
        policy = RetryPolicy(max_attempts=3, non_retryable_error_types={"ValueError:"})
        retry_coordinator = RetryCoordinator(runtime, policy)
        monitor = create_monitor(runtime, retry_coordinator=retry_coordinator)
        monitor.start()

        monitor.retry_task(create_failed_task())

        self.assertEqual(policy.max_attempts, 3)
        self.assertEqual(policy.non_retryable_error_types, {"ValueError:"})

    def test_task_failed_event_does_not_trigger_automatic_retry(self) -> None:
        """task.failed events do not trigger automatic retry execution."""
        runtime = HeliosRuntime()
        agent = TestAgent()
        runtime.register(agent)
        retry_coordinator = RetryCoordinator(runtime, RetryPolicy())
        monitor = create_monitor(runtime, retry_coordinator=retry_coordinator)
        monitor.start()

        runtime.event_bus.publish(
            Event(
                event_type="task.failed",
                payload={"task_id": "task-1", "error_message": "failed"},
                source="test",
            ),
        )

        self.assertEqual(agent.run_calls, 0)
        self.assertEqual(retry_coordinator.get_attempts("task-1"), 0)

    def test_stop_stops_runtime_and_alert_service(self) -> None:
        """stop stops the runtime first and removes alert subscriptions."""
        monitor = create_monitor()
        monitor.start()

        monitor.stop()

        self.assertFalse(monitor.running)
        self.assertFalse(monitor.runtime.running)
        self.assertEqual(
            monitor.runtime.event_bus.subscriber_count("supervisor.degraded"),
            0,
        )
        self.assertEqual(
            monitor.runtime.event_bus.subscriber_count("supervisor.unhealthy"),
            0,
        )
        self.assertEqual(monitor.runtime.event_bus.subscriber_count("task.failed"), 0)

    def test_stop_is_idempotent(self) -> None:
        """Calling stop multiple times does not fail."""
        monitor = create_monitor()
        monitor.start()

        monitor.stop()
        monitor.stop()

        self.assertFalse(monitor.running)
        self.assertFalse(monitor.runtime.running)
        self.assertEqual(monitor.alert_service.count(), 0)

    def test_supervisor_events_after_stop_create_no_alerts(self) -> None:
        """Supervisor events after stop do not create alerts."""
        monitor = create_monitor()
        monitor.start()
        monitor.stop()

        monitor.supervisor.inspect()

        self.assertEqual(monitor.alert_service.count(), 0)

    def test_monitor_does_not_modify_agents_directly(self) -> None:
        """Monitor lifecycle does not run or mutate agents directly."""
        runtime = HeliosRuntime()
        agent = TestAgent()
        runtime.register(agent)
        monitor = create_monitor(runtime)
        original_status = agent.status

        monitor.start()
        monitor.inspect()
        monitor.stop()

        self.assertIs(agent.status, original_status)
        self.assertIs(agent.status, AgentStatus.IDLE)
        self.assertEqual(agent.run_calls, 0)
        self.assertEqual(agent.health_check_calls, 1)


if __name__ == "__main__":
    unittest.main()
