"""Agent registry for tracking runtime agent instances."""

from engine.runtime.base_agent import BaseAgent
from engine.runtime.capability import AgentCapability


class AgentRegistry:
    """Registry for storing agents by their unique agent ID."""

    def __init__(self) -> None:
        """Create an empty agent registry."""
        self._agents: dict[str, BaseAgent] = {}

    def register(self, agent: BaseAgent) -> None:
        """Register an agent.

        Raises:
            ValueError: If an agent with the same ID is already registered.
        """
        if agent.agent_id in self._agents:
            msg = f"Agent with ID '{agent.agent_id}' is already registered."
            raise ValueError(msg)

        self._agents[agent.agent_id] = agent

    def unregister(self, agent_id: str) -> None:
        """Unregister an agent by ID.

        Raises:
            KeyError: If no agent with the given ID is registered.
        """
        del self._agents[agent_id]

    def get(self, agent_id: str) -> BaseAgent:
        """Return the registered agent for the given ID."""
        return self._agents[agent_id]

    def exists(self, agent_id: str) -> bool:
        """Return whether an agent with the given ID is registered."""
        return agent_id in self._agents

    def all(self) -> list[BaseAgent]:
        """Return all registered agents."""
        return list(self._agents.values())

    def find_by_capability(self, capability: AgentCapability) -> list[BaseAgent]:
        """Return all agents that support the given capability."""
        return [agent for agent in self._agents.values() if agent.can_handle(capability)]

    def count(self) -> int:
        """Return the number of registered agents."""
        return len(self._agents)
