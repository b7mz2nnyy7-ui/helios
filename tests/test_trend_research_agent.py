"""Tests for the Atlas trend research agent."""

import unittest
from typing import Any

from agents.trend_research.agent import TrendResearchAgent
from agents.trend_research.mock_llm_provider import MockLLMProvider
from agents.trend_research.models import TrendResult
from agents.trend_research.mock_tool import MockTrendTool
from agents.trend_research.report import TrendReport
from engine.llm.base_provider import BaseLLMProvider
from engine.llm.models import LLMRequest, LLMResponse
from engine.memory.base_store import BaseMemoryStore
from engine.memory.models import MemoryEntry
from engine.runtime.capability import AgentCapability
from engine.tasks.priority import TaskPriority
from engine.tasks.status import TaskStatus
from engine.tasks.task import Task
from engine.tools.base_tool import BaseTool
from engine.tools.llm_tool import LLMTool


class RecordingTrendTool(BaseTool):
    """Trend tool that records the query it receives."""

    def __init__(self) -> None:
        """Create a recording trend tool."""
        super().__init__(
            tool_id="mock_trend_tool",
            name="Recording Trend Tool",
            description="Records query values for tests.",
        )
        self.received_query: str | None = None
        self.result = [
            TrendResult(
                topic="Recorded Trend",
                score=0.9,
                source="test",
                reason="Used by tests.",
            ),
            TrendResult(
                topic="Second Recorded Trend",
                score=0.7,
                source="test",
                reason="Also used by tests.",
            ),
        ]

    def execute(self, **kwargs: Any) -> list[TrendResult]:
        """Record and return deterministic test results."""
        query = kwargs.get("query")
        if not isinstance(query, str) or not query:
            msg = "query must be a non-empty string."
            raise ValueError(msg)

        self.received_query = query
        return self.result


class FailingTrendTool(BaseTool):
    """Trend tool that always fails."""

    def __init__(self) -> None:
        """Create a failing trend tool."""
        super().__init__(
            tool_id="mock_trend_tool",
            name="Failing Trend Tool",
            description="Fails for tests.",
        )

    def execute(self, **kwargs: Any) -> list[TrendResult]:
        """Raise a runtime error."""
        msg = "tool failed"
        raise RuntimeError(msg)


class UnexpectedTrendTool(BaseTool):
    """Trend tool that fails if it is called."""

    def __init__(self) -> None:
        """Create an unexpected trend tool."""
        super().__init__(
            tool_id="mock_trend_tool",
            name="Unexpected Trend Tool",
            description="Fails when called by tests.",
        )

    def execute(self, **kwargs: Any) -> list[TrendResult]:
        """Raise when the tool is unexpectedly called."""
        msg = "trend tool should not be called"
        raise AssertionError(msg)


class InvalidTrendTool(BaseTool):
    """Trend tool that returns an invalid value."""

    def __init__(self) -> None:
        """Create an invalid trend tool."""
        super().__init__(
            tool_id="mock_trend_tool",
            name="Invalid Trend Tool",
            description="Returns invalid results for tests.",
        )

    def execute(self, **kwargs: Any) -> object:
        """Return an invalid trend result."""
        return ["not a TrendResult"]


class RecordingLLMProvider(BaseLLMProvider):
    """LLM provider that records the request it receives."""

    def __init__(self) -> None:
        """Create a recording LLM provider."""
        super().__init__(provider_id="recording", model="recording-model")
        self.received_request: LLMRequest | None = None
        self.response = LLMResponse(
            content="Recorded LLM summary.",
            model=self.model,
            provider=self.provider_id,
        )

    def generate(self, request: LLMRequest) -> LLMResponse:
        """Record the request and return a fixed response."""
        self.received_request = request
        return self.response


class FailingLLMProvider(BaseLLMProvider):
    """LLM provider that always fails."""

    def __init__(self) -> None:
        """Create a failing LLM provider."""
        super().__init__(provider_id="failing", model="failing-model")

    def generate(self, request: LLMRequest) -> LLMResponse:
        """Raise a runtime error."""
        msg = "llm failed"
        raise RuntimeError(msg)


