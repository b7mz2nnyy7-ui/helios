"""Tests for the Helios runtime."""

import unittest
from typing import Any

from engine.events.event import Event
from engine.runtime.base_agent import BaseAgent
from engine.runtime.capability import AgentCapability
from engine.runtime.dispatcher import TaskDispatcher
from engine.runtime.registry import AgentRegistry
from engine.runtime.runtime import HeliosRuntime
from engine.tasks.priority import TaskPriority
from engine.tasks.task import Task


class TestAgent(BaseAgent):
    """Concrete test agent that records run calls."""

    def __init__(
        self,
        agent_id: str,
        name: str,
        capabilities: set[AgentCapability] | None = None,
        healthy: bool = True,
    ) -> None:
        """Create a test agent."""
        super().__init__(
            agent_id=agent_id,
            name=name,
            capabilities=capabilities or set(),
        )
        self.run_called = False
        self.received_task: Task | None = None
        self.result = "runtime-result"
        self.healthy = healthy

    def run(self, task: Task) -> Any:
        """Record that the agent was run."""
        self.run_called = True
        self.received_task = task
        return self.result

    def health_check(self) -> bool:
        """Return the configured health state."""
        return self.healthy


class SpyTaskDispatcher(TaskDispatcher):
    """Dispatcher that records dispatch calls for runtime tests."""

    def __init__(self) -> None:
        """Create a spy dispatcher."""
        super().__init__(AgentRegistry())
        self.dispatched_task: Task | None = None
        self.result = "dispatcher-result"

    def dispatch(self, task: Task) -> Any:
        """Record the dispatch call."""
        self.dispatched_task = task
        return self.result


class FailingTaskDispatcher(TaskDispatcher):
    """Dispatcher that always fails for runtime tests."""

    def __init__(self) -> None:
        """Create a failing dispatcher."""
        super().__init__(AgentRegistry())

    def dispatch(self, task: Task) -> Any:
        """Raise a runtime error."""
        msg = "dispatch failed"
        raise RuntimeError(msg)


def create_task() -> Task:
    """Create a test task."""
    return Task(
        task_id="task-1",
        title="Test Task",
        description="A task used for runtime tests.",
        priority=TaskPriority.MEDIUM,
        required_capability=AgentCapability.STRATEGY,
        payload={},
    )


