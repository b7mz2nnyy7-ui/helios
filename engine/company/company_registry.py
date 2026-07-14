"""Registry for Helios company agent definitions."""

from engine.company.agent_definition import AgentDefinition
from engine.company.department import Department


class CompanyRegistry:
    """Registry for storing provider-neutral agent definitions."""

    def __init__(self) -> None:
        """Create an empty company registry."""
        self._definitions: dict[str, AgentDefinition] = {}

    def register(self, definition: AgentDefinition) -> None:
        """Register an agent definition.

        Raises:
            ValueError: If a definition with the same agent ID is already registered.
        """
        if definition.agent_id in self._definitions:
            msg = f"Agent definition with ID '{definition.agent_id}' is already registered."
            raise ValueError(msg)

        self._definitions[definition.agent_id] = definition

    def unregister(self, agent_id: str) -> None:
        """Unregister an agent definition by ID.

        Raises:
            KeyError: If no definition with the given ID is registered.
        """
        del self._definitions[agent_id]

    def get(self, agent_id: str) -> AgentDefinition:
        """Return the registered agent definition for the given ID."""
        return self._definitions[agent_id]

    def exists(self, agent_id: str) -> bool:
        """Return whether an agent definition with the given ID is registered."""
        return agent_id in self._definitions

    def all(self) -> list[AgentDefinition]:
        """Return all registered agent definitions."""
        return list(self._definitions.values())

    def find_by_department(self, department: Department) -> list[AgentDefinition]:
        """Return all definitions for the given department."""
        return [
            definition
            for definition in self._definitions.values()
            if definition.department is department
        ]

    def find_by_capability(self, capability: str) -> list[AgentDefinition]:
        """Return all definitions for the given capability."""
        return [
            definition
            for definition in self._definitions.values()
            if definition.capability == capability
        ]

    def count(self) -> int:
        """Return the number of registered agent definitions."""
        return len(self._definitions)

