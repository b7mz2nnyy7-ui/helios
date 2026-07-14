"""Tests for the base agent abstraction."""

import unittest

from engine.runtime.base_agent import BaseAgent
from engine.runtime.status import AgentStatus
from engine.tasks.task import Task


class TestAgent(BaseAgent):
    """Concrete agent implementation used for tests."""

    def run(self, task: Task) -> None:
        """Run the test agent."""


class BaseAgentTestCase(unittest.TestCase):
    """Tests for BaseAgent behavior."""

    def test_base_agent_cannot_be_instantiated_directly(self) -> None:
        """BaseAgent is abstract and cannot be instantiated directly."""
        with self.assertRaises(TypeError):
            BaseAgent(agent_id="agent-1", name="Base")  # type: ignore[abstract]

    def test_status_is_idle_after_creation(self) -> None:
        """A new agent starts in the IDLE status."""
        agent = TestAgent(agent_id="agent-1", name="Test Agent")

        self.assertIs(agent.status, AgentStatus.IDLE)

    def test_stop_sets_status_to_stopped(self) -> None:
        """Stopping an agent sets its status to STOPPED."""
        agent = TestAgent(agent_id="agent-1", name="Test Agent")

        agent.stop()

        self.assertIs(agent.status, AgentStatus.STOPPED)

    def test_health_check_returns_true(self) -> None:
        """The initial health check implementation always returns True."""
        agent = TestAgent(agent_id="agent-1", name="Test Agent")

        self.assertTrue(agent.health_check())


if __name__ == "__main__":
    unittest.main()
