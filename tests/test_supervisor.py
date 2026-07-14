"""Tests for the deterministic system supervisor."""

import unittest
from datetime import UTC
from typing import Any

from engine.events.bus import EventBus
from engine.events.event import Event
from engine.runtime.base_agent import BaseAgent
from engine.runtime.runtime import HeliosRuntime
from engine.runtime.status import AgentStatus
from engine.supervision.models import SupervisorStatus
from engine.supervision.supervisor import SystemSupervisor
from engine.tasks.task import Task


class TestAgent(BaseAgent):
    """Agent implementation used for supervisor tests."""

    def __init__(
        self,
        agent_id: str = "agent-1",
        name: str = "Test Agent",
        healthy: bool = True,
        raises_on_health_check: bool = False,
    ) -> None:
        """Create a configurable test agent."""
        super().__init__(agent_id=agent_id, name=name)
        self.healthy = healthy
        self.raises_on_health_check = raises_on_health_check
        self.health_check_calls = 0
        self.run_calls = 0

    def run(self, task: Task) -> Any:
        """Record run calls without doing work."""
        self.run_calls += 1
        return None

    def health_check(self) -> bool:
        """Return the configured health state or raise an error."""
        self.health_check_calls += 1
        if self.raises_on_health_check:
            msg = "health check failed"
            raise RuntimeError(msg)

        return self.healthy