class InvalidLLMTool(BaseTool):
    """LLM tool that returns an invalid response."""

    def __init__(self) -> None:
        """Create an invalid LLM tool."""
        super().__init__(
            tool_id="llm",
            name="Invalid LLM Tool",
            description="Returns invalid responses for tests.",
        )

    def execute(self, **kwargs: Any) -> object:
        """Return an invalid LLM response."""
        return "not an LLMResponse"


class RecordingMemoryStore(BaseMemoryStore):
    """Memory store that records saved entries."""

    def __init__(self) -> None:
        """Create a recording memory store."""
        self.entries: list[MemoryEntry] = []

    def save(self, entry: MemoryEntry) -> None:
        """Record a saved memory entry."""
        self.entries.append(entry)

    def get(self, memory_id: str) -> MemoryEntry:
        """Return a recorded memory entry."""
        for entry in self.entries:
            if entry.memory_id == memory_id:
                return entry

        raise KeyError(memory_id)

    def exists(self, memory_id: str) -> bool:
        """Return whether an entry was recorded."""
        return any(entry.memory_id == memory_id for entry in self.entries)

    def delete(self, memory_id: str) -> None:
        """Delete a recorded memory entry."""
        entry = self.get(memory_id)
        self.entries.remove(entry)

    def list_all(self) -> list[MemoryEntry]:
        """Return all recorded entries."""
        return list(self.entries)


class FailingMemoryStore(RecordingMemoryStore):
    """Memory store that fails when saving."""

    def save(self, entry: MemoryEntry) -> None:
        """Raise a runtime error."""
        msg = "memory failed"
        raise RuntimeError(msg)


def create_trend_task(payload: dict[str, Any] | None = None) -> Task:
    """Create a trend research task."""
    task_payload = {"query": "AI"} if payload is None else payload
    return Task(
        task_id="task-1",
        title="Trend Research",
        description="Research trends for a query.",
        priority=TaskPriority.MEDIUM,
        required_capability=AgentCapability.TREND_RESEARCH,
        payload=task_payload,
    )


