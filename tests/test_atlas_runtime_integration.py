"""Runtime integration tests for Atlas."""

import unittest

from agents.trend_research.agent import TrendResearchAgent
from agents.trend_research.models import TrendResult
from agents.trend_research.report import TrendReport
from engine.events.event import Event
from engine.runtime.capability import AgentCapability
from engine.runtime.runtime import HeliosRuntime
from engine.tasks.priority import TaskPriority
from engine.tasks.status import TaskStatus
from engine.tasks.task import Task


def create_trend_task(payload: dict[str, str]) -> Task:
    """Create a trend research task for integration tests."""
    return Task(
        task_id="task-1",
        title="Trend Research",
        description="Research trends for a query.",
        priority=TaskPriority.MEDIUM,
        required_capability=AgentCapability.TREND_RESEARCH,
        payload=payload,
    )


class AtlasRuntimeIntegrationTestCase(unittest.TestCase):
    """Integration tests for Atlas through HeliosRuntime."""

    def test_runtime_dispatches_trend_task_to_atlas(self) -> None:
        """Runtime routes a trend task to Atlas and publishes a dispatch event."""
        runtime = HeliosRuntime()
        atlas = TrendResearchAgent()
        task = create_trend_task({"query": "AI"})
        dispatched_events: list[Event] = []
        runtime.event_bus.subscribe("task.dispatched", dispatched_events.append)
        runtime.register(atlas)

        runtime.start()
        result = runtime.submit_task(task)

        self.assertIs(task.status, TaskStatus.COMPLETED)
        self.assertIsInstance(result, TrendReport)
        self.assertIs(result, task.result)
        self.assertIsNotNone(atlas.last_result)
        last_result = atlas.last_result
        assert last_result is not None
        self.assertEqual(len(last_result), 3)
        self.assertTrue(
            all(isinstance(result, TrendResult) for result in last_result),
        )
        self.assertIsNotNone(atlas.last_report)
        report = atlas.last_report
        assert report is not None
        self.assertIs(report, task.result)
        self.assertEqual(report.query, "AI")
        self.assertEqual(report.trends, last_result)
        self.assertIn("Mock trend summary", report.summary)
        self.assertEqual(report.generated_by, "mock:mock-trend-model")
        self.assertEqual(len(dispatched_events), 1)
        self.assertEqual(
            dispatched_events[0].payload,
            {
                "task_id": "task-1",
                "required_capability": "TREND_RESEARCH",
                "priority": "MEDIUM",
            },
        )

    def test_runtime_does_not_publish_dispatch_event_when_atlas_fails(self) -> None:
        """Runtime propagates Atlas errors without publishing task.dispatched."""
        runtime = HeliosRuntime()
        atlas = TrendResearchAgent()
        task = create_trend_task({})
        dispatched_events: list[Event] = []
        failed_events: list[Event] = []
        runtime.event_bus.subscribe("task.dispatched", dispatched_events.append)
        runtime.event_bus.subscribe("task.failed", failed_events.append)
        runtime.register(atlas)

        with self.assertRaises(ValueError):
            runtime.submit_task(task)

        self.assertIs(task.status, TaskStatus.FAILED)
        self.assertEqual(task.error_message, "query must be a non-empty string.")
        self.assertEqual(dispatched_events, [])
        self.assertEqual(len(failed_events), 1)
        self.assertEqual(
            failed_events[0].payload,
            {
                "task_id": "task-1",
                "required_capability": "TREND_RESEARCH",
                "priority": "MEDIUM",
                "error_message": "query must be a non-empty string.",
            },
        )


if __name__ == "__main__":
    unittest.main()
