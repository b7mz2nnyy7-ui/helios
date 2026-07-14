"""Runtime integration tests for Forge video production agent."""

import unittest

from agents.avatar.models import AvatarProfile
from agents.creative_director.models import CreativeBrief
from agents.music.models import MusicProfile
from agents.storyboard.models import Storyboard, StoryboardScene
from agents.video_production.agent import VideoProductionAgent
from agents.voice.models import VoiceProfile
from engine.media.render_job import RenderJob, RenderJobStatus
from engine.runtime.capability import AgentCapability
from engine.runtime.runtime import HeliosRuntime
from engine.tasks.priority import TaskPriority
from engine.tasks.status import TaskStatus
from engine.tasks.task import Task


def create_video_task(payload: dict[str, object] | None = None) -> Task:
    """Create a video production task for runtime integration tests."""
    task_payload = {
        "storyboard": Storyboard(
            title="AI Agents Workflow Storyboard",
            selected_hook="The fastest AI win is a workflow you stop repeating.",
            scenes=[
                StoryboardScene(1, 6.0, "Open hook.", "Creator at desk.", "Push", None, "Cut"),
                StoryboardScene(2, 8.0, "Show work.", "Split screen.", "Track", None, "Cut"),
                StoryboardScene(3, 10.0, "Show system.", "Node diagram.", "Zoom", None, "Fade"),
            ],
            visual_style="Clean kinetic captions",
            summary="Storyboard for practical AI workflow content.",
            generated_by="mock:mock-storyboard-model",
        ),
        "creative_brief": CreativeBrief(
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
        ),
        "avatar_profile": AvatarProfile(
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
        ),
        "voice_profile": VoiceProfile(
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
        ),
        "music_profile": MusicProfile(
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
        ),
    }
    return Task(
        task_id="video-task-1",
        title="Video Production",
        description="Create a provider-neutral render job.",
        priority=TaskPriority.MEDIUM,
        required_capability=AgentCapability.VIDEO_PRODUCTION,
        payload=task_payload if payload is None else payload,
    )


class VideoProductionRuntimeIntegrationTestCase(unittest.TestCase):
    """Integration tests for Forge through HeliosRuntime."""

    def test_runtime_dispatches_video_production_task_to_forge(self) -> None:
        """Runtime can dispatch VIDEO_PRODUCTION tasks to Forge."""
        runtime = HeliosRuntime()
        forge = VideoProductionAgent()
        task = create_video_task()
        runtime.register(forge)

        result = runtime.submit_task(task)

        self.assertIsInstance(result, RenderJob)
        self.assertIs(result, task.result)
        self.assertIs(task.status, TaskStatus.COMPLETED)
        self.assertIs(forge.last_render_job, result)
        self.assertEqual(result.status, RenderJobStatus.PENDING)

    def test_runtime_returns_render_job(self) -> None:
        """Runtime returns the RenderJob from Forge."""
        runtime = HeliosRuntime()
        runtime.register(VideoProductionAgent())
        task = create_video_task()

        result = runtime.submit_task(task)

        self.assertIsInstance(result, RenderJob)

    def test_runtime_propagates_forge_errors(self) -> None:
        """Runtime propagates Forge validation errors."""
        runtime = HeliosRuntime()
        runtime.register(VideoProductionAgent())
        task = create_video_task({"storyboard": "invalid"})

        with self.assertRaises(ValueError):
            runtime.submit_task(task)

        self.assertIs(task.status, TaskStatus.FAILED)


if __name__ == "__main__":
    unittest.main()
