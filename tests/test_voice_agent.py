"""Tests for the Vox voice agent."""

import unittest
from typing import Any

from agents.avatar.models import AvatarProfile
from agents.creative_director.models import CreativeBrief
from agents.script.models import ScriptSection, VideoScript
from agents.voice.agent import VoiceAgent
from agents.voice.mock_llm_provider import MockVoiceLLMProvider
from agents.voice.models import VoiceProfile
from engine.llm.base_provider import BaseLLMProvider
from engine.llm.models import LLMRequest, LLMResponse
from engine.runtime.capability import AgentCapability
from engine.tasks.priority import TaskPriority
from engine.tasks.status import TaskStatus
from engine.tasks.task import Task
from engine.tools.llm_tool import LLMTool


class RecordingVoiceLLMProvider(BaseLLMProvider):
    """LLM provider that records voice requests."""

    def __init__(self) -> None:
        """Create a recording provider."""
        super().__init__(provider_id="recording", model="recording-voice-model")
        self.received_request: LLMRequest | None = None
        self.response = MockVoiceLLMProvider(
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


class FailingVoiceLLMProvider(BaseLLMProvider):
    """LLM provider that always fails."""

    def __init__(self) -> None:
        """Create a failing provider."""
        super().__init__(provider_id="failing", model="failing-voice-model")

    def generate(self, request: LLMRequest) -> LLMResponse:
        """Raise a runtime error."""
        msg = "voice llm failed"
        raise RuntimeError(msg)


def create_video_script() -> VideoScript:
    """Create a video script for voice tests."""
    return VideoScript(
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
    )


def create_avatar_profile() -> AvatarProfile:
    """Create an avatar profile for voice tests."""
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


def create_creative_brief() -> CreativeBrief:
    """Create a creative brief for voice tests."""
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


def create_voice_payload() -> dict[str, Any]:
    """Create a valid voice payload."""
    return {
        "video_script": create_video_script(),
        "avatar_profile": create_avatar_profile(),
        "creative_brief": create_creative_brief(),
    }


def create_voice_task(payload: dict[str, Any] | None = None) -> Task:
    """Create a voice task."""
    return Task(
        task_id="voice-task-1",
        title="Voice",
        description="Create a voice profile.",
        priority=TaskPriority.MEDIUM,
        required_capability=AgentCapability.VOICE,
        payload=create_voice_payload() if payload is None else payload,
    )


class VoiceAgentTestCase(unittest.TestCase):
    """Tests for VoiceAgent behavior."""

    def test_agent_has_voice_capability(self) -> None:
        """Vox declares the VOICE capability."""
        agent = VoiceAgent()

        self.assertTrue(agent.can_handle(AgentCapability.VOICE))

    def test_agent_name_is_vox(self) -> None:
        """Vox has the expected display name."""
        agent = VoiceAgent()

        self.assertEqual(agent.name, "Vox")

    def test_default_llm_tool_exists(self) -> None:
        """Vox has a default LLM tool."""
        agent = VoiceAgent()

        self.assertIsInstance(agent.get_tool("llm"), LLMTool)

    def test_valid_inputs_complete_task(self) -> None:
        """Valid voice inputs complete the task."""
        agent = VoiceAgent()
        task = create_voice_task()

        profile = agent.run(task)

        self.assertIsInstance(profile, VoiceProfile)
        self.assertIs(task.status, TaskStatus.COMPLETED)

    def test_missing_video_script_raises_value_error(self) -> None:
        """Vox rejects missing VideoScript payloads."""
        agent = VoiceAgent()
        payload = create_voice_payload()
        payload["video_script"] = "invalid"
        task = create_voice_task(payload)

        with self.assertRaises(ValueError):
            agent.run(task)

    def test_missing_avatar_profile_raises_value_error(self) -> None:
        """Vox rejects missing AvatarProfile payloads."""
        agent = VoiceAgent()
        payload = create_voice_payload()
        payload["avatar_profile"] = "invalid"
        task = create_voice_task(payload)

        with self.assertRaises(ValueError):
            agent.run(task)

    def test_missing_creative_brief_raises_value_error(self) -> None:
        """Vox rejects missing CreativeBrief payloads."""
        agent = VoiceAgent()
        payload = create_voice_payload()
        payload["creative_brief"] = "invalid"
        task = create_voice_task(payload)

        with self.assertRaises(ValueError):
            agent.run(task)

    def test_empty_language_raises_value_error(self) -> None:
        """Vox rejects empty language values."""
        agent = VoiceAgent()
        payload = create_voice_payload()
        payload["language"] = ""
        task = create_voice_task(payload)

        with self.assertRaises(ValueError):
            agent.run(task)

    def test_default_language_works(self) -> None:
        """Vox defaults language to German."""
        agent = VoiceAgent()
        task = create_voice_task()

        profile = agent.run(task)

        self.assertEqual(profile.language, "de")

    def test_prompt_contains_script_avatar_and_creative_data(self) -> None:
        """Vox prompt contains script, avatar and creative data."""
        provider = RecordingVoiceLLMProvider()
        agent = VoiceAgent(tools=[LLMTool(provider=provider)])
        payload = create_voice_payload()
        payload["language"] = "en"
        task = create_voice_task(payload)

        agent.run(task)

        request = provider.received_request
        assert request is not None
        self.assertIn("title: AI Agents That Actually Save Time", request.user_prompt)
        self.assertIn("hook: The fastest AI win", request.user_prompt)
        self.assertIn("Problem", request.user_prompt)
        self.assertIn("call_to_action: Pick one recurring content task.", request.user_prompt)
        self.assertIn("voice_style: Clear, grounded and practical", request.user_prompt)
        self.assertIn("energy_level: Medium-high", request.user_prompt)
        self.assertIn("age_group: 28-35", request.user_prompt)
        self.assertIn("platform_fit: Short-form vertical explainers", request.user_prompt)
        self.assertIn("emotional_tone: Clear, focused and empowering", request.user_prompt)
        self.assertIn("music_style: Modern pulse", request.user_prompt)
        self.assertIn("platform_style: Short-form vertical video", request.user_prompt)
        self.assertIn("branding_notes: Use practical proof and avoid hype", request.user_prompt)
        self.assertIn("Gewünschte Sprache: en", request.user_prompt)

    def test_pace_words_per_minute_is_validated(self) -> None:
        """VoiceProfile validates speaking pace."""
        with self.assertRaises(ValueError):
            VoiceProfile(
                language="de",
                voice_character="Calm",
                speaking_style="Clear",
                emotional_tone="Focused",
                pace_words_per_minute=0,
                pitch="Medium",
                emphasis_notes="Emphasize key words.",
                pronunciation_notes="Crisp.",
                multilingual_notes="Keep common English terms.",
                platform_fit="Short-form.",
                summary="Invalid.",
                generated_by="mock",
            )

    def test_last_voice_profile_and_task_result_are_identical(self) -> None:
        """Vox stores the profile and writes it to the task."""
        agent = VoiceAgent()
        task = create_voice_task()

        profile = agent.run(task)

        self.assertIs(task.result, profile)
        self.assertIs(agent.last_voice_profile, profile)

    def test_mock_provider_is_deterministic(self) -> None:
        """MockVoiceLLMProvider returns deterministic content."""
        provider = MockVoiceLLMProvider()
        request = LLMRequest(system_prompt="Vox", user_prompt="Voice data")

        first_response = provider.generate(request)
        second_response = provider.generate(request)

        self.assertEqual(first_response, second_response)
        self.assertEqual(first_response.provider, "mock")
        self.assertEqual(first_response.model, "mock-voice-model")

    def test_voice_profile_to_markdown(self) -> None:
        """VoiceProfile can be rendered as Markdown."""
        agent = VoiceAgent()
        task = create_voice_task()

        profile = agent.run(task)

        markdown = profile.to_markdown()
        self.assertIn("# Voice Profile", markdown)
        self.assertIn(profile.voice_character, markdown)
        self.assertIn(profile.summary, markdown)

    def test_llm_failure_sets_task_failed(self) -> None:
        """LLM errors move the task to FAILED."""
        agent = VoiceAgent(tools=[LLMTool(provider=FailingVoiceLLMProvider())])
        task = create_voice_task()

        with self.assertRaises(RuntimeError):
            agent.run(task)

        self.assertIs(task.status, TaskStatus.FAILED)
        self.assertEqual(task.error_message, "voice llm failed")

    def test_errors_are_propagated(self) -> None:
        """LLM errors are propagated unchanged."""
        agent = VoiceAgent(tools=[LLMTool(provider=FailingVoiceLLMProvider())])
        task = create_voice_task()

        with self.assertRaisesRegex(RuntimeError, "voice llm failed"):
            agent.run(task)


if __name__ == "__main__":
    unittest.main()