class SystemSupervisorTestCase(unittest.TestCase):
    """Tests for SystemSupervisor behavior."""

    def test_running_runtime_without_agents_is_healthy(self) -> None:
        """A running runtime without registered agents is healthy."""
        runtime = HeliosRuntime()
        runtime.start()

        report = SystemSupervisor(runtime).inspect()

        self.assertIs(report.status, SupervisorStatus.HEALTHY)
        self.assertTrue(report.runtime_running)
        self.assertEqual(report.total_agents, 0)

    def test_stopped_runtime_is_unhealthy(self) -> None:
        """A stopped runtime is unhealthy."""
        runtime = HeliosRuntime()

        report = SystemSupervisor(runtime).inspect()

        self.assertIs(report.status, SupervisorStatus.UNHEALTHY)
        self.assertFalse(report.runtime_running)

    def test_all_healthy_agents_result_in_healthy_status(self) -> None:
        """A running runtime with healthy agents is healthy."""
        runtime = HeliosRuntime()
        runtime.register(TestAgent(agent_id="agent-1", healthy=True))
        runtime.register(TestAgent(agent_id="agent-2", healthy=True))
        runtime.start()

        report = SystemSupervisor(runtime).inspect()

        self.assertIs(report.status, SupervisorStatus.HEALTHY)
        self.assertEqual(report.healthy_agents, 2)
        self.assertEqual(report.unhealthy_agents, 0)

    def test_unhealthy_agent_results_in_degraded_status(self) -> None:
        """A running runtime with an unhealthy agent is degraded."""
        runtime = HeliosRuntime()
        runtime.register(TestAgent(agent_id="agent-1", healthy=True))
        runtime.register(TestAgent(agent_id="agent-2", healthy=False))
        runtime.start()

        report = SystemSupervisor(runtime).inspect()

        self.assertIs(report.status, SupervisorStatus.DEGRADED)
        self.assertEqual(report.healthy_agents, 1)
        self.assertEqual(report.unhealthy_agents, 1)

    def test_health_check_exception_results_in_degraded_status(self) -> None:
        """A health_check exception marks the agent unhealthy."""
        runtime = HeliosRuntime()
        runtime.register(TestAgent(raises_on_health_check=True))
        runtime.start()

        report = SystemSupervisor(runtime).inspect()

        self.assertIs(report.status, SupervisorStatus.DEGRADED)
        self.assertFalse(report.agent_reports[0].healthy)

    def test_counters_are_correct(self) -> None:
        """Supervisor report counters match agent health states."""
        runtime = HeliosRuntime()
        runtime.register(TestAgent(agent_id="agent-1", healthy=True))
        runtime.register(TestAgent(agent_id="agent-2", healthy=False))
        runtime.register(TestAgent(agent_id="agent-3", healthy=True))
        runtime.start()

        report = SystemSupervisor(runtime).inspect()

        self.assertEqual(report.total_agents, 3)
        self.assertEqual(report.healthy_agents, 2)
        self.assertEqual(report.unhealthy_agents, 1)

    def test_agent_status_is_copied_to_report(self) -> None:
        """Agent lifecycle status is copied into the agent report."""
        runtime = HeliosRuntime()
        agent = TestAgent()
        agent.stop()
        runtime.register(agent)
        runtime.start()

        report = SystemSupervisor(runtime).inspect()

        self.assertIs(report.agent_reports[0].status, AgentStatus.STOPPED)

    def test_created_at_uses_utc(self) -> None:
        """Supervisor report created_at is timezone-aware UTC."""
        runtime = HeliosRuntime()
        runtime.start()

        report = SystemSupervisor(runtime).inspect()

        self.assertIs(report.created_at.tzinfo, UTC)

    def test_inspect_does_not_mutate_runtime_or_agents(self) -> None:
        """Inspecting does not start, stop, run, or modify agents."""
        runtime = HeliosRuntime()
        agent = TestAgent()
        runtime.register(agent)
        original_running = runtime.running
        original_status = agent.status

        SystemSupervisor(runtime).inspect()

        self.assertIs(runtime.running, original_running)
        self.assertIs(agent.status, original_status)
        self.assertEqual(agent.run_calls, 0)
        self.assertEqual(agent.health_check_calls, 1)

    def test_multiple_inspections_return_independent_reports(self) -> None:
        """Each inspect call creates an independent report object."""
        runtime = HeliosRuntime()
        runtime.register(TestAgent())
        runtime.start()
        supervisor = SystemSupervisor(runtime)

        first_report = supervisor.inspect()
        second_report = supervisor.inspect()

        self.assertIsNot(first_report, second_report)
        self.assertIsNot(first_report.agent_reports, second_report.agent_reports)
        self.assertIsNot(first_report.agent_reports[0], second_report.agent_reports[0])

    def test_healthy_report_publishes_healthy_event(self) -> None:
        """A healthy report publishes supervisor.healthy."""
        runtime = HeliosRuntime()
        runtime.start()
        event_bus = EventBus()
        events: list[Event] = []
        event_bus.subscribe("supervisor.healthy", events.append)

        SystemSupervisor(runtime, event_bus=event_bus).inspect()

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event_type, "supervisor.healthy")

    def test_degraded_report_publishes_degraded_event(self) -> None:
        """A degraded report publishes supervisor.degraded."""
        runtime = HeliosRuntime()
        runtime.register(TestAgent(healthy=False))
        runtime.start()
        event_bus = EventBus()
        events: list[Event] = []
        event_bus.subscribe("supervisor.degraded", events.append)

        SystemSupervisor(runtime, event_bus=event_bus).inspect()

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event_type, "supervisor.degraded")

    def test_unhealthy_report_publishes_unhealthy_event(self) -> None:
        """An unhealthy report publishes supervisor.unhealthy."""
        runtime = HeliosRuntime()
        event_bus = EventBus()
        events: list[Event] = []
        event_bus.subscribe("supervisor.unhealthy", events.append)

        SystemSupervisor(runtime, event_bus=event_bus).inspect()

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event_type, "supervisor.unhealthy")

    def test_published_event_has_payload_and_source(self) -> None:
        """Published supervisor events include the expected payload and source."""
        runtime = HeliosRuntime()
        runtime.register(TestAgent(agent_id="healthy", healthy=True))
        runtime.register(TestAgent(agent_id="unhealthy", healthy=False))
        runtime.start()
        event_bus = EventBus()
        events: list[Event] = []
        event_bus.subscribe("supervisor.degraded", events.append)

        SystemSupervisor(runtime, event_bus=event_bus).inspect()

        self.assertEqual(events[0].source, "system_supervisor")
        self.assertEqual(
            events[0].payload,
            {
                "status": "DEGRADED",
                "runtime_running": True,
                "total_agents": 2,
                "healthy_agents": 1,
                "unhealthy_agents": 1,
            },
        )

    def test_inspect_publishes_exactly_one_event(self) -> None:
        """Each inspect call publishes exactly one supervisor event."""
        runtime = HeliosRuntime()
        runtime.start()
        event_bus = EventBus()
        events: list[Event] = []
        event_bus.subscribe("supervisor.healthy", events.append)

        SystemSupervisor(runtime, event_bus=event_bus).inspect()

        self.assertEqual(len(events), 1)

    def test_inspect_without_event_bus_does_not_fail(self) -> None:
        """Supervisor still works without an EventBus."""
        runtime = HeliosRuntime()
        runtime.start()

        report = SystemSupervisor(runtime).inspect()

        self.assertIs(report.status, SupervisorStatus.HEALTHY)

    def test_supervisor_instances_do_not_share_event_bus(self) -> None:
        """Supervisor instances only publish to their configured EventBus."""
        runtime = HeliosRuntime()
        runtime.start()
        first_bus = EventBus()
        second_bus = EventBus()
        first_events: list[Event] = []
        second_events: list[Event] = []
        first_bus.subscribe("supervisor.healthy", first_events.append)
        second_bus.subscribe("supervisor.healthy", second_events.append)

        SystemSupervisor(runtime, event_bus=first_bus).inspect()

        self.assertEqual(len(first_events), 1)
        self.assertEqual(second_events, [])

    def test_event_handler_error_is_propagated(self) -> None:
        """Event handler errors are propagated unchanged."""
        runtime = HeliosRuntime()
        runtime.start()
        event_bus = EventBus()

        def failing_handler(event: Event) -> None:
            msg = "handler failed"
            raise RuntimeError(msg)

        event_bus.subscribe("supervisor.healthy", failing_handler)

        with self.assertRaisesRegex(RuntimeError, "handler failed"):
            SystemSupervisor(runtime, event_bus=event_bus).inspect()

    def test_handler_error_does_not_mutate_system_state(self) -> None:
        """A publish failure does not mutate runtime or agent state."""
        runtime = HeliosRuntime()
        agent = TestAgent()
        runtime.register(agent)
        runtime.start()
        original_running = runtime.running
        original_status = agent.status
        event_bus = EventBus()

        def failing_handler(event: Event) -> None:
            msg = "handler failed"
            raise RuntimeError(msg)

        event_bus.subscribe("supervisor.healthy", failing_handler)

        with self.assertRaises(RuntimeError):
            SystemSupervisor(runtime, event_bus=event_bus).inspect()

        self.assertIs(runtime.running, original_running)
        self.assertIs(agent.status, original_status)
        self.assertEqual(agent.run_calls, 0)


if __name__ == "__main__":
    unittest.main()
