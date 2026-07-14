"""Tests for the local content pipeline."""

import unittest
from typing import Any

from agents.audience_research.agent import AudienceResearchAgent
from agents.hook.agent import HookAgent
from agents.script.agent import ScriptAgent
from agents.storyboard.agent import StoryboardAgent
from engine.media.render_job import RenderJobStatus
from engine.runtime.runtime import HeliosRuntime
from engine.tasks.task import Task
from workflows.content_pipeline import ContentPipeline


class FailingScriptAgent(ScriptAgent):
    """Script agent that fails deterministically for pipeline tests."""

    def run(self, task: Task) -> Any:
        """Raise a deterministic script failure."""
        msg = "script step failed"
        raise RuntimeError(msg)


class ContentPipelineTestCase(unittest.TestCase):
    """Tests for ContentPipeline behavior."""

    def test_query_validation(self) -> None:
        """Pipeline rejects empty queries."""
        pipeline = ContentPipeline(HeliosRuntime())

        with self.assertRaises(ValueError):
            pipeline.run("")

    def test_language_and_age_range_are_forwarded(self) -> None:
        """Audience settings are forwarded to Mira."""
        pipeline = ContentPipeline(HeliosRuntime())

        result = pipeline.run(
            "AI Agents",
            language="en",
            target_age_range="25-44",
        )

        self.assertEqual(result.audience_profile.language, "en")
        self.assertEqual(result.audience_profile.target_age_range, "25-44")

    def test_target_duration_is_forwarded_to_lumen(self) -> None:
        """Target duration reaches the storyboard task."""
        pipeline = ContentPipeline(HeliosRuntime())

        result = pipeline.run("AI Agents", target_duration_seconds=45.0)

        self.assertGreater(result.storyboard.total_duration_seconds, 0)
        storyboard_agent = pipeline.runtime.registry.get("storyboard")
        assert isinstance(storyboard_agent, StoryboardAgent)
        self.assertIs(storyboard_agent.last_storyboard, result.storyboard)

    def test_standard_agents_are_registered(self) -> None:
        """Pipeline registers the twelve default mock agents."""
        runtime = HeliosRuntime()

        ContentPipeline(runtime)

        self.assertEqual(runtime.registry.count(), 12)
        self.assertTrue(runtime.registry.exists("trend_research"))
        self.assertTrue(runtime.registry.exists("video_production"))

    def test_existing_matching_agent_is_reused(self) -> None:
        """Pipeline respects agents already registered in the runtime."""
        runtime = HeliosRuntime()
        existing_agent = AudienceResearchAgent()
        runtime.register(existing_agent)

        ContentPipeline(runtime)

        self.assertIs(runtime.registry.get("audience_research"), existing_agent)
        self.assertEqual(runtime.registry.count(), 12)

    def test_steps_are_executed_in_order(self) -> None:
        """Runtime dispatch events reflect the expected pipeline order."""
        runtime = HeliosRuntime()
        dispatched_task_ids: list[str] = []
        runtime.event_bus.subscribe(
            "task.dispatched",
            lambda event: dispatched_task_ids.append(str(event.payload["task_id"])),
        )
        pipeline = ContentPipeline(runtime)

        pipeline.run("AI Agents")

        self.assertEqual(
            dispatched_task_ids,
            [
                "content-pipeline-trend_research",
                "content-pipeline-audience_research",
                "content-pipeline-knowledge",
                "content-pipeline-strategy",
                "content-pipeline-script",
                "content-pipeline-hook",
                "content-pipeline-storyboard",
                "content-pipeline-creative_director",
                "content-pipeline-avatar",
                "content-pipeline-voice",
                "content-pipeline-music",
                "content-pipeline-video_production",
            ],
        )

    def test_render_job_is_pending_and_task_ids_are_complete(self) -> None:
        """Pipeline returns a pending render job and all completed task IDs."""
        pipeline = ContentPipeline(HeliosRuntime())

        result = pipeline.run("AI Agents")

        self.assertIs(result.render_job.status, RenderJobStatus.PENDING)
        self.assertEqual(len(result.completed_task_ids), 12)

    def test_runtime_is_started_when_needed(self) -> None:
        """Pipeline starts an inactive runtime."""
        runtime = HeliosRuntime()
        pipeline = ContentPipeline(runtime)

        pipeline.run("AI Agents")

        self.assertTrue(runtime.running)

    def test_running_runtime_remains_active(self) -> None:
        """Pipeline leaves an already running runtime active."""
        runtime = HeliosRuntime()
        runtime.start()
        pipeline = ContentPipeline(runtime)

        pipeline.run("AI Agents")

        self.assertTrue(runtime.running)

    def test_pipeline_stops_after_failure(self) -> None:
        """Pipeline propagates errors and does not execute later agents."""
        runtime = HeliosRuntime()
        dispatched_task_ids: list[str] = []
        runtime.event_bus.subscribe(
            "task.dispatched",
            lambda event: dispatched_task_ids.append(str(event.payload["task_id"])),
        )
        ContentPipeline(runtime)
        runtime.unregister("script")
        runtime.register(FailingScriptAgent())

        with self.assertRaisesRegex(RuntimeError, "script step failed"):
            ContentPipeline(runtime, agents=[]).run("AI Agents")

        self.assertEqual(
            dispatched_task_ids,
            [
                "content-pipeline-trend_research",
                "content-pipeline-audience_research",
                "content-pipeline-knowledge",
                "content-pipeline-strategy",
            ],
        )
        hook_agent = runtime.registry.get("hook")
        assert isinstance(hook_agent, HookAgent)
        self.assertIsNone(hook_agent.last_hook)

    def test_multiple_pipeline_instances_share_no_state(self) -> None:
        """Separate pipeline instances keep independent runtime state."""
        first_pipeline = ContentPipeline(HeliosRuntime())
        second_pipeline = ContentPipeline(HeliosRuntime())

        first_result = first_pipeline.run("AI Agents")
        second_result = second_pipeline.run("AI Agents")

        self.assertIsNot(first_pipeline.runtime, second_pipeline.runtime)
        self.assertIsNot(first_result.trend_report, second_result.trend_report)

    def test_result_to_markdown(self) -> None:
        """ContentPipelineResult renders to Markdown."""
        pipeline = ContentPipeline(HeliosRuntime())

        result = pipeline.run("AI Agents")
        markdown = result.to_markdown()

        self.assertIn("# Content Pipeline Result: AI Agents", markdown)
        self.assertIn("Render Job", markdown)
        self.assertIn("content-pipeline-video_production", markdown)

    def test_custom_task_id_generator(self) -> None:
        """Task IDs can be generated deterministically by injection."""
        pipeline = ContentPipeline(
            HeliosRuntime(),
            task_id_generator=lambda step: f"test-run-{step}",
        )

        result = pipeline.run("AI Agents")

        self.assertEqual(result.completed_task_ids[0], "test-run-trend_research")
        self.assertEqual(result.completed_task_ids[-1], "test-run-video_production")


if __name__ == "__main__":
    unittest.main()
