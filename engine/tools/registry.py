"""Registry for Helios tools."""

from engine.tools.base_tool import BaseTool


class ToolRegistry:
    """Registry for storing tools by their unique tool ID."""

    def __init__(self) -> None:
        """Create an empty tool registry."""
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """Register a tool.

        Raises:
            ValueError: If a tool with the same ID is already registered.
        """
        if tool.tool_id in self._tools:
            msg = f"Tool with ID '{tool.tool_id}' is already registered."
            raise ValueError(msg)

        self._tools[tool.tool_id] = tool

    def unregister(self, tool_id: str) -> None:
        """Unregister a tool by ID.

        Raises:
            KeyError: If no tool with the given ID is registered.
        """
        del self._tools[tool_id]

    def get(self, tool_id: str) -> BaseTool:
        """Return the registered tool for the given ID."""
        return self._tools[tool_id]

    def exists(self, tool_id: str) -> bool:
        """Return whether a tool with the given ID is registered."""
        return tool_id in self._tools

    def all(self) -> list[BaseTool]:
        """Return all registered tools."""
        return list(self._tools.values())

    def count(self) -> int:
        """Return the number of registered tools."""
        return len(self._tools)
