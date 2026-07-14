"""Runtime integration tests for Pulse music and sound agent."""

import unittest

from agents.audience_research.models import AudiencePainPoint, AudienceProfile
from agents.creative_director.models import CreativeBrief
from agents.music.agent import MusicAgent
from agents.music.models import MusicProfile
from agents.script.models import ScriptSection, VideoScript
from engine.runtime.capability import AgentCapability
from engine.runtime.runtime import HeliosRuntime
from engine.tasks.priority import TaskPriority
from engine.tasks.status import TaskStatus
from engine.tasks.task import Task


def create_music_task(payload: dict[str, object] | None = None) -> Task:
    """Create a music task for runtime integration tests."""
    task_payload = {
        "creative_brief": CreativeBrief(
            visual_style="Clean kinetic tech editorial",
            color_palette="Deep charcoal, electric cyan, soft white",
            typography="Bold grotesk headlines",
            camera_style="Fast push-ins and UI closeups",
            lighting_style="High-contrast desk light",
            animation_style="Minimal node lines",
            avatar_style="Confident operator, practical and calm",
            editing_style="Tight cuts",
            music_style="Modern pulse, restrained percussion and light synth",
            emotional_tone="Clear, focused and empowering",
            platform_style="Short-form vertical video",
            branding_notes="Use practical proof and avoid hype",
            summary="Creative direction for practical AI workflow content.",
            generated_by="mock:mock-creative-model",
        ),
        "audience_profile": AudienceProfile(
            topic="AI Agents",
            target_age_range="18-34",
            language="de",
            interests=["Automation"],
            pain_points=[AudiencePainPoint("Tool overload", 0.82, "Frustration")],
            preferred_tone="Clear",
            preferred_platforms=["YouTube"],
            summary="Creators want practical workflows.",
            generated_by="mock:mock-audience-model",
        ),
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
    }
    return Task(
        task_id="music-task-1",
        title="Music",
        description="Create a music and sound profile.",
        priority=TaskPriority.MEDIUM,
        required_capability=AgentCapability.MUSIC,
        payload=task_payload if payload is None else payload,
    )


class MusicRuntimeIntegrationTestCase(unittest.TestCase):
    """Integration tests for Pulse through HeliosRuntime."""

    def test_runtime_dispatches_music_task_to_pulse(self) -> None:
        """Runtime can dispatch MUSIC tasks to Pulse."""
        runtime = HeliosRuntime()
        pulse = MusicAgent()
        task = create_music_task()
        runtime.register(pulse)

        result = runtime.submit_task(task)

        self.assertIsInstance(result, MusicProfile)
        self.assertIs(result, task.result)
        self.assertIs(task.status, TaskStatus.COMPLETED)
        self.assertIs(pulse.last_music_profile, result)

    def test_runtime_returns_music_profile(self) -> None:
        """Runtime returns the MusicProfile from Pulse."""
        runtime = HeliosRuntime()
        runtime.register(MusicAgent())
        task = create_music_task()

        result = runtime.submit_task(task)

        self.assertIsInstance(result, MusicProfile)

    def test_runtime_propagates_pulse_errors(self) -> None:
        """Runtime propagates Pulse validation errors."""
        runtime = HeliosRuntime()
        runtime.register(MusicAgent())
        task = create_music_task({"creative_brief": "invalid"})

        with self.assertRaises(ValueError):
            runtime.submit_task(task)

        self.assertIs(task.status, TaskStatus.FAILED)


if __name__ == "__main__":
    unittest.main()
