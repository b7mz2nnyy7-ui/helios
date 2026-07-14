"""Tests for the Lumen storyboard agent."""

import unittest
from typing import Any

from agents.hook.models import HookCandidate, OptimizedHook
from agents.script.models import ScriptSection, VideoScript
from agents.storyboard.agent import StoryboardAgent
from agents.storyboard.mock_llm_provider import MockStoryboardLLMProvider
from agents.storyboard.models import Storyboard, StoryboardScene
from engine.llm.base_provider import BaseLLMProvider
from engine.llm.models import LLMRequest, LLMResponse
from engine.runtime.capability import AgentCapability
from engine.tasks.priority import TaskPriority
from engine.tasks.status import TaskStatus
from engine.tasks.task import Task
from engine.tools.llm_tool import LLMTool


class RecordingStoryboardLLMProvider(BaseLLMProvider):
    """LLM provider that records storyboard requests."""

    def __init__(self) -> None:
        """Create a recording provider."""
        super().__init__(provider_id="recording", model="recording-storyboard-model")
        self.received_request: LLMRequest | None = None
        self.response = MockStoryboardLLMProvider(
            provider_id=self.provider_id,
            model=self.model,
        ).generate(
            LLMRequest(
                system_prompt="recording",
                user_prompt="recording",
            ),
        )

    def generate(self, request: LLMRequest) -> LLMResponse:
        """Record the request and return a deterministic response."""
        self.received_request = request
        return self.response


class FailingStoryboardLLMProvider(BaseLLMProvider):
    """LLM provider that always fails."""

    def __init__(self) -> None:
        """Create a failing provider."""
        super().__init__(provider_id="failing", model="failing-storyboard-model")

    def generate(self, request: LLMRequest) -> LLMResponse:
        """Raise a runtime error."""
        msg = "storyboard llm failed"
        raise RuntimeError(msg)


def create_video_script() -> VideoScript:
    """Create a video script for storyboard tests."""
    return VideoScript(
        title="AI Agents That Actually Save Time",
        hook="Most AI agent content sounds futuristic.",
        sections=[
            ScriptSection("Problem", "Teams are overwhelmed by tools."),
            ScriptSection("Insight", "Automation removes repeated work."),
            ScriptSection("Action", "Start with one pain point."),
        ],
        call_to_action="Pick one recurring content task.",
        summary="A practical script about AI workflows.",
        generated_by="mock:mock-script-model",
    )


def create_optimized_hook() -> OptimizedHook:
    """Create an optimized hook for storyboard tests."""
    selected_hook = HookCandidate(
        text="The fastest AI win is a workflow you stop repeating.",
        score=0.95,
        reason="Highest clarity and novelty.",
    )
    return OptimizedHook(
        original_hook="Most AI agent content sounds futuristic.",
        selected_hook=selected_hook,
        candidates=[selected_hook],
        summary="Optimized for clarity.",
        generated_by="mock:mock-hook-model",
    )


def create_storyboard_payload() -> dict[str, Any]:
    """Create a valid storyboard payload."""
    return {
        "video_script": create_video_script(),
        "optimized_hook": create_optimized_hook(),
    }


def create_storyboard_task(payload: dict[str, Any] | None = None) -> Task:
    """Create a storyboard task."""
    return Task(
        task_id="storyboard-task-1",
        title="Storyboard",
        description="Create a short-form video storyboard.",
        priority=TaskPriority.MEDIUM,
        required_capability=AgentCapability.STORYBOARD,
        payload=create_storyboard_payload() if payload is None else payload,
    )


