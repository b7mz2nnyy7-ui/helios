"""Tests for the base tool abstraction and agent tool usage."""

import unittest
from typing import Any

from engine.runtime.base_agent import BaseAgent
from engine.tasks.task import Task
from engine.tools.base_tool import BaseTool


class TestAgent(BaseAgent):
    """Concrete agent implementation used for tool tests."""

    def run(self, task: Task) -> None:
        """Run the test agent."""


class TestTool(BaseTool):
    """Concrete tool implementation used for tests."""

    def execute(self, **kwargs: Any) -> Any:
        """Execute the test tool."""
        return kwargs


class BaseToolTestCase(unittest.TestCase):
    """Tests for BaseTool and agent tool behavior."""

    def test_execute_is_abstract(self) -> None:
        """BaseTool cannot be instantiated directly."""
        with self.assertRaises(TypeError):
            BaseTool(
                tool_id="tool-1",
                name="Base Tool",
                description="Abstract base tool.",
            )  # type: ignore[abstract]

    def test_tool_can_be_added_to_agent(self) -> None:
        """A tool can be added to an agent."""
        agent = TestAgent(agent_id="agent-1", name="Test Agent")
        tool = TestTool(
            tool_id="tool-1",
            name="Test Tool",
            description="A tool used for tests.",
        )

        agent.add_tool(tool)

        self.assertEqual(agent.tools, [tool])

    def test_same_tool_cannot_be_added_twice_to_agent(self) -> None:
        """The same tool cannot be added to an agent twice."""
        agent = TestAgent(agent_id="agent-1", name="Test Agent")
        tool = TestTool(
            tool_id="tool-1",
            name="Test Tool",
            description="A tool used for tests.",
        )
        agent.add_tool(tool)

        with self.assertRaisesRegex(ValueError, "tool-1"):
            agent.add_tool(tool)

    def test_different_tools_with_same_id_cannot_be_added_to_agent(self) -> None:
        """Different tool objects with the same ID cannot both be added."""
        agent = TestAgent(agent_id="agent-1", name="Test Agent")
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
        agent.add_tool(first_tool)

        with self.assertRaisesRegex(ValueError, "tool-1"):
            agent.add_tool(second_tool)

    def test_tools_with_different_ids_can_be_added_to_agent(self) -> None:
        """Tools with different IDs can be added to the same agent."""
        agent = TestAgent(agent_id="agent-1", name="Test Agent")
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

        agent.add_tool(first_tool)
        agent.add_tool(second_tool)

        self.assertEqual(agent.tools, [first_tool, second_tool])

    def test_tool_can_be_removed_from_agent(self) -> None:
        """A tool can be removed from an agent."""
        agent = TestAgent(agent_id="agent-1", name="Test Agent")
        tool = TestTool(
            tool_id="tool-1",
            name="Test Tool",
            description="A tool used for tests.",
        )
        agent.add_tool(tool)

        agent.remove_tool("tool-1")

        self.assertEqual(agent.tools, [])

    def test_remove_unknown_tool_from_agent_raises_key_error(self) -> None:
        """Removing an unknown tool from an agent raises KeyError."""
        agent = TestAgent(agent_id="agent-1", name="Test Agent")

        with self.assertRaises(KeyError):
            agent.remove_tool("unknown-tool")

    def test_tool_can_be_found_on_agent(self) -> None:
        """An attached tool can be found by ID."""
        agent = TestAgent(agent_id="agent-1", name="Test Agent")
        tool = TestTool(
            tool_id="tool-1",
            name="Test Tool",
            description="A tool used for tests.",
        )
        agent.add_tool(tool)

        result = agent.get_tool("tool-1")

        self.assertIs(result, tool)

    def test_get_unknown_tool_from_agent_raises_key_error(self) -> None:
        """Getting an unknown tool from an agent raises KeyError."""
        agent = TestAgent(agent_id="agent-1", name="Test Agent")

        with self.assertRaises(KeyError):
            agent.get_tool("unknown-tool")


if __name__ == "__main__":
    unittest.main()
