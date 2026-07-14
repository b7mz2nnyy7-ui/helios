"""Tests for the task dispatcher."""

import unittest
from typing import Any

from engine.runtime.base_agent import BaseAgent
from engine.runtime.capability import AgentCapability
from engine.runtime.dispatcher import TaskDispatcher
from engine.runtime.registry import AgentRegistry
from engine.tasks.priority import TaskPriority
from engine.tasks.task import Task


class RecordingAgent(BaseAgent):
    """Test agent that records the task it receives."""

    def __init__(
        self,
        agent_id: str,
        name: str,
        capabilities: set[AgentCapability] | None = None,
    ) -> None:
        """Create a recording agent."""
        super().__init__(
            agent_id=agent_id,
            name=name,
            capabilities=capabilities or set(),
        )
        self.run_called = False
        self.received_task: Task | None = None
        self.result = "dispatch-result"

    def run(self, task: Task) -> Any:
        """Record the dispatched task."""
        self.run_called = True
        self.received_task = task
        return self.result


def create_task() -> Task:
    """Create a test task."""
    return Task(
        task_id="task-1",
        title="Test Task",
        description="A task used for dispatcher tests.",
        priority=TaskPriority.MEDIUM,
        required_capability=AgentCapability.STRATEGY,
        payload={},
    )


class TaskDispatcherTestCase(unittest.TestCase):
    """Tests for TaskDispatcher behavior."""

    def test_dispatch_finds_agent_by_capability(self) -> None:
        """Dispatch calls an agent with the required capability."""
        registry = AgentRegistry()
        first_agent = RecordingAgent(
            agent_id="agent-1",
            name="First Agent",
            capabilities={AgentCapability.ANALYTICS},
        )
        second_agent = RecordingAgent(
            agent_id="agent-2",
            name="Second Agent",
            capabilities={AgentCapability.STRATEGY},
        )
        task = create_task()
        registry.register(first_agent)
        registry.register(second_agent)
        dispatcher = TaskDispatcher(registry)

        dispatcher.dispatch(task)

        self.assertFalse(first_agent.run_called)
        self.assertTrue(second_agent.run_called)

    def test_dispatch_uses_first_matching_agent(self) -> None:
        """Dispatch uses the first registered agent with the capability."""
        registry = AgentRegistry()
        first_agent = RecordingAgent(
            agent_id="agent-1",
            name="First Agent",
            capabilities={AgentCapability.STRATEGY},
        )
        second_agent = RecordingAgent(
            agent_id="agent-2",
            name="Second Agent",
            capabilities={AgentCapability.STRATEGY},
        )
        task = create_task()
        registry.register(first_agent)
        registry.register(second_agent)
        dispatcher = TaskDispatcher(registry)

        dispatcher.dispatch(task)

        self.assertTrue(first_agent.run_called)
        self.assertFalse(second_agent.run_called)

    def test_dispatch_without_matching_agent_raises_value_error(self) -> None:
        """Dispatching without a capable agent raises ValueError."""
        dispatcher = TaskDispatcher(AgentRegistry())

        with self.assertRaises(ValueError):
            dispatcher.dispatch(create_task())

    def test_dispatch_passes_task_to_agent(self) -> None:
        """Dispatch passes the task object to the selected agent."""
        registry = AgentRegistry()
        agent = RecordingAgent(
            agent_id="agent-1",
            name="Test Agent",
            capabilities={AgentCapability.STRATEGY},
        )
        task = create_task()
        registry.register(agent)
        dispatcher = TaskDispatcher(registry)

        dispatcher.dispatch(task)

        self.assertIs(agent.received_task, task)

    def test_dispatch_returns_agent_result(self) -> None:
        """Dispatch returns the selected agent's result."""
        registry = AgentRegistry()
        agent = RecordingAgent(
            agent_id="agent-1",
            name="Test Agent",
            capabilities={AgentCapability.STRATEGY},
        )
        task = create_task()
        registry.register(agent)
        dispatcher = TaskDispatcher(registry)

        result = dispatcher.dispatch(task)

        self.assertEqual(result, "dispatch-result")


if __name__ == "__main__":
    unittest.main()
