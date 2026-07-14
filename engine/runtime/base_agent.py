"""Base abstraction for Helios agents."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from engine.runtime.capability import AgentCapability
from engine.runtime.status import AgentStatus
from engine.tasks.task import Task
from engine.tools.base_tool import BaseTool


@dataclass
class BaseAgent(ABC):
    """Abstract base class for all Helios agents."""

    agent_id: str
    name: str
    capabilities: set[AgentCapability] = field(default_factory=set)
    tools: list[BaseTool] = field(default_factory=list)
    status: AgentStatus = field(default=AgentStatus.IDLE, init=False)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC), init=False)

    @abstractmethod
    def run(self, task: Task) -> Any:
        """Run the agent for the given task."""

    def stop(self) -> None:
        """Stop the agent."""
        self.status = AgentStatus.STOPPED

    def health_check(self) -> bool:
        """Return whether the agent is healthy."""
        return True

    def can_handle(self, capability: AgentCapability) -> bool:
        """Return whether the agent supports the given capability."""
        return capability in self.capabilities

    def add_tool(self, tool: BaseTool) -> None:
        """Add a tool to the agent."""
        if any(existing_tool.tool_id == tool.tool_id for existing_tool in self.tools):
            msg = f"Tool with ID '{tool.tool_id}' is already attached to the agent."
            raise ValueError(msg)

        self.tools.append(tool)

    def remove_tool(self, tool_id: str) -> None:
        """Remove a tool from the agent by ID.

        Raises:
            KeyError: If no tool with the given ID is attached to the agent.
        """
        tool = self.get_tool(tool_id)
        self.tools.remove(tool)

    def get_tool(self, tool_id: str) -> BaseTool:
        """Return an attached tool by ID.

        Raises:
            KeyError: If no tool with the given ID is attached to the agent.
        """
        for tool in self.tools:
            if tool.tool_id == tool_id:
                return tool

        raise KeyError(tool_id)
