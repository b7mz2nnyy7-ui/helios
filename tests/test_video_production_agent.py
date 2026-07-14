"""Tests for the Forge video production agent."""

import unittest
from typing import Any

from agents.avatar.models import AvatarProfile
from agents.creative_director.models import CreativeBrief
from agents.music.models import MusicProfile
from agents.storyboard.models import Storyboard, StoryboardScene
from agents.video_production.agent import VideoProductionAgent
from agents.video_production.mock_llm_provider import MockVideoProductionLLMProvider
from agents.voice.models import VoiceProfile
from engine.llm.base_provider import BaseLLMProvider
from engine.llm.models import LLMRequest, LLMResponse
from engine.media.render_job import RenderJob, RenderJobStatus
from engine.runtime.capability import AgentCapability
from engine.tasks.priority import TaskPriority
from engine.tasks.status import TaskStatus
from engine.tasks.task import Task
from engine.tools.llm_tool import LLMTool


class RecordingVideoProductionLLMProvider(BaseLLMProvider):
    """LLM provider that records video production requests."""

    def __init__(self) -> None:
        """Create a recording provider."""
        super().__init__(
            provider_id="recording",
            model="recording-video-production-model",
        )
        self.received_request: LLMRequest | None = None
        self.response = MockVideoProductionLLMProvider(
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


class FailingVideoProductionLLMProvider(BaseLLMProvider):
    """LLM provider that always fails."""

    def __init__(self) -> None:
        """Create a failing provider."""
        super().__init__(provider_id="failing", model="failing-video-model")

    def generate(self, request: LLMRequest) -> LLMResponse:
        """Raise a runtime error."""
        msg = "video production llm failed"
        raise RuntimeError(msg)


def create_storyboard() -> Storyboard:
    """Create a storyboard for video production tests."""
    return Storyboard(
        title="AI Agents Workflow Storyboard",
        selected_hook="The fastest AI win is a workflow you stop repeating.",
        scenes=[
            StoryboardScene(1, 6.0, "Open hook.", "Creator at desk.", "Push in", None, "Cut"),
            StoryboardScene(2, 8.0, "Show work.", "Split screen.", "Track", None, "Cut"),
            StoryboardScene(3, 10.0, "Show system.", "Node diagram.", "Zoom", None, "Fade"),
        ],
        visual_style="Clean kinetic captions",
        summary="Storyboard for practical AI workflow content.",
        generated_by="mock:mock-storyboard-model",
    )


def create_creative_brief() -> CreativeBrief:
    """Create a creative brief for video production tests."""
    return CreativeBrief(
        visual_style="Clean kinetic tech editorial",
        color_palette="Deep charcoal, electric cyan, soft white",
        typography="Bold grotesk headlines",
        camera_style="Fast push-ins and UI closeups",
        lighting_style="High-contrast desk light",
        animation_style="Minimal node lines",
        avatar_style="Confident operator, practical and calm",
        editing_style="Tight cuts",
        music_style="Modern pulse",
        emotional_tone="Clear, focused and empowering",
        platform_style="Short-form vertical video",
        branding_notes="Use practical proof and avoid hype",
        summary="Creative direction for practical AI workflow content.",
        generated_by="mock:mock-creative-model",
    )


def create_avatar_profile() -> AvatarProfile:
    """Create an avatar profile for video production tests."""
    return AvatarProfile(
        name="Echo",
        age_group="28-35",
        appearance="Approachable tech strategist.",
        clothing_style="Minimal dark jacket.",
        hairstyle="Neat modern styling.",
        facial_expression="Focused and calm.",
        body_language="Open posture.",
        voice_style="Clear, grounded and practical",
        energy_level="Medium-high",
        platform_fit="Short-form vertical explainers",
        branding_notes="Avoid hype.",
        summary="Consistent AI avatar.",
        generated_by="mock:mock-avatar-model",
    )


def create_voice_profile() -> VoiceProfile:
    """Create a voice profile for video production tests."""
    return VoiceProfile(
        language="de",
        voice_character="Calm strategic narrator",
        speaking_style="Clear, concise and slightly energetic",
        emotional_tone="Focused",
        pace_words_per_minute=145,
        pitch="Medium",
        emphasis_notes="Emphasize workflow.",
        pronunciation_notes="Keep AI terms crisp.",
        multilingual_notes="Preserve common English terms.",
        platform_fit="Short-form narration.",
        summary="Voice profile.",
        generated_by="mock:mock-voice-model",
    )


def create_music_profile() -> MusicProfile:
    """Create a music profile for video production tests."""
    return MusicProfile(
        genre="Minimal electronic pulse",
        mood="Focused",
        energy_level="Medium-high",
        tempo_bpm=118,
        transition_style="Tight whooshes",
        sound_effect_style="Clean UI taps",
        intro_style="Immediate beat",
        outro_style="Clean resolve",
        platform_fit="Short-form pacing",
        copyright_strategy="Royalty-safe music",
        summary="Music profile.",
        generated_by="mock:mock-music-model",
    )


def create_video_payload() -> dict[str, Any]:
    """Create a valid video production payload."""
    return {
        "storyboard": create_storyboard(),
        "creative_brief": create_creative_brief(),
        "avatar_profile": create_avatar_profile(),
        "voice_profile": create_voice_profile(),
        "music_profile": create_music_profile(),
    }


def create_video_task(payload: dict[str, Any] | None = None) -> Task:
    """Create a video production task."""
    return Task(
        task_id="video-task-1",
        title="Video Production",
        description="Create a provider-neutral render job.",
        priority=TaskPriority.MEDIUM,
        required_capability=AgentCapability.VIDEO_PRODUCTION,
        payload=create_video_payload() if payload is None else payload,
    )


class VideoProductionAgentTestCase(unittest.TestCase):
    """Tests for VideoProductionAgent behavior."""

    def test_agent_has_video_production_capability(self) -> None:
        """Forge declares the VIDEO_PRODUCTION capability."""
        agent = VideoProductionAgent()

        self.assertTrue(agent.can_handle(AgentCapability.VIDEO_PRODUCTION))

    def test_agent_name_is_forge(self) -> None:
        """Forge has the expected display name."""
        agent = VideoProductionAgent()

        self.assertEqual(agent.name, "Forge")

    def test_default_llm_tool_exists(self) -> None:
        """Forge has a default LLM tool."""
        agent = VideoProductionAgent()

        self.assertIsInstance(agent.get_tool("llm"), LLMTool)

    def test_payload_validated_and_task_completed(self) -> None:
        """Valid video production inputs complete the task."""
        agent = VideoProductionAgent()
        task = create_video_task()

        render_job = agent.run(task)

        self.assertIsInstance(render_job, RenderJob)
        self.assertIs(task.status, TaskStatus.COMPLETED)

    def test_missing_storyboard_raises_value_error(self) -> None:
        """Forge rejects missing Storyboard payloads."""
        self._assert_missing_model_raises("storyboard")

    def test_missing_creative_brief_raises_value_error(self) -> None:
        """Forge rejects missing CreativeBrief payloads."""
        self._assert_missing_model_raises("creative_brief")

    def test_missing_avatar_raises_value_error(self) -> None:
        """Forge rejects missing AvatarProfile payloads."""
        self._assert_missing_model_raises("avatar_profile")

    def test_missing_voice_raises_value_error(self) -> None:
        """Forge rejects missing VoiceProfile payloads."""
        self._assert_missing_model_raises("voice_profile")

    def test_missing_music_raises_value_error(self) -> None:
        """Forge rejects missing MusicProfile payloads."""
        self._assert_missing_model_raises("music_profile")

    def test_task_result_and_last_render_job_are_identical(self) -> None:
        """Forge stores the render job and writes it to the task."""
        agent = VideoProductionAgent()
        task = create_video_task()

        render_job = agent.run(task)

        self.assertIs(task.result, render_job)
        self.assertIs(agent.last_render_job, render_job)

    def test_render_job_status_is_pending(self) -> None:
        """Forge creates a pending render job."""
        agent = VideoProductionAgent()
        task = create_video_task()

        render_job = agent.run(task)

        self.assertEqual(render_job.status, RenderJobStatus.PENDING)

    def test_render_plan_contains_all_scenes(self) -> None:
        """Forge maps every storyboard scene to a render scene."""
        agent = VideoProductionAgent()
        task = create_video_task()

        render_job = agent.run(task)

        self.assertEqual(len(render_job.plan.scenes), 3)
        self.assertEqual(render_job.plan.total_duration_seconds, 24.0)
        self.assertIn("Creator at desk.", render_job.plan.scenes[0].visual_instruction)
        self.assertIn("Clear, concise", render_job.plan.scenes[0].voice_instruction)
        self.assertIn("Minimal electronic pulse", render_job.plan.scenes[0].music_instruction)

    def test_prompt_contains_all_required_models(self) -> None:
        """Forge prompt contains storyboard, creative, avatar, voice and music data."""
        provider = RecordingVideoProductionLLMProvider()
        agent = VideoProductionAgent(tools=[LLMTool(provider=provider)])
        task = create_video_task()

        agent.run(task)

        request = provider.received_request
        assert request is not None
        self.assertIn("Storyboard", request.user_prompt)
        self.assertIn("AI Agents Workflow Storyboard", request.user_prompt)
        self.assertIn("CreativeBrief", request.user_prompt)
        self.assertIn("Clean kinetic tech editorial", request.user_prompt)
        self.assertIn("AvatarProfile", request.user_prompt)
        self.assertIn("Echo", request.user_prompt)
        self.assertIn("VoiceProfile", request.user_prompt)
        self.assertIn("Clear, concise and slightly energetic", request.user_prompt)
        self.assertIn("MusicProfile", request.user_prompt)
        self.assertIn("Minimal electronic pulse", request.user_prompt)
        self.assertEqual(
            request.system_prompt,
            "Forge erstellt providerneutrale Produktionspläne für KI-Videos.",
        )

    def test_mock_provider_is_deterministic(self) -> None:
        """MockVideoProductionLLMProvider returns deterministic content."""
        provider = MockVideoProductionLLMProvider()
        request = LLMRequest(system_prompt="Forge", user_prompt="Production data")

        first_response = provider.generate(request)
        second_response = provider.generate(request)

        self.assertEqual(first_response, second_response)
        self.assertEqual(first_response.provider, "mock")
        self.assertEqual(first_response.model, "mock-video-production-model")

    def test_llm_failure_sets_task_failed(self) -> None:
        """LLM errors move the task to FAILED."""
        agent = VideoProductionAgent(
            tools=[LLMTool(provider=FailingVideoProductionLLMProvider())],
        )
        task = create_video_task()

        with self.assertRaises(RuntimeError):
            agent.run(task)

        self.assertIs(task.status, TaskStatus.FAILED)
        self.assertEqual(task.error_message, "video production llm failed")

    def test_errors_are_propagated(self) -> None:
        """LLM errors are propagated unchanged."""
        agent = VideoProductionAgent(
            tools=[LLMTool(provider=FailingVideoProductionLLMProvider())],
        )
        task = create_video_task()

        with self.assertRaisesRegex(RuntimeError, "video production llm failed"):
            agent.run(task)

    def _assert_missing_model_raises(self, field_name: str) -> None:
        payload = create_video_payload()
        payload[field_name] = "invalid"
        agent = VideoProductionAgent()
        task = create_video_task(payload)

        with self.assertRaises(ValueError):
            agent.run(task)


if __name__ == "__main__":
    unittest.main()
