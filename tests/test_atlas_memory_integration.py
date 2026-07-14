"""Atlas memory integration tests."""

import tempfile
import unittest
from pathlib import Path

from agents.trend_research.agent import TrendResearchAgent
from agents.trend_research.report import TrendReport
from engine.runtime.capability import AgentCapability
from engine.runtime.runtime import HeliosRuntime
from engine.tasks.priority import TaskPriority
from engine.tasks.status import TaskStatus
from engine.tasks.task import Task
from integrations.obsidian.store import ObsidianMemoryStore


def create_trend_task() -> Task:
    """Create a trend research task."""
    return Task(
        task_id="task/001",
        title="Trend Research",
        description="Research trends for a query.",
        priority=TaskPriority.MEDIUM,
        required_capability=AgentCapability.TREND_RESEARCH,
        payload={"query": "AI"},
    )


class AtlasMemoryIntegrationTestCase(unittest.TestCase):
    """End-to-end memory tests for Atlas and Obsidian."""

    def test_runtime_atlas_writes_report_to_obsidian_vault(self) -> None:
        """Atlas stores a completed report in a temporary Obsidian vault."""
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path = Path(temp_dir)
            memory_store = ObsidianMemoryStore(vault_path)
            runtime = HeliosRuntime()
            atlas = TrendResearchAgent(memory_store=memory_store)
            task = create_trend_task()
            runtime.register(atlas)

            result = runtime.submit_task(task)

            self.assertIs(task.status, TaskStatus.COMPLETED)
            self.assertIsInstance(result, TrendReport)
            self.assertIs(task.result, atlas.last_report)
            memory_path = vault_path / "trend-report-task-001.md"
            self.assertTrue(memory_path.exists())
            entry = memory_store.get("trend-report-task-001")
            self.assertEqual(entry.title, "Trend Report: AI")
            self.assertEqual(entry.category, "trend_research")
            self.assertIn("# Trend Report: AI", entry.content)
            self.assertEqual(entry.metadata["task_id"], "task/001")


if __name__ == "__main__":
    unittest.main()
