"""Task dispatching for the Helios runtime."""

from dataclasses import dataclass
from typing import Any

from engine.runtime.registry import AgentRegistry
from engine.tasks.task import Task


@dataclass
class TaskDispatcher:
    """Dispatches tasks to registered agents."""

    registry: AgentRegistry

    def dispatch(self, task: Task) -> Any:
        """Dispatch a task to the first agent with the required capability."""
        agents = self.registry.find_by_capability(task.required_capability)
        if not agents:
            msg = "No agent found for required capability."
            raise ValueError(msg)

        agent = agents[0]
        return agent.run(task)
