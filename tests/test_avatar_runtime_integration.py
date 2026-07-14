"""Runtime integration tests for Echo avatar agent."""

import unittest

from agents.audience_research.models import AudiencePainPoint, AudienceProfile
from agents.avatar.agent import AvatarAgent
from agents.avatar.models import AvatarProfile
from agents.creative_director.models import CreativeBrief
from engine.runtime.capability import AgentCapability
from engine.runtime.runtime import HeliosRuntime
from engine.tasks.priority import TaskPriority
from engine.tasks.status import TaskStatus
from engine.tasks.task import Task


def create_avatar_task(payload: dict[str, object] | None = None) -> Task:
    """Create an avatar task for runtime integration tests."""
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
            music_style="Modern pulse",
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
    }
    return Task(
        task_id="avatar-task-1",
        title="Avatar",
        description="Create an avatar profile.",
        priority=TaskPriority.MEDIUM,
        required_capability=AgentCapability.AVATAR,
        payload=task_payload if payload is None else payload,
    )


class AvatarRuntimeIntegrationTestCase(unittest.TestCase):
    """Integration tests for Echo through HeliosRuntime."""

    def test_runtime_dispatches_avatar_task_to_echo(self) -> None:
        """Runtime can dispatch AVATAR tasks to Echo."""
        runtime = HeliosRuntime()
        echo = AvatarAgent()
        task = create_avatar_task()
        runtime.register(echo)

        result = runtime.submit_task(task)

        self.assertIsInstance(result, AvatarProfile)
        self.assertIs(result, task.result)
        self.assertIs(task.status, TaskStatus.COMPLETED)
        self.assertIs(echo.last_avatar, result)

    def test_runtime_returns_avatar_profile(self) -> None:
        """Runtime returns the AvatarProfile from Echo."""
        runtime = HeliosRuntime()
        runtime.register(AvatarAgent())
        task = create_avatar_task()

        result = runtime.submit_task(task)

        self.assertIsInstance(result, AvatarProfile)

    def test_runtime_propagates_echo_errors(self) -> None:
        """Runtime propagates Echo validation errors."""
        runtime = HeliosRuntime()
        runtime.register(AvatarAgent())
        task = create_avatar_task({"creative_brief": "invalid"})

        with self.assertRaises(ValueError):
            runtime.submit_task(task)

        self.assertIs(task.status, TaskStatus.FAILED)


if __name__ == "__main__":
    unittest.main()