class HeliosRuntimeTestCase(unittest.TestCase):
    """Tests for HeliosRuntime behavior."""

    def test_runtime_starts_correctly(self) -> None:
        """Starting the runtime sets running to True."""
        runtime = HeliosRuntime()

        runtime.start()

        self.assertTrue(runtime.running)

    def test_start_publishes_runtime_started_event(self) -> None:
        """Starting the runtime publishes exactly one runtime.started event."""
        runtime = HeliosRuntime()
        events: list[Event] = []
        runtime.event_bus.subscribe("runtime.started", events.append)

        runtime.start()

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event_type, "runtime.started")

    def test_start_event_has_helios_runtime_source(self) -> None:
        """The runtime started event has the runtime source."""
        runtime = HeliosRuntime()
        events: list[Event] = []
        runtime.event_bus.subscribe("runtime.started", events.append)

        runtime.start()

        self.assertEqual(events[0].source, "helios_runtime")

    def test_runtime_stops_correctly(self) -> None:
        """Stopping the runtime sets running to False."""
        runtime = HeliosRuntime()
        runtime.start()

        runtime.stop()

        self.assertFalse(runtime.running)

    def test_stop_publishes_runtime_stopped_event(self) -> None:
        """Stopping the runtime publishes exactly one runtime.stopped event."""
        runtime = HeliosRuntime()
        events: list[Event] = []
        runtime.event_bus.subscribe("runtime.stopped", events.append)

        runtime.stop()

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event_type, "runtime.stopped")

    def test_agent_can_be_registered(self) -> None:
        """An agent can be registered through the runtime."""
        runtime = HeliosRuntime()
        agent = TestAgent(agent_id="agent-1", name="Test Agent")

        runtime.register(agent)

        self.assertTrue(runtime.registry.exists("agent-1"))

    def test_agent_can_be_removed(self) -> None:
        """An agent can be unregistered through the runtime."""
        runtime = HeliosRuntime()
        agent = TestAgent(agent_id="agent-1", name="Test Agent")
        runtime.register(agent)

        runtime.unregister("agent-1")

        self.assertFalse(runtime.registry.exists("agent-1"))

    def test_submit_task_calls_agent_run(self) -> None:
        """Submitting a task calls run on the selected agent."""
        runtime = HeliosRuntime()
        agent = TestAgent(
            agent_id="agent-1",
            name="Test Agent",
            capabilities={AgentCapability.STRATEGY},
        )
        task = create_task()
        runtime.register(agent)

        runtime.submit_task(task)

        self.assertTrue(agent.run_called)

    def test_submit_task_publishes_task_dispatched_event(self) -> None:
        """Submitting a task publishes one task.dispatched event after dispatch."""
        runtime = HeliosRuntime()
        events: list[Event] = []
        agent = TestAgent(
            agent_id="agent-1",
            name="Test Agent",
            capabilities={AgentCapability.STRATEGY},
        )
        task = create_task()
        runtime.register(agent)
        runtime.event_bus.subscribe("task.dispatched", events.append)

        runtime.submit_task(task)

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event_type, "task.dispatched")

    def test_task_dispatched_event_contains_task_payload(self) -> None:
        """The task dispatched event contains task details as strings."""
        runtime = HeliosRuntime()
        events: list[Event] = []
        agent = TestAgent(
            agent_id="agent-1",
            name="Test Agent",
            capabilities={AgentCapability.STRATEGY},
        )
        task = create_task()
        runtime.register(agent)
        runtime.event_bus.subscribe("task.dispatched", events.append)

        runtime.submit_task(task)

        self.assertEqual(
            events[0].payload,
            {
                "task_id": "task-1",
                "required_capability": "STRATEGY",
                "priority": "MEDIUM",
            },
        )

    def test_runtime_event_object_is_passed_to_subscriber(self) -> None:
        """The original runtime event object is passed to subscribers."""
        runtime = HeliosRuntime()
        first_events: list[Event] = []
        second_events: list[Event] = []
        runtime.event_bus.subscribe("runtime.started", first_events.append)
        runtime.event_bus.subscribe("runtime.started", second_events.append)

        runtime.start()

        self.assertIs(first_events[0], second_events[0])

    def test_failed_dispatch_does_not_publish_task_dispatched_event(self) -> None:
        """A failed dispatch does not publish a task.dispatched event."""
        runtime = HeliosRuntime()
        events: list[Event] = []
        runtime.event_bus.subscribe("task.dispatched", events.append)

        with self.assertRaises(ValueError):
            runtime.submit_task(create_task())

        self.assertEqual(events, [])

    def test_failed_dispatch_publishes_task_failed_event(self) -> None:
        """A failed dispatch publishes a task.failed event."""
        runtime = HeliosRuntime()
        events: list[Event] = []
        runtime.dispatcher = FailingTaskDispatcher()
        runtime.event_bus.subscribe("task.failed", events.append)

        with self.assertRaises(RuntimeError):
            runtime.submit_task(create_task())

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event_type, "task.failed")

    def test_task_failed_event_contains_task_and_error_payload(self) -> None:
        """The task.failed event contains task details and the error message."""
        runtime = HeliosRuntime()
        events: list[Event] = []
        runtime.dispatcher = FailingTaskDispatcher()
        runtime.event_bus.subscribe("task.failed", events.append)

        with self.assertRaises(RuntimeError):
            runtime.submit_task(create_task())

        self.assertEqual(
            events[0].payload,
            {
                "task_id": "task-1",
                "required_capability": "STRATEGY",
                "priority": "MEDIUM",
                "error_message": "dispatch failed",
            },
        )

    def test_submit_task_uses_dispatcher(self) -> None:
        """Submitting a task delegates execution to the dispatcher."""
        runtime = HeliosRuntime()
        dispatcher = SpyTaskDispatcher()
        task = create_task()
        runtime.dispatcher = dispatcher

        runtime.submit_task(task)

        self.assertIs(dispatcher.dispatched_task, task)

    def test_submit_task_returns_dispatcher_result(self) -> None:
        """Submitting a task returns the dispatcher's result."""
        runtime = HeliosRuntime()
        dispatcher = SpyTaskDispatcher()
        task = create_task()
        runtime.dispatcher = dispatcher

        result = runtime.submit_task(task)

        self.assertEqual(result, "dispatcher-result")

    def test_submit_task_uses_capability_routing(self) -> None:
        """Submitting a task routes it to an agent with the required capability."""
        runtime = HeliosRuntime()
        first_agent = TestAgent(
            agent_id="agent-1",
            name="First Agent",
            capabilities={AgentCapability.ANALYTICS},
        )
        second_agent = TestAgent(
            agent_id="agent-2",
            name="Second Agent",
            capabilities={AgentCapability.STRATEGY},
        )
        task = create_task()
        runtime.register(first_agent)
        runtime.register(second_agent)

        runtime.submit_task(task)

        self.assertFalse(first_agent.run_called)
        self.assertIs(second_agent.received_task, task)

    def test_runtime_instances_have_different_event_buses(self) -> None:
        """Different runtime instances do not share the same event bus."""
        first_runtime = HeliosRuntime()
        second_runtime = HeliosRuntime()

        self.assertIsNot(first_runtime.event_bus, second_runtime.event_bus)

    def test_inspect_health_returns_structured_runtime_health(self) -> None:
        """Runtime health includes running state and agent counts."""
        runtime = HeliosRuntime()
        runtime.register(TestAgent(agent_id="agent-1", name="Healthy Agent"))
        runtime.start()

        health = runtime.inspect_health()

        self.assertTrue(health.healthy)
        self.assertTrue(health.running)
        self.assertEqual(health.agent_count, 1)
        self.assertEqual(health.healthy_agents, ["agent-1"])
        self.assertEqual(health.unhealthy_agents, [])

    def test_inspect_health_reports_unhealthy_agents(self) -> None:
        """Runtime health reports unhealthy registered agents."""
        runtime = HeliosRuntime()
        runtime.register(TestAgent(agent_id="agent-1", name="Healthy Agent"))
        runtime.register(
            TestAgent(agent_id="agent-2", name="Unhealthy Agent", healthy=False),
        )
        runtime.start()

        health = runtime.inspect_health()

        self.assertFalse(health.healthy)
        self.assertEqual(health.healthy_agents, ["agent-1"])
        self.assertEqual(health.unhealthy_agents, ["agent-2"])

    def test_runtime_health_check_requires_running_runtime(self) -> None:
        """Runtime health_check is false when the runtime is stopped."""
        runtime = HeliosRuntime()
        runtime.register(TestAgent(agent_id="agent-1", name="Healthy Agent"))

        self.assertFalse(runtime.health_check())

    def test_runtime_health_check_is_true_when_running_and_agents_are_healthy(
        self,
    ) -> None:
        """Runtime health_check is true when runtime and agents are healthy."""
        runtime = HeliosRuntime()
        runtime.register(TestAgent(agent_id="agent-1", name="Healthy Agent"))
        runtime.start()

        self.assertTrue(runtime.health_check())


if __name__ == "__main__":
    unittest.main()
