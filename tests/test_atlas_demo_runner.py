"""Tests for the local Atlas demo runner."""

import tempfile
import unittest
from pathlib import Path

from engine.tasks.status import TaskStatus
from scripts.run_atlas_demo import (
    VAULT_ENV_VAR,
    get_vault_path,
    parse_query,
    run_demo,
)


class AtlasDemoRunnerTestCase(unittest.TestCase):
    """Tests for the Atlas demo script helpers."""

    def test_missing_query_raises_value_error(self) -> None:
        """A missing command-line query is rejected."""
        with self.assertRaises(ValueError):
            parse_query([])

    def test_missing_vault_configuration_raises_runtime_error(self) -> None:
        """A missing vault environment variable is rejected."""
        with self.assertRaises(RuntimeError):
            get_vault_path({})

    def test_vault_configuration_returns_path(self) -> None:
        """The vault path is read from the configured environment variable."""
        vault_path = get_vault_path({VAULT_ENV_VAR: "/tmp/helios-vault"})

        self.assertEqual(vault_path, Path("/tmp/helios-vault"))

    def test_successful_demo_run_writes_report_to_temp_vault(self) -> None:
        """A successful demo run completes the task and writes Markdown."""
        with tempfile.TemporaryDirectory() as temp_dir:
            result = run_demo("AI Agents", Path(temp_dir))

            self.assertIs(result.status, TaskStatus.COMPLETED)
            self.assertEqual(result.query, "AI Agents")
            self.assertEqual(result.trend_count, 3)
            self.assertEqual(result.generated_by, "mock:mock-trend-model")
            self.assertTrue(result.markdown_path.exists())
            self.assertIn(
                "# Trend Report: AI Agents",
                result.markdown_path.read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()
