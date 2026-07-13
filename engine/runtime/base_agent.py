from abc import ABC, abstractmethod


class BaseAgent(ABC):
    """Basisklasse für alle Helios-Agenten."""

    def __init__(self, agent_id: str, name: str):
        self.agent_id = agent_id
        self.name = name

    @abstractmethod
    def run(self) -> None:
        """Startet den Agenten."""
        raise NotImplementedError
        