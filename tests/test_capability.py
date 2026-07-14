"""Tests for agent capabilities."""

import unittest

from engine.runtime.base_agent import BaseAgent
from engine.runtime.capability import AgentCapability
from engine.tasks.task import Task


class TestAgent(BaseAgent):
    """Concrete agent implementation used for capability tests."""

    def run(self, task: Task) -> None:
        """Run the test agent."""


class AgentCapabilityTestCase(unittest.TestCase):
    """Tests for agent capability behavior."""

    def test_agent_has_empty_capability_set_by_default(self) -> None:
        """A new agent has no capabilities by default."""
        agent = TestAgent(agent_id="agent-1", name="Test Agent")

        self.assertEqual(agent.capabilities, set())

    def test_agent_can_have_one_capability(self) -> None:
        """An agent can declare one capability."""
        agent = TestAgent(
            agent_id="agent-1",
            name="Test Agent",
            capabilities={AgentCapability.TREND_RESEARCH},
        )

        self.assertEqual(agent.capabilities, {AgentCapability.TREND_RESEARCH})

    def test_agent_can_have_multiple_capabilities(self) -> None:
        """An agent can declare multiple capabilities."""
        capabilities = {
            AgentCapability.STRATEGY,
            AgentCapability.SCRIPT_WRITING,
            AgentCapability.QUALITY_CONTROL,
        }
        agent = TestAgent(
            agent_id="agent-1",
            name="Test Agent",
            capabilities=capabilities,
        )

        self.assertEqual(agent.capabilities, capabilities)

    def test_can_handle_returns_true_for_supported_capability(self) -> None:
        """can_handle returns True for a declared capability."""
        agent = TestAgent(
            agent_id="agent-1",
            name="Test Agent",
            capabilities={AgentCapability.ANALYTICS},
        )

        self.assertTrue(agent.can_handle(AgentCapability.ANALYTICS))

    def test_can_handle_returns_false_for_unsupported_capability(self) -> None:
        """can_handle returns False for a capability the agent does not have."""
        agent = TestAgent(
            agent_id="agent-1",
            name="Test Agent",
            capabilities={AgentCapability.PUBLISHING},
        )

        self.assertFalse(agent.can_handle(AgentCapability.MEMORY))


if __name__ == "__main__":
    unittest.main()
