"""Tests for the local content pipeline demo runner."""

import contextlib
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.run_content_pipeline import (
    ContentPipelineDemoResult,
    format_summary,
    main,
    parse_args,
    resolve_output_path,
    run_demo,
    slugify_query,
)


class ContentPipelineRunnerTestCase(unittest.TestCase):
    """Tests for the content pipeline CLI and report helpers."""

    def test_missing_query_is_rejected(self) -> None:
        """The CLI rejects a missing required query."""
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                parse_args([])

    def test_empty_query_is_rejected(self) -> None:
        """The CLI rejects a blank query."""
        with self.assertRaises(ValueError):
            parse_args(["   "])

    def test_invalid_duration_is_rejected(self) -> None:
        """The CLI rejects non-positive durations."""
        with self.assertRaises(ValueError):
            parse_args(["AI Agents", "--duration", "0"])

    def test_cli_defaults(self) -> None:
        """The CLI exposes the documented default values."""
        args = parse_args(["AI Agents"])

        self.assertEqual(args.query, "AI Agents")
        self.assertEqual(args.language, "de")
        self.assertEqual(args.age_range, "18-34")
        self.assertEqual(args.duration, 30.0)
        self.assertEqual(args.output_dir, Path("output"))

    def test_explicit_cli_values(self) -> None:
        """The CLI accepts explicit optional values."""
        args = parse_args(
            [
                "AI Agents",
                "--language",
                "en",
                "--age-range",
                "25-44",
                "--duration",
                "45",
                "--output-dir",
                "/tmp/helios-output",
            ],
        )

        self.assertEqual(args.language, "en")
        self.assertEqual(args.age_range, "25-44")
        self.assertEqual(args.duration, 45.0)
        self.assertEqual(args.output_dir, Path("/tmp/helios-output"))

    def test_slugify_query(self) -> None:
        """Queries produce lowercase deterministic slugs."""
        self.assertEqual(slugify_query("AI Agents"), "ai-agents")

    def test_slugify_handles_special_characters_safely(self) -> None:
        """Special characters cannot escape into the filename."""
        self.assertEqual(
            slugify_query("  AI / Agents: 2026!  "),
            "ai-agents-2026",
        )

    def test_slugify_prevents_path_traversal(self) -> None:
        """Traversal-only queries cannot produce output paths."""
        with self.assertRaises(ValueError):
            slugify_query("../../")

        self.assertEqual(slugify_query("../../AI/Agents"), "ai-agents")

    def test_existing_file_gets_numbered_suffix(self) -> None:
        """Existing reports are preserved with a numbered next path."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            (output_dir / "content-pipeline-ai-agents.md").write_text(
                "existing",
                encoding="utf-8",
            )

            path = resolve_output_path(output_dir, "AI Agents")

            self.assertEqual(path.name, "content-pipeline-ai-agents-2.md")

    def test_demo_writes_complete_markdown_report(self) -> None:
        """A successful demo writes every pipeline section."""
        with tempfile.TemporaryDirectory() as temp_dir:
            demo = run_demo("AI Agents", output_dir=Path(temp_dir))
            markdown = demo.markdown_path.read_text(encoding="utf-8")

            self.assertTrue(demo.markdown_path.exists())
            for heading in (
                "Trend Report",
                "Audience Profile",
                "Knowledge Response",
                "Content Strategy",
                "Video Script",
                "Optimized Hook",
                "Storyboard",
                "Creative Brief",
                "Avatar Profile",
                "Voice Profile",
                "Music Profile",
                "RenderJob",
                "VideoProductionPlan",
            ):
                self.assertIn(f"## {heading}", markdown)

            self.assertIn("- Query: AI Agents", markdown)
            self.assertIn("- Language: de", markdown)
            self.assertIn("- Target Age Range: 18-34", markdown)
            self.assertIn("- Target Duration: 30.0s", markdown)
            self.assertIn("- Completed Tasks: 12", markdown)
            self.assertIn("RenderJob Status: PENDING", markdown)

    def test_terminal_summary_contains_required_values(self) -> None:
        """The terminal summary includes all operational result values."""
        with tempfile.TemporaryDirectory() as temp_dir:
            demo = run_demo("AI Agents", output_dir=Path(temp_dir))
            summary = format_summary(demo)

            for value in (
                "Query: AI Agents",
                "Status: COMPLETED",
                "Abgeschlossene Tasks: 12",
                "Script-Titel:",
                "Ausgewählter Hook:",
                "Storyboard-Szenen:",
                "Zielplattform:",
                "Gesamtdauer:",
                "RenderJob-ID:",
                "RenderJob-Status: PENDING",
                str(demo.markdown_path),
            ):
                self.assertIn(value, summary)

    def test_main_returns_zero_on_success(self) -> None:
        """A successful command returns exit code zero."""
        with tempfile.TemporaryDirectory() as temp_dir:
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                exit_code = main(
                    ["AI Agents", "--output-dir", temp_dir],
                )

            self.assertEqual(exit_code, 0)
            self.assertIn("Status: COMPLETED", stdout.getvalue())

    def test_script_runs_directly_from_outside_repository(self) -> None:
        """The documented script path works without a configured PYTHONPATH."""
        script_path = Path(__file__).parents[1] / "scripts/run_content_pipeline.py"
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "output"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(script_path),
                    "AI Agents",
                    "--output-dir",
                    str(output_dir),
                ],
                cwd=temp_dir,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn("Status: COMPLETED", completed.stdout)
            self.assertTrue(
                (output_dir / "content-pipeline-ai-agents.md").exists(),
            )

    def test_main_returns_one_and_writes_stderr_on_failure(self) -> None:
        """Pipeline failures return one and are reported on stderr."""
        def failing_runner(
            query: str,
            language: str,
            target_age_range: str,
            target_duration_seconds: float,
            output_dir: Path,
        ) -> ContentPipelineDemoResult:
            del query, language, target_age_range, target_duration_seconds, output_dir
            msg = "pipeline failed"
            raise RuntimeError(msg)

        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            exit_code = main(["AI Agents"], runner=failing_runner)

        self.assertEqual(exit_code, 1)
        self.assertIn("Fehler: pipeline failed", stderr.getvalue())

    def test_failure_does_not_write_a_file(self) -> None:
        """A failed pipeline produces no Markdown report."""
        def failing_runner(
            query: str,
            language: str,
            target_age_range: str,
            target_duration_seconds: float,
            output_dir: Path,
        ) -> ContentPipelineDemoResult:
            del query, language, target_age_range, target_duration_seconds, output_dir
            msg = "pipeline failed"
            raise RuntimeError(msg)

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "reports"
            with contextlib.redirect_stderr(io.StringIO()):
                exit_code = main(
                    ["AI Agents", "--output-dir", str(output_dir)],
                    runner=failing_runner,
                )

            self.assertEqual(exit_code, 1)
            self.assertFalse(output_dir.exists())


if __name__ == "__main__":
    unittest.main()
