"""Tests for the local content pipeline demo runner."""

import contextlib
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from engine.media.asset import MediaAssetType
from engine.media.render_job import RenderJobStatus
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
        self.assertFalse(args.render)
        self.assertEqual(args.render_provider, "mock-video")

    def test_render_flag_is_parsed(self) -> None:
        """The CLI enables rendering only when requested."""
        args = parse_args(["AI Agents", "--render"])

        self.assertTrue(args.render)
        self.assertEqual(args.render_provider, "mock-video")

    def test_explicit_render_provider_is_parsed(self) -> None:
        """The CLI retains an explicit render provider ID."""
        args = parse_args(
            [
                "AI Agents",
                "--render",
                "--render-provider",
                "custom-video",
            ],
        )

        self.assertTrue(args.render)
        self.assertEqual(args.render_provider, "custom-video")

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
            self.assertIn("# Render Result", markdown)
            self.assertIn("Render not executed", markdown)

    def test_demo_with_render_completes_job_and_video_asset(self) -> None:
        """The optional render step completes the existing render job."""
        with tempfile.TemporaryDirectory() as temp_dir:
            demo = run_demo(
                "AI Agents",
                output_dir=Path(temp_dir),
                render=True,
            )

            asset = demo.rendered_asset
            self.assertIsNotNone(asset)
            assert asset is not None
            self.assertIs(
                demo.pipeline_result.render_job.status,
                RenderJobStatus.COMPLETED,
            )
            self.assertIs(demo.pipeline_result.render_job.result_asset, asset)
            self.assertIs(asset.asset_type, MediaAssetType.VIDEO)
            self.assertEqual(asset.format, "mp4")

    def test_render_markdown_contains_asset_and_metadata(self) -> None:
        """Rendered reports contain the complete mock asset result."""
        with tempfile.TemporaryDirectory() as temp_dir:
            demo = run_demo(
                "AI Agents",
                output_dir=Path(temp_dir),
                render=True,
            )
            markdown = demo.markdown_path.read_text(encoding="utf-8")

            for value in (
                "# Render Result",
                "RenderJob Status: COMPLETED",
                "Provider: mock-video",
                "Asset ID: asset-render-plan-ai-agents-workflow-storyboard",
                "Asset Type: VIDEO",
                "Asset Format: mp4",
                "render_job_id:",
                "plan_id:",
                "target_platform:",
                "total_duration_seconds:",
                "scene_count:",
            ):
                self.assertIn(value, markdown)

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

    def test_render_terminal_summary_contains_asset_values(self) -> None:
        """Rendered terminal output contains the required asset values."""
        with tempfile.TemporaryDirectory() as temp_dir:
            demo = run_demo(
                "AI Agents",
                output_dir=Path(temp_dir),
                render=True,
            )
            summary = format_summary(demo)

            for value in (
                "Pipeline-Status: COMPLETED",
                "RenderJob-Status: COMPLETED",
                "Provider: mock-video",
                "Asset-ID:",
                "Asset-Typ: VIDEO",
                "Asset-Format: mp4",
                "Zielplattform:",
                "Gesamtdauer:",
                "Szenenanzahl: 4",
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

    def test_main_returns_zero_with_render(self) -> None:
        """The CLI completes the optional render path successfully."""
        with tempfile.TemporaryDirectory() as temp_dir:
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                exit_code = main(
                    ["AI Agents", "--render", "--output-dir", temp_dir],
                )

            self.assertEqual(exit_code, 0)
            self.assertIn("RenderJob-Status: COMPLETED", stdout.getvalue())

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
            *,
            render: bool = False,
            render_provider: str = "mock-video",
        ) -> ContentPipelineDemoResult:
            del (
                query,
                language,
                target_age_range,
                target_duration_seconds,
                output_dir,
                render,
                render_provider,
            )
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
            *,
            render: bool = False,
            render_provider: str = "mock-video",
        ) -> ContentPipelineDemoResult:
            del (
                query,
                language,
                target_age_range,
                target_duration_seconds,
                output_dir,
                render,
                render_provider,
            )
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

    def test_unknown_render_provider_returns_one_without_report(self) -> None:
        """Unknown providers fail without writing a success report."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "reports"
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                exit_code = main(
                    [
                        "AI Agents",
                        "--render",
                        "--render-provider",
                        "unknown",
                        "--output-dir",
                        str(output_dir),
                    ],
                )

            self.assertEqual(exit_code, 1)
            self.assertIn("Fehler:", stderr.getvalue())
            self.assertIn("unknown", stderr.getvalue())
            self.assertFalse(output_dir.exists())

    def test_render_runs_share_no_state(self) -> None:
        """Separate demo runs create independent jobs and assets."""
        with tempfile.TemporaryDirectory() as temp_dir:
            first = run_demo(
                "AI Agents",
                output_dir=Path(temp_dir),
                render=True,
            )
            second = run_demo(
                "AI Agents",
                output_dir=Path(temp_dir),
                render=True,
            )

            self.assertIsNot(
                first.pipeline_result.render_job,
                second.pipeline_result.render_job,
            )
            self.assertIsNot(first.rendered_asset, second.rendered_asset)
            self.assertNotEqual(first.markdown_path, second.markdown_path)

    def test_render_uses_no_network_and_creates_no_video_file(self) -> None:
        """Mock rendering writes only the requested Markdown report."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            with patch("socket.socket", side_effect=AssertionError("network used")):
                demo = run_demo(
                    "AI Agents",
                    output_dir=output_dir,
                    render=True,
                )

            self.assertTrue(demo.markdown_path.exists())
            self.assertEqual(list(output_dir.glob("*.mp4")), [])
            self.assertEqual(
                [path.suffix for path in output_dir.iterdir()],
                [".md"],
            )


if __name__ == "__main__":
    unittest.main()
