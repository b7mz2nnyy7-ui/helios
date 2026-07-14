"""Tests for the tool registry."""

import unittest
from typing import Any

from engine.tools.base_tool import BaseTool
from engine.tools.registry import ToolRegistry


class TestTool(BaseTool):
    """Concrete tool implementation used for registry tests."""

    def execute(self, **kwargs: Any) -> Any:
        """Execute the test tool."""
        return kwargs


class ToolRegistryTestCase(unittest.TestCase):
    """Tests for ToolRegistry behavior."""

    def test_register_adds_tool(self) -> None:
        """Registering a tool stores it by ID."""
        registry = ToolRegistry()
        tool = TestTool(
            tool_id="tool-1",
            name="Test Tool",
            description="A tool used for tests.",
        )

        registry.register(tool)

        self.assertIs(registry.get("tool-1"), tool)

    def test_register_duplicate_tool_id_raises_value_error(self) -> None:
        """Registering the same tool ID twice raises ValueError."""
        registry = ToolRegistry()
        first_tool = TestTool(
            tool_id="tool-1",
            name="First Tool",
            description="The first test tool.",
        )
        second_tool = TestTool(
            tool_id="tool-1",
            name="Second Tool",
            description="The second test tool.",
        )

        registry.register(first_tool)

        with self.assertRaises(ValueError):
            registry.register(second_tool)

    def test_unregister_removes_tool(self) -> None:
        """Unregistering a tool removes it from the registry."""
        registry = ToolRegistry()
        tool = TestTool(
            tool_id="tool-1",
            name="Test Tool",
            description="A tool used for tests.",
        )
        registry.register(tool)

        registry.unregister("tool-1")

        self.assertFalse(registry.exists("tool-1"))

    def test_unregister_unknown_tool_raises_key_error(self) -> None:
        """Unregistering an unknown tool raises KeyError."""
        registry = ToolRegistry()

        with self.assertRaises(KeyError):
            registry.unregister("unknown-tool")

    def test_get_returns_registered_tool(self) -> None:
        """Getting a tool by ID returns the registered instance."""
        registry = ToolRegistry()
        tool = TestTool(
            tool_id="tool-1",
            name="Test Tool",
            description="A tool used for tests.",
        )
        registry.register(tool)

        result = registry.get("tool-1")

        self.assertIs(result, tool)

    def test_get_unknown_tool_raises_key_error(self) -> None:
        """Getting an unknown tool raises KeyError."""
        registry = ToolRegistry()

        with self.assertRaises(KeyError):
            registry.get("unknown-tool")

    def test_exists_returns_true_for_registered_tool(self) -> None:
        """Exists returns True for a registered tool ID."""
        registry = ToolRegistry()
        tool = TestTool(
            tool_id="tool-1",
            name="Test Tool",
            description="A tool used for tests.",
        )
        registry.register(tool)

        self.assertTrue(registry.exists("tool-1"))

    def test_exists_returns_false_for_unknown_tool(self) -> None:
        """Exists returns False for an unknown tool ID."""
        registry = ToolRegistry()

        self.assertFalse(registry.exists("unknown-tool"))

    def test_all_returns_all_registered_tools(self) -> None:
        """All returns a list of all registered tools."""
        registry = ToolRegistry()
        first_tool = TestTool(
            tool_id="tool-1",
            name="First Tool",
            description="The first test tool.",
        )
        second_tool = TestTool(
            tool_id="tool-2",
            name="Second Tool",
            description="The second test tool.",
        )
        registry.register(first_tool)
        registry.register(second_tool)

        result = registry.all()

        self.assertEqual(result, [first_tool, second_tool])

    def test_count_returns_number_of_registered_tools(self) -> None:
        """Count returns the number of registered tools."""
        registry = ToolRegistry()
        registry.register(
            TestTool(
                tool_id="tool-1",
                name="First Tool",
                description="The first test tool.",
            ),
        )
        registry.register(
            TestTool(
                tool_id="tool-2",
                name="Second Tool",
                description="The second test tool.",
            ),
        )

        self.assertEqual(registry.count(), 2)


if __name__ == "__main__":
    unittest.main()
