"""Runtime integration tests for Vox voice agent."""

import unittest

from agents.avatar.models import AvatarProfile
from agents.creative_director.models import CreativeBrief
from agents.script.models import ScriptSection, VideoScript
from agents.voice.agent import VoiceAgent
from agents.voice.models import VoiceProfile
from engine.runtime.capability import AgentCapability
from engine.runtime.runtime import HeliosRuntime
from engine.tasks.priority import TaskPriority
from engine.tasks.status import TaskStatus
from engine.tasks.task import Task


def create_voice_task(payload: dict[str, object] | None = None) -> Task:
    """Create a voice task for runtime integration tests."""
    task_payload = {
        "video_script": VideoScript(
            title="AI Agents That Actually Save Time",
            hook="The fastest AI win is a workflow you stop repeating.",
            sections=[
                ScriptSection("Problem", "Teams are overwhelmed by tools."),
                ScriptSection("Insight", "Automation removes repeated work."),
                ScriptSection("Action", "Start with one pain point."),
            ],
            call_to_action="Pick one recurring content task.",
            summary="A practical script about AI workflows.",
            generated_by="mock:mock-script-model",
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
    }
    return Task(
        task_id="voice-task-1",
        title="Voice",
        description="Create a voice profile.",
        priority=TaskPriority.MEDIUM,
        required_capability=AgentCapability.VOICE,
        payload=task_payload if payload is None else payload,
    )


class VoiceRuntimeIntegrationTestCase(unittest.TestCase):
    """Integration tests for Vox through HeliosRuntime."""

    def test_runtime_dispatches_voice_task_to_vox(self) -> None:
        """Runtime can dispatch VOICE tasks to Vox."""
        runtime = HeliosRuntime()
        vox = VoiceAgent()
        task = create_voice_task()
        runtime.register(vox)

        result = runtime.submit_task(task)

        self.assertIsInstance(result, VoiceProfile)
        self.assertIs(result, task.result)
        self.assertIs(task.status, TaskStatus.COMPLETED)
        self.assertIs(vox.last_voice_profile, result)

    def test_runtime_returns_voice_profile(self) -> None:
        """Runtime returns the VoiceProfile from Vox."""
        runtime = HeliosRuntime()
        runtime.register(VoiceAgent())
        task = create_voice_task()

        result = runtime.submit_task(task)

        self.assertIsInstance(result, VoiceProfile)

    def test_runtime_propagates_vox_errors(self) -> None:
        """Runtime propagates Vox validation errors."""
        runtime = HeliosRuntime()
        runtime.register(VoiceAgent())
        task = create_voice_task({"video_script": "invalid"})

        with self.assertRaises(ValueError):
            runtime.submit_task(task)

        self.assertIs(task.status, TaskStatus.FAILED)


if __name__ == "__main__":
    unittest.main()
