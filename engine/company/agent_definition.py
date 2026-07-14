"""Agent definition model for the Helios company architecture."""

from dataclasses import dataclass

from engine.company.department import Department


@dataclass(frozen=True)
class AgentDefinition:
    """Provider-neutral metadata for a future Helios company agent."""

    agent_id: str
    display_name: str
    department: Department
    capability: str
    description: str
    responsibilities: tuple[str, ...]
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    required_tools: tuple[str, ...]
    memory_access: tuple[str, ...]
    event_subscriptions: tuple[str, ...]

