"""Runtime integration tests for Nova strategy agent."""

import unittest

from agents.strategy.agent import StrategyAgent
from agents.strategy.models import ContentStrategy
from agents.trend_research.models import TrendResult
from agents.trend_research.report import TrendReport
from engine.runtime.capability import AgentCapability
from engine.runtime.runtime import HeliosRuntime
from engine.tasks.priority import TaskPriority
from engine.tasks.status import TaskStatus
from engine.tasks.task import Task


def create_trend_report() -> TrendReport:
    """Create a trend report for runtime integration tests."""
    return TrendReport(
        query="AI Agents",
        summary="Mock trend summary.",
        trends=[
            TrendResult("AI Agents automation", 0.92, "mock:search", "High interest."),
            TrendResult("AI Agents workflow", 0.84, "mock:social", "Workflow demand."),
            TrendResult("AI Agents strategy", 0.78, "mock:content", "Strategy need."),
        ],
        generated_by="mock:mock-trend-model",
    )


def create_strategy_task(payload: dict[str, object] | None = None) -> Task:
    """Create a strategy task for runtime integration tests."""
    task_payload = {"trend_report": create_trend_report()} if payload is None else payload
    return Task(
        task_id="strategy-task-1",
        title="Strategy",
        description="Create content strategy from trend research.",
        priority=TaskPriority.MEDIUM,
        required_capability=AgentCapability.STRATEGY,
        payload=task_payload,
    )


class StrategyRuntimeIntegrationTestCase(unittest.TestCase):
    """Integration tests for Nova through HeliosRuntime."""

    def test_runtime_dispatches_strategy_task_to_nova(self) -> None:
        """Runtime can dispatch STRATEGY tasks to Nova."""
        runtime = HeliosRuntime()
        nova = StrategyAgent()
        task = create_strategy_task()
        runtime.register(nova)

        result = runtime.submit_task(task)

        self.assertIsInstance(result, ContentStrategy)
        self.assertIs(result, task.result)
        self.assertIs(task.status, TaskStatus.COMPLETED)
        self.assertIs(nova.last_strategy, result)
        self.assertEqual(result.query, "AI Agents")
        self.assertEqual(len(result.ideas), 5)

    def test_runtime_returns_content_strategy(self) -> None:
        """Runtime returns the ContentStrategy from Nova."""
        runtime = HeliosRuntime()
        runtime.register(StrategyAgent())
        task = create_strategy_task()

        result = runtime.submit_task(task)

        self.assertIsInstance(result, ContentStrategy)

    def test_runtime_propagates_nova_errors(self) -> None:
        """Runtime propagates Nova validation errors."""
        runtime = HeliosRuntime()
        runtime.register(StrategyAgent())
        task = create_strategy_task({"trend_report": "invalid"})

        with self.assertRaises(ValueError):
            runtime.submit_task(task)

        self.assertIs(task.status, TaskStatus.FAILED)


if __name__ == "__main__":
    unittest.main()