class StoryboardAgentTestCase(unittest.TestCase):
    """Tests for StoryboardAgent behavior."""

    def test_agent_has_storyboard_capability(self) -> None:
        """Lumen declares the STORYBOARD capability."""
        agent = StoryboardAgent()

        self.assertTrue(agent.can_handle(AgentCapability.STORYBOARD))

    def test_agent_name_is_lumen(self) -> None:
        """Lumen has the expected display name."""
        agent = StoryboardAgent()

        self.assertEqual(agent.name, "Lumen")

    def test_default_llm_tool_exists(self) -> None:
        """Lumen has a default LLM tool."""
        agent = StoryboardAgent()

        self.assertIsInstance(agent.get_tool("llm"), LLMTool)

    def test_valid_inputs_complete_task(self) -> None:
        """Valid storyboard inputs complete the task."""
        agent = StoryboardAgent()
        task = create_storyboard_task()

        result = agent.run(task)

        self.assertIsInstance(result, Storyboard)
        self.assertIs(task.status, TaskStatus.COMPLETED)

    def test_missing_video_script_raises_value_error(self) -> None:
        """Lumen rejects missing or invalid VideoScript payloads."""
        agent = StoryboardAgent()
        payload = create_storyboard_payload()
        payload["video_script"] = "invalid"
        task = create_storyboard_task(payload)

        with self.assertRaises(ValueError):
            agent.run(task)

    def test_missing_optimized_hook_raises_value_error(self) -> None:
        """Lumen rejects missing or invalid OptimizedHook payloads."""
        agent = StoryboardAgent()
        payload = create_storyboard_payload()
        payload["optimized_hook"] = "invalid"
        task = create_storyboard_task(payload)

        with self.assertRaises(ValueError):
            agent.run(task)

    def test_invalid_target_duration_raises_value_error(self) -> None:
        """Lumen rejects invalid target durations."""
        agent = StoryboardAgent()
        payload = create_storyboard_payload()
        payload["target_duration_seconds"] = 0.0
        task = create_storyboard_task(payload)

        with self.assertRaises(ValueError):
            agent.run(task)

    def test_prompt_contains_script_hook_sections_and_duration(self) -> None:
        """Lumen prompt contains script, hook, sections and target duration."""
        provider = RecordingStoryboardLLMProvider()
        agent = StoryboardAgent(tools=[LLMTool(provider=provider)])
        payload = create_storyboard_payload()
        payload["target_duration_seconds"] = 45.0
        task = create_storyboard_task(payload)

        agent.run(task)

        request = provider.received_request
        assert request is not None
        self.assertIn("Script-Titel: AI Agents That Actually Save Time", request.user_prompt)
        self.assertIn(
            "Ausgewählter Hook: The fastest AI win is a workflow you stop repeating.",
            request.user_prompt,
        )
        self.assertIn("Problem", request.user_prompt)
        self.assertIn("Insight", request.user_prompt)
        self.assertIn("Action", request.user_prompt)
        self.assertIn("Call to Action: Pick one recurring content task.", request.user_prompt)
        self.assertIn("Zieldauer: 45.0s", request.user_prompt)
        self.assertIn("Kamera", request.user_prompt)
        self.assertIn("Visuals", request.user_prompt)
        self.assertIn("Übergängen", request.user_prompt)

    def test_storyboard_has_at_least_three_scenes(self) -> None:
        """Lumen creates at least three scenes."""
        agent = StoryboardAgent()
        task = create_storyboard_task()

        storyboard = agent.run(task)

        self.assertGreaterEqual(len(storyboard.scenes), 3)

    def test_scene_numbers_are_correct(self) -> None:
        """Scene numbers are sequential."""
        agent = StoryboardAgent()
        task = create_storyboard_task()

        storyboard = agent.run(task)

        self.assertEqual(
            [scene.scene_number for scene in storyboard.scenes],
            [1, 2, 3, 4],
        )

    def test_total_duration_matches_scene_sum(self) -> None:
        """Storyboard duration equals the sum of scene durations."""
        agent = StoryboardAgent()
        task = create_storyboard_task()

        storyboard = agent.run(task)

        expected_duration = sum(scene.duration_seconds for scene in storyboard.scenes)
        self.assertEqual(storyboard.total_duration_seconds, expected_duration)

    def test_last_storyboard_and_task_result_are_identical(self) -> None:
        """Lumen stores the storyboard and writes it to the task."""
        agent = StoryboardAgent()
        task = create_storyboard_task()

        storyboard = agent.run(task)

        self.assertIs(agent.last_storyboard, storyboard)
        self.assertIs(task.result, storyboard)

    def test_mock_provider_is_deterministic(self) -> None:
        """MockStoryboardLLMProvider returns deterministic content."""
        provider = MockStoryboardLLMProvider()
        request = LLMRequest(system_prompt="Lumen", user_prompt="Storyboard data")

        first_response = provider.generate(request)
        second_response = provider.generate(request)

        self.assertEqual(first_response, second_response)
        self.assertEqual(first_response.provider, "mock")
        self.assertEqual(first_response.model, "mock-storyboard-model")

    def test_model_validations_work(self) -> None:
        """Storyboard models validate invalid values."""
        with self.assertRaises(ValueError):
            StoryboardScene(
                scene_number=0,
                duration_seconds=1.0,
                narration="Narration",
                visual_description="Visual",
                camera_direction="Camera",
                on_screen_text=None,
                transition="Cut",
            )

        with self.assertRaises(ValueError):
            Storyboard(
                title="Invalid",
                selected_hook="Hook",
                scenes=[],
                visual_style="Style",
                summary="Summary",
                generated_by="mock",
            )

    def test_storyboard_markdown_contains_scene_data(self) -> None:
        """Storyboard can be rendered as Markdown."""
        agent = StoryboardAgent()
        task = create_storyboard_task()

        storyboard = agent.run(task)

        self.assertIn("Scene 1", storyboard.to_markdown())
        self.assertIn(storyboard.selected_hook, storyboard.to_markdown())

    def test_llm_failure_sets_task_failed(self) -> None:
        """LLM errors move the task to FAILED."""
        agent = StoryboardAgent(
            tools=[LLMTool(provider=FailingStoryboardLLMProvider())],
        )
        task = create_storyboard_task()

        with self.assertRaises(RuntimeError):
            agent.run(task)

        self.assertIs(task.status, TaskStatus.FAILED)
        self.assertEqual(task.error_message, "storyboard llm failed")

    def test_errors_are_propagated(self) -> None:
        """LLM errors are propagated unchanged."""
        agent = StoryboardAgent(
            tools=[LLMTool(provider=FailingStoryboardLLMProvider())],
        )
        task = create_storyboard_task()

        with self.assertRaisesRegex(RuntimeError, "storyboard llm failed"):
            agent.run(task)


if __name__ == "__main__":
    unittest.main()
