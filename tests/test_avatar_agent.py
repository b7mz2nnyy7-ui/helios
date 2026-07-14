"""Tests for the Echo avatar agent."""

import unittest
from typing import Any

from agents.audience_research.models import AudiencePainPoint, AudienceProfile
from agents.avatar.agent import AvatarAgent
from agents.avatar.mock_llm_provider import MockAvatarLLMProvider
from agents.avatar.models import AvatarProfile
from agents.creative_director.models import CreativeBrief
from engine.llm.base_provider import BaseLLMProvider
from engine.llm.models import LLMRequest, LLMResponse
from engine.runtime.capability import AgentCapability
from engine.tasks.priority import TaskPriority
from engine.tasks.status import TaskStatus
from engine.tasks.task import Task
from engine.tools.llm_tool import LLMTool


class RecordingAvatarLLMProvider(BaseLLMProvider):
    """LLM provider that records avatar requests."""

    def __init__(self) -> None:
        """Create a recording provider."""
        super().__init__(provider_id="recording", model="recording-avatar-model")
        self.received_request: LLMRequest | None = None
        self.response = MockAvatarLLMProvider(
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


class FailingAvatarLLMProvider(BaseLLMProvider):
    """LLM provider that always fails."""

    def __init__(self) -> None:
        """Create a failing provider."""
        super().__init__(provider_id="failing", model="failing-avatar-model")

    def generate(self, request: LLMRequest) -> LLMResponse:
        """Raise a runtime error."""
        msg = "avatar llm failed"
        raise RuntimeError(msg)


def create_creative_brief() -> CreativeBrief:
    """Create a creative brief for avatar tests."""
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


def create_audience_profile() -> AudienceProfile:
    """Create an audience profile for avatar tests."""
    return AudienceProfile(
        topic="AI Agents",
        target_age_range="18-34",
        language="de",
        interests=["Automation", "Creator productivity"],
        pain_points=[AudiencePainPoint("Tool overload", 0.82, "Frustration")],
        preferred_tone="Clear",
        preferred_platforms=["YouTube"],
        summary="Creators want practical workflows.",
        generated_by="mock:mock-audience-model",
    )


def create_avatar_payload() -> dict[str, Any]:
    """Create a valid avatar payload."""
    return {
        "creative_brief": create_creative_brief(),
        "audience_profile": create_audience_profile(),
    }


def create_avatar_task(payload: dict[str, Any] | None = None) -> Task:
    """Create an avatar task."""
    return Task(
        task_id="avatar-task-1",
        title="Avatar",
        description="Create an avatar profile.",
        priority=TaskPriority.MEDIUM,
        required_capability=AgentCapability.AVATAR,
        payload=create_avatar_payload() if payload is None else payload,
    )


class AvatarAgentTestCase(unittest.TestCase):
    """Tests for AvatarAgent behavior."""

    def test_agent_has_avatar_capability(self) -> None:
        """Echo declares the AVATAR capability."""
        agent = AvatarAgent()

        self.assertTrue(agent.can_handle(AgentCapability.AVATAR))

    def test_agent_name_is_echo(self) -> None:
        """Echo has the expected display name."""
        agent = AvatarAgent()

        self.assertEqual(agent.name, "Echo")

    def test_default_llm_tool_exists(self) -> None:
        """Echo has a default LLM tool."""
        agent = AvatarAgent()

        self.assertIsInstance(agent.get_tool("llm"), LLMTool)

    def test_payload_validated_and_task_completed(self) -> None:
        """Valid avatar inputs complete the task."""
        agent = AvatarAgent()
        task = create_avatar_task()

        profile = agent.run(task)

        self.assertIsInstance(profile, AvatarProfile)
        self.assertIs(task.status, TaskStatus.COMPLETED)

    def test_missing_creative_brief_raises_value_error(self) -> None:
        """Echo rejects missing CreativeBrief payloads."""
        agent = AvatarAgent()
        payload = create_avatar_payload()
        payload["creative_brief"] = "invalid"
        task = create_avatar_task(payload)

        with self.assertRaises(ValueError):
            agent.run(task)

    def test_missing_audience_profile_raises_value_error(self) -> None:
        """Echo rejects missing AudienceProfile payloads."""
        agent = AvatarAgent()
        payload = create_avatar_payload()
        payload["audience_profile"] = "invalid"
        task = create_avatar_task(payload)

        with self.assertRaises(ValueError):
            agent.run(task)

    def test_task_result_and_last_avatar_are_identical(self) -> None:
        """Echo stores the avatar and writes it to the task."""
        agent = AvatarAgent()
        task = create_avatar_task()

        profile = agent.run(task)

        self.assertIs(task.result, profile)
        self.assertIs(agent.last_avatar, profile)

    def test_prompt_contains_creative_and_audience_data(self) -> None:
        """Echo prompt contains creative brief and audience profile data."""
        provider = RecordingAvatarLLMProvider()
        agent = AvatarAgent(tools=[LLMTool(provider=provider)])
        task = create_avatar_task()

        agent.run(task)

        request = provider.received_request
        assert request is not None
        self.assertIn("visual_style: Clean kinetic tech editorial", request.user_prompt)
        self.assertIn(
            "avatar_style: Confident operator, practical and calm",
            request.user_prompt,
        )
        self.assertIn(
            "emotional_tone: Clear, focused and empowering",
            request.user_prompt,
        )
        self.assertIn("AudienceProfile", request.user_prompt)
        self.assertIn("Zielgruppe: AI Agents", request.user_prompt)
        self.assertIn("Sprache: de", request.user_prompt)
        self.assertIn("Automation", request.user_prompt)
        self.assertIn("Tool overload", request.user_prompt)
        self.assertEqual(
            request.system_prompt,
            "Echo entwickelt konsistente KI-Avatare für hochwertige "
            "Social-Media-Marken.",
        )

    def test_mock_provider_is_deterministic(self) -> None:
        """MockAvatarLLMProvider returns deterministic content."""
        provider = MockAvatarLLMProvider()
        request = LLMRequest(system_prompt="Echo", user_prompt="Avatar data")

        first_response = provider.generate(request)
        second_response = provider.generate(request)

        self.assertEqual(first_response, second_response)
        self.assertEqual(first_response.provider, "mock")
        self.assertEqual(first_response.model, "mock-avatar-model")

    def test_avatar_profile_contains_required_fields(self) -> None:
        """Echo creates a complete AvatarProfile."""
        agent = AvatarAgent()
        task = create_avatar_task()

        profile = agent.run(task)

        self.assertTrue(profile.name)
        self.assertTrue(profile.age_group)
        self.assertTrue(profile.appearance)
        self.assertTrue(profile.clothing_style)
        self.assertTrue(profile.hairstyle)
        self.assertTrue(profile.facial_expression)
        self.assertTrue(profile.body_language)
        self.assertTrue(profile.voice_style)
        self.assertTrue(profile.energy_level)
        self.assertTrue(profile.platform_fit)
        self.assertTrue(profile.branding_notes)
        self.assertTrue(profile.summary)
        self.assertEqual(profile.generated_by, "mock:mock-avatar-model")

    def test_avatar_to_markdown(self) -> None:
        """AvatarProfile can be rendered as Markdown."""
        agent = AvatarAgent()
        task = create_avatar_task()

        profile = agent.run(task)

        markdown = profile.to_markdown()
        self.assertIn("# Avatar Profile: Echo", markdown)
        self.assertIn(profile.appearance, markdown)
        self.assertIn(profile.summary, markdown)

    def test_llm_failure_sets_task_failed(self) -> None:
        """LLM errors move the task to FAILED."""
        agent = AvatarAgent(tools=[LLMTool(provider=FailingAvatarLLMProvider())])
        task = create_avatar_task()

        with self.assertRaises(RuntimeError):
            agent.run(task)

        self.assertIs(task.status, TaskStatus.FAILED)
        self.assertEqual(task.error_message, "avatar llm failed")

    def test_errors_are_propagated(self) -> None:
        """LLM errors are propagated unchanged."""
        agent = AvatarAgent(tools=[LLMTool(provider=FailingAvatarLLMProvider())])
        task = create_avatar_task()

        with self.assertRaisesRegex(RuntimeError, "avatar llm failed"):
            agent.run(task)


if __name__ == "__main__":
    unittest.main()
