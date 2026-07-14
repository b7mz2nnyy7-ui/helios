"""Tests for the agent registry."""

import unittest

from engine.runtime.base_agent import BaseAgent
from engine.runtime.capability import AgentCapability
from engine.runtime.registry import AgentRegistry
from engine.tasks.task import Task


class TestAgent(BaseAgent):
    """Concrete agent implementation used for registry tests."""

    def run(self, task: Task) -> None:
        """Run the test agent."""


class AgentRegistryTestCase(unittest.TestCase):
    """Tests for AgentRegistry behavior."""

    def test_register_adds_agent(self) -> None:
        """Registering an agent stores it by ID."""
        registry = AgentRegistry()
        agent = TestAgent(agent_id="agent-1", name="Test Agent")

        registry.register(agent)

        self.assertIs(registry.get("agent-1"), agent)

    def test_register_duplicate_agent_id_raises_value_error(self) -> None:
        """Registering the same agent ID twice raises ValueError."""
        registry = AgentRegistry()
        first_agent = TestAgent(agent_id="agent-1", name="First Agent")
        second_agent = TestAgent(agent_id="agent-1", name="Second Agent")

        registry.register(first_agent)

        with self.assertRaises(ValueError):
            registry.register(second_agent)

    def test_unregister_removes_agent(self) -> None:
        """Unregistering an agent removes it from the registry."""
        registry = AgentRegistry()
        agent = TestAgent(agent_id="agent-1", name="Test Agent")
        registry.register(agent)

        registry.unregister("agent-1")

        self.assertFalse(registry.exists("agent-1"))

    def test_unregister_unknown_agent_raises_key_error(self) -> None:
        """Unregistering an unknown agent raises KeyError."""
        registry = AgentRegistry()

        with self.assertRaises(KeyError):
            registry.unregister("unknown-agent")

    def test_get_returns_registered_agent(self) -> None:
        """Getting an agent by ID returns the registered instance."""
        registry = AgentRegistry()
        agent = TestAgent(agent_id="agent-1", name="Test Agent")
        registry.register(agent)

        result = registry.get("agent-1")

        self.assertIs(result, agent)

    def test_exists_returns_true_for_registered_agent(self) -> None:
        """Exists returns True for a registered agent ID."""
        registry = AgentRegistry()
        agent = TestAgent(agent_id="agent-1", name="Test Agent")
        registry.register(agent)

        self.assertTrue(registry.exists("agent-1"))

    def test_exists_returns_false_for_unknown_agent(self) -> None:
        """Exists returns False for an unknown agent ID."""
        registry = AgentRegistry()

        self.assertFalse(registry.exists("unknown-agent"))

    def test_all_returns_all_registered_agents(self) -> None:
        """All returns a list of all registered agents."""
        registry = AgentRegistry()
        first_agent = TestAgent(agent_id="agent-1", name="First Agent")
        second_agent = TestAgent(agent_id="agent-2", name="Second Agent")
        registry.register(first_agent)
        registry.register(second_agent)

        result = registry.all()

        self.assertEqual(result, [first_agent, second_agent])

    def test_count_returns_number_of_registered_agents(self) -> None:
        """Count returns the number of registered agents."""
        registry = AgentRegistry()
        registry.register(TestAgent(agent_id="agent-1", name="First Agent"))
        registry.register(TestAgent(agent_id="agent-2", name="Second Agent"))

        self.assertEqual(registry.count(), 2)

    def test_find_by_capability_returns_matching_agent(self) -> None:
        """Finding by capability returns agents that support it."""
        registry = AgentRegistry()
        matching_agent = TestAgent(
            agent_id="agent-1",
            name="Matching Agent",
            capabilities={AgentCapability.STRATEGY},
        )
        other_agent = TestAgent(
            agent_id="agent-2",
            name="Other Agent",
            capabilities={AgentCapability.ANALYTICS},
        )
        registry.register(matching_agent)
        registry.register(other_agent)

        result = registry.find_by_capability(AgentCapability.STRATEGY)

        self.assertEqual(result, [matching_agent])

    def test_find_by_capability_returns_multiple_matching_agents(self) -> None:
        """Finding by capability can return multiple matching agents."""
        registry = AgentRegistry()
        first_agent = TestAgent(
            agent_id="agent-1",
            name="First Agent",
            capabilities={AgentCapability.STRATEGY},
        )
        second_agent = TestAgent(
            agent_id="agent-2",
            name="Second Agent",
            capabilities={AgentCapability.STRATEGY},
        )
        registry.register(first_agent)
        registry.register(second_agent)

        result = registry.find_by_capability(AgentCapability.STRATEGY)

        self.assertEqual(result, [first_agent, second_agent])


if __name__ == "__main__":
    unittest.main()