class TrendResearchAgentTestCase(unittest.TestCase):
    """Tests for TrendResearchAgent behavior."""

    def test_agent_has_trend_research_capability(self) -> None:
        """Atlas declares the TREND_RESEARCH capability."""
        agent = TrendResearchAgent()

        self.assertTrue(agent.can_handle(AgentCapability.TREND_RESEARCH))

    def test_agent_name_defaults_to_atlas(self) -> None:
        """Atlas has the default name Atlas."""
        agent = TrendResearchAgent()

        self.assertEqual(agent.name, "Atlas")

    def test_agent_has_default_trend_and_llm_tools(self) -> None:
        """Atlas has the default trend and LLM tools."""
        agent = TrendResearchAgent()

        self.assertIsInstance(agent.get_tool("mock_trend_tool"), MockTrendTool)
        self.assertIsInstance(agent.get_tool("llm"), LLMTool)

    def test_valid_task_is_started_and_completed(self) -> None:
        """A valid task is moved from pending to completed."""
        agent = TrendResearchAgent()
        task = create_trend_task()

        agent.run(task)

        self.assertIs(task.status, TaskStatus.COMPLETED)

    def test_tool_receives_query_from_payload(self) -> None:
        """Atlas passes the task query to the trend tool."""
        tool = RecordingTrendTool()
        agent = TrendResearchAgent(tools=[tool])
        task = create_trend_task({"query": "robotics"})

        agent.run(task)

        self.assertEqual(tool.received_query, "robotics")

    def test_last_result_contains_tool_results(self) -> None:
        """Atlas stores the tool results after successful processing."""
        tool = RecordingTrendTool()
        agent = TrendResearchAgent(tools=[tool])
        task = create_trend_task()

        agent.run(task)

        self.assertEqual(agent.last_result, tool.result)

    def test_llm_receives_llm_request(self) -> None:
        """Atlas sends an LLMRequest to the LLM tool."""
        provider = RecordingLLMProvider()
        agent = TrendResearchAgent(tools=[LLMTool(provider=provider)])
        task = create_trend_task()

        agent.run(task)

        self.assertIsInstance(provider.received_request, LLMRequest)

    def test_llm_prompt_contains_query_and_trend_topics(self) -> None:
        """Atlas includes the query and trend topics in the LLM prompt."""
        trend_tool = RecordingTrendTool()
        provider = RecordingLLMProvider()
        agent = TrendResearchAgent(
            tools=[trend_tool, LLMTool(provider=provider)],
        )
        task = create_trend_task({"query": "robotics"})

        agent.run(task)

        request = provider.received_request
        assert request is not None
        self.assertIn("robotics", request.user_prompt)
        self.assertIn("Recorded Trend", request.user_prompt)
        self.assertIn("Second Recorded Trend", request.user_prompt)

    def test_last_report_is_stored(self) -> None:
        """Atlas stores a TrendReport after successful processing."""
        provider = RecordingLLMProvider()
        agent = TrendResearchAgent(tools=[LLMTool(provider=provider)])
        task = create_trend_task()

        agent.run(task)

        self.assertIsNotNone(agent.last_report)

    def test_run_returns_trend_report(self) -> None:
        """Atlas returns the generated TrendReport."""
        agent = TrendResearchAgent()
        task = create_trend_task()

        result = agent.run(task)

        self.assertIsInstance(result, TrendReport)

    def test_run_return_value_is_task_result(self) -> None:
        """Atlas returns the same report stored on the task."""
        agent = TrendResearchAgent()
        task = create_trend_task()

        result = agent.run(task)

        self.assertIs(result, task.result)

    def test_last_report_is_task_result(self) -> None:
        """Atlas last_report is the same object stored on the task."""
        agent = TrendResearchAgent()
        task = create_trend_task()

        agent.run(task)

        self.assertIs(agent.last_report, task.result)

    def test_report_contains_query_trends_llm_text_and_model_identifier(self) -> None:
        """Atlas report contains query, trends, summary, and model identifier."""
        trend_tool = RecordingTrendTool()
        provider = RecordingLLMProvider()
        agent = TrendResearchAgent(
            tools=[trend_tool, LLMTool(provider=provider)],
        )
        task = create_trend_task({"query": "robotics"})

        agent.run(task)

        report = agent.last_report
        assert report is not None
        self.assertEqual(report.query, "robotics")
        self.assertEqual(report.trends, trend_tool.result)
        self.assertEqual(report.summary, "Recorded LLM summary.")
        self.assertEqual(report.generated_by, "recording:recording-model")

    def test_wrong_capability_raises_value_error(self) -> None:
        """Atlas rejects tasks with the wrong capability."""
        agent = TrendResearchAgent()
        task = Task(
            task_id="task-1",
            title="Strategy",
            description="A non-trend task.",
            priority=TaskPriority.MEDIUM,
            required_capability=AgentCapability.STRATEGY,
            payload={"query": "AI"},
        )

        with self.assertRaises(ValueError):
            agent.run(task)

    def test_missing_query_raises_value_error(self) -> None:
        """A missing query raises ValueError."""
        agent = TrendResearchAgent()
        task = create_trend_task({})

        with self.assertRaises(ValueError):
            agent.run(task)

    def test_missing_query_is_rejected_before_trend_tool_runs(self) -> None:
        """Atlas validates the query before calling the trend tool."""
        agent = TrendResearchAgent(tools=[UnexpectedTrendTool()])
        task = create_trend_task({})

        with self.assertRaisesRegex(ValueError, "query must be a non-empty string."):
            agent.run(task)

    def test_tool_error_sets_task_to_failed(self) -> None:
        """A tool error moves a running task to FAILED."""
        agent = TrendResearchAgent(tools=[FailingTrendTool()])
        task = create_trend_task()

        with self.assertRaises(RuntimeError):
            agent.run(task)

        self.assertIs(task.status, TaskStatus.FAILED)
        self.assertEqual(task.error_message, "tool failed")

    def test_tool_error_is_reraised(self) -> None:
        """A tool error is propagated to the caller."""
        agent = TrendResearchAgent(tools=[FailingTrendTool()])
        task = create_trend_task()

        with self.assertRaisesRegex(RuntimeError, "tool failed"):
            agent.run(task)

    def test_invalid_trend_tool_result_sets_task_to_failed(self) -> None:
        """An invalid trend tool result moves the task to FAILED."""
        agent = TrendResearchAgent(tools=[InvalidTrendTool()])
        task = create_trend_task()

        with self.assertRaises(ValueError):
            agent.run(task)

        self.assertIs(task.status, TaskStatus.FAILED)
        self.assertEqual(
            task.error_message,
            "trend tool must return a list of TrendResult.",
        )

    def test_llm_error_sets_task_to_failed(self) -> None:
        """An LLM error moves the task to FAILED."""
        agent = TrendResearchAgent(
            tools=[LLMTool(provider=FailingLLMProvider())],
        )
        task = create_trend_task()

        with self.assertRaises(RuntimeError):
            agent.run(task)

        self.assertIs(task.status, TaskStatus.FAILED)
        self.assertEqual(task.error_message, "llm failed")

    def test_llm_error_is_reraised(self) -> None:
        """An LLM error is propagated to the caller."""
        agent = TrendResearchAgent(
            tools=[LLMTool(provider=FailingLLMProvider())],
        )
        task = create_trend_task()

        with self.assertRaisesRegex(RuntimeError, "llm failed"):
            agent.run(task)

    def test_invalid_llm_tool_response_sets_task_to_failed(self) -> None:
        """An invalid LLM tool response moves the task to FAILED."""
        agent = TrendResearchAgent(tools=[InvalidLLMTool()])
        task = create_trend_task()

        with self.assertRaises(ValueError):
            agent.run(task)

        self.assertIs(task.status, TaskStatus.FAILED)
        self.assertEqual(task.error_message, "llm tool must return an LLMResponse.")

    def test_mock_llm_provider_returns_deterministic_response(self) -> None:
        """The mock LLM provider returns deterministic text."""
        provider = MockLLMProvider()
        request = LLMRequest(
            system_prompt="Atlas",
            user_prompt="Query: AI",
        )

        response = provider.generate(request)

        self.assertEqual(response.provider, "mock")
        self.assertEqual(response.model, "mock-trend-model")
        self.assertIn("Query: AI", response.content)

    def test_mock_trend_tool_returns_deterministic_trend_results(self) -> None:
        """The mock trend tool returns deterministic TrendResult objects."""
        tool = MockTrendTool()

        first_result = tool.execute(query="AI")
        second_result = tool.execute(query="AI")

        self.assertEqual(first_result, second_result)
        self.assertEqual(len(first_result), 3)
        self.assertTrue(all(isinstance(result, TrendResult) for result in first_result))

    def test_mock_trend_tool_empty_query_raises_value_error(self) -> None:
        """The mock trend tool rejects an empty query."""
        tool = MockTrendTool()

        with self.assertRaises(ValueError):
            tool.execute(query="")

    def test_agent_still_works_without_memory_store(self) -> None:
        """Atlas still completes tasks without a memory store."""
        agent = TrendResearchAgent()
        task = create_trend_task()

        agent.run(task)

        self.assertIs(task.status, TaskStatus.COMPLETED)

    def test_successful_report_is_saved_once(self) -> None:
        """Atlas saves a successful report once when memory is configured."""
        memory_store = RecordingMemoryStore()
        agent = TrendResearchAgent(memory_store=memory_store)
        task = create_trend_task()

        agent.run(task)

        self.assertEqual(len(memory_store.entries), 1)

    def test_saved_entry_contains_title_category_and_content(self) -> None:
        """Saved memory entry contains the report title, category, and content."""
        memory_store = RecordingMemoryStore()
        agent = TrendResearchAgent(memory_store=memory_store)
        task = create_trend_task()

        agent.run(task)

        entry = memory_store.entries[0]
        self.assertEqual(entry.title, "Trend Report: AI")
        self.assertEqual(entry.category, "trend_research")
        self.assertIn("# Trend Report: AI", entry.content)

    def test_saved_entry_metadata_contains_required_values(self) -> None:
        """Saved memory metadata contains task and report details."""
        memory_store = RecordingMemoryStore()
        agent = TrendResearchAgent(memory_store=memory_store)
        task = create_trend_task()

        agent.run(task)

        metadata = memory_store.entries[0].metadata
        self.assertEqual(metadata["task_id"], "task-1")
        self.assertEqual(metadata["query"], "AI")
        self.assertEqual(metadata["generated_by"], "mock:mock-trend-model")
        self.assertEqual(metadata["trend_count"], 3)
        self.assertEqual(metadata["agent_id"], "trend_research")

    def test_report_to_markdown_contains_query_summary_and_trends(self) -> None:
        """TrendReport Markdown contains the query, summary, and trend sections."""
        trends = [
            TrendResult("Trend One", 0.9, "source-a", "reason-a"),
            TrendResult("Trend Two", 0.8, "source-b", "reason-b"),
        ]
        report = TrendReport(
            query="AI",
            summary="Summary text.",
            trends=trends,
            generated_by="mock:model",
        )

        markdown = report.to_markdown()

        self.assertIn("# Trend Report: AI", markdown)
        self.assertIn("Generated by: mock:model", markdown)
        self.assertIn("Summary text.", markdown)
        self.assertIn("### Trend One", markdown)
        self.assertIn("### Trend Two", markdown)

    def test_safe_memory_id_is_generated(self) -> None:
        """Atlas generates the expected safe memory ID."""
        memory_store = RecordingMemoryStore()
        agent = TrendResearchAgent(memory_store=memory_store)
        task = create_trend_task()

        agent.run(task)

        self.assertEqual(memory_store.entries[0].memory_id, "trend-report-task-1")

    def test_invalid_task_id_characters_are_replaced(self) -> None:
        """Atlas replaces unsafe task ID characters with hyphens."""
        memory_store = RecordingMemoryStore()
        agent = TrendResearchAgent(memory_store=memory_store)
        task = Task(
            task_id="task/001",
            title="Trend Research",
            description="Research trends for a query.",
            priority=TaskPriority.MEDIUM,
            required_capability=AgentCapability.TREND_RESEARCH,
            payload={"query": "AI"},
        )

        agent.run(task)

        self.assertEqual(memory_store.entries[0].memory_id, "trend-report-task-001")

    def test_empty_safe_task_id_raises_value_error(self) -> None:
        """Atlas rejects task IDs that contain no safe characters."""
        agent = TrendResearchAgent(memory_store=RecordingMemoryStore())
        task = Task(
            task_id="///",
            title="Trend Research",
            description="Research trends for a query.",
            priority=TaskPriority.MEDIUM,
            required_capability=AgentCapability.TREND_RESEARCH,
            payload={"query": "AI"},
        )

        with self.assertRaises(ValueError):
            agent.run(task)

    def test_memory_error_sets_task_to_failed(self) -> None:
        """A memory save error moves the task to FAILED."""
        agent = TrendResearchAgent(memory_store=FailingMemoryStore())
        task = create_trend_task()

        with self.assertRaises(RuntimeError):
            agent.run(task)

        self.assertIs(task.status, TaskStatus.FAILED)
        self.assertEqual(task.error_message, "memory failed")

    def test_memory_error_is_reraised(self) -> None:
        """A memory save error is propagated to the caller."""
        agent = TrendResearchAgent(memory_store=FailingMemoryStore())
        task = create_trend_task()

        with self.assertRaisesRegex(RuntimeError, "memory failed"):
            agent.run(task)

    def test_memory_error_leaves_task_result_none(self) -> None:
        """A memory save error leaves task.result unset."""
        agent = TrendResearchAgent(memory_store=FailingMemoryStore())
        task = create_trend_task()

        with self.assertRaises(RuntimeError):
            agent.run(task)

        self.assertIsNone(task.result)
        self.assertIsNotNone(agent.last_report)


if __name__ == "__main__":
    unittest.main()
