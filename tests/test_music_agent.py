"""Tests for the Pulse music and sound agent."""

import unittest
from typing import Any

from agents.audience_research.models import AudiencePainPoint, AudienceProfile
from agents.creative_director.models import CreativeBrief
from agents.music.agent import MusicAgent
from agents.music.mock_llm_provider import MockMusicLLMProvider
from agents.music.models import MusicProfile
from agents.script.models import ScriptSection, VideoScript
from engine.llm.base_provider import BaseLLMProvider
from engine.llm.models import LLMRequest, LLMResponse
from engine.runtime.capability import AgentCapability
from engine.tasks.priority import TaskPriority
from engine.tasks.status import TaskStatus
from engine.tasks.task import Task
from engine.tools.llm_tool import LLMTool


class RecordingMusicLLMProvider(BaseLLMProvider):
    """LLM provider that records music requests."""

    def __init__(self) -> None:
        """Create a recording provider."""
        super().__init__(provider_id="recording", model="recording-music-model")
        self.received_request: LLMRequest | None = None
        self.response = MockMusicLLMProvider(
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


class FailingMusicLLMProvider(BaseLLMProvider):
    """LLM provider that always fails."""

    def __init__(self) -> None:
        """Create a failing provider."""
        super().__init__(provider_id="failing", model="failing-music-model")

    def generate(self, request: LLMRequest) -> LLMResponse:
        """Raise a runtime error."""
        msg = "music llm failed"
        raise RuntimeError(msg)


def create_creative_brief() -> CreativeBrief:
    """Create a creative brief for music tests."""
    return CreativeBrief(
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
    )


def create_audience_profile() -> AudienceProfile:
    """Create an audience profile for music tests."""
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


def create_video_script() -> VideoScript:
    """Create a video script for music tests."""
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


def create_music_payload() -> dict[str, Any]:
    """Create a valid music payload."""
    return {
        "creative_brief": create_creative_brief(),
        "audience_profile": create_audience_profile(),
        "video_script": create_video_script(),
    }


def create_music_task(payload: dict[str, Any] | None = None) -> Task:
    """Create a music task."""
    return Task(
        task_id="music-task-1",
        title="Music",
        description="Create a music and sound profile.",
        priority=TaskPriority.MEDIUM,
        required_capability=AgentCapability.MUSIC,
        payload=create_music_payload() if payload is None else payload,
    )


class MusicAgentTestCase(unittest.TestCase):
    """Tests for MusicAgent behavior."""

    def test_agent_has_music_capability(self) -> None:
        """Pulse declares the MUSIC capability."""
        agent = MusicAgent()

        self.assertTrue(agent.can_handle(AgentCapability.MUSIC))

    def test_agent_name_is_pulse(self) -> None:
        """Pulse has the expected display name."""
        agent = MusicAgent()

        self.assertEqual(agent.name, "Pulse")

    def test_default_llm_tool_exists(self) -> None:
        """Pulse has a default LLM tool."""
        agent = MusicAgent()

        self.assertIsInstance(agent.get_tool("llm"), LLMTool)

    def test_payload_validated_and_task_completed(self) -> None:
        """Valid music inputs complete the task."""
        agent = MusicAgent()
        task = create_music_task()

        profile = agent.run(task)

        self.assertIsInstance(profile, MusicProfile)
        self.assertIs(task.status, TaskStatus.COMPLETED)

    def test_missing_creative_brief_raises_value_error(self) -> None:
        """Pulse rejects missing CreativeBrief payloads."""
        agent = MusicAgent()
        payload = create_music_payload()
        payload["creative_brief"] = "invalid"
        task = create_music_task(payload)

        with self.assertRaises(ValueError):
            agent.run(task)

    def test_missing_audience_profile_raises_value_error(self) -> None:
        """Pulse rejects missing AudienceProfile payloads."""
        agent = MusicAgent()
        payload = create_music_payload()
        payload["audience_profile"] = "invalid"
        task = create_music_task(payload)

        with self.assertRaises(ValueError):
            agent.run(task)

    def test_missing_video_script_raises_value_error(self) -> None:
        """Pulse rejects missing VideoScript payloads."""
        agent = MusicAgent()
        payload = create_music_payload()
        payload["video_script"] = "invalid"
        task = create_music_task(payload)

        with self.assertRaises(ValueError):
            agent.run(task)

    def test_task_result_and_last_music_profile_are_identical(self) -> None:
        """Pulse stores the profile and writes it to the task."""
        agent = MusicAgent()
        task = create_music_task()

        profile = agent.run(task)

        self.assertIs(task.result, profile)
        self.assertIs(agent.last_music_profile, profile)

    def test_prompt_contains_music_script_and_audience_data(self) -> None:
        """Pulse prompt contains creative, audience and script data."""
        provider = RecordingMusicLLMProvider()
        agent = MusicAgent(tools=[LLMTool(provider=provider)])
        task = create_music_task()

        agent.run(task)

        request = provider.received_request
        assert request is not None
        self.assertIn(
            "music_style: Modern pulse, restrained percussion and light synth",
            request.user_prompt,
        )
        self.assertIn("emotional_tone: Clear, focused and empowering", request.user_prompt)
        self.assertIn("platform_style: Short-form vertical video", request.user_prompt)
        self.assertIn("VideoScript", request.user_prompt)
        self.assertIn("Titel: AI Agents That Actually Save Time", request.user_prompt)
        self.assertIn("Hook: The fastest AI win", request.user_prompt)
        self.assertIn("AudienceProfile", request.user_prompt)
        self.assertIn("Zielgruppe: AI Agents", request.user_prompt)
        self.assertIn("Sprache: de", request.user_prompt)
        self.assertIn("Automation", request.user_prompt)
        self.assertEqual(
            request.system_prompt,
            "Pulse entwickelt Musik- und Soundkonzepte für hochwertige "
            "Short-Form-Videos.",
        )

    def test_runtime_values_are_complete(self) -> None:
        """Pulse creates a complete MusicProfile."""
        agent = MusicAgent()
        task = create_music_task()

        profile = agent.run(task)

        self.assertTrue(profile.genre)
        self.assertTrue(profile.mood)
        self.assertTrue(profile.energy_level)
        self.assertGreater(profile.tempo_bpm, 0)
        self.assertTrue(profile.transition_style)
        self.assertTrue(profile.sound_effect_style)
        self.assertTrue(profile.intro_style)
        self.assertTrue(profile.outro_style)
        self.assertTrue(profile.platform_fit)
        self.assertTrue(profile.copyright_strategy)
        self.assertTrue(profile.summary)
        self.assertEqual(profile.generated_by, "mock:mock-music-model")

    def test_mock_provider_is_deterministic(self) -> None:
        """MockMusicLLMProvider returns deterministic content."""
        provider = MockMusicLLMProvider()
        request = LLMRequest(system_prompt="Pulse", user_prompt="Music data")

        first_response = provider.generate(request)
        second_response = provider.generate(request)

        self.assertEqual(first_response, second_response)
        self.assertEqual(first_response.provider, "mock")
        self.assertEqual(first_response.model, "mock-music-model")

    def test_tempo_bpm_is_validated(self) -> None:
        """MusicProfile validates tempo."""
        with self.assertRaises(ValueError):
            MusicProfile(
                genre="Electronic",
                mood="Focused",
                energy_level="Medium",
                tempo_bpm=0,
                transition_style="Cuts",
                sound_effect_style="Clicks",
                intro_style="Immediate",
                outro_style="Clean",
                platform_fit="Short-form",
                copyright_strategy="Licensed",
                summary="Invalid.",
                generated_by="mock",
            )

    def test_music_profile_to_markdown(self) -> None:
        """MusicProfile can be rendered as Markdown."""
        agent = MusicAgent()
        task = create_music_task()

        profile = agent.run(task)

        markdown = profile.to_markdown()
        self.assertIn("# Music Profile", markdown)
        self.assertIn(profile.genre, markdown)
        self.assertIn(profile.summary, markdown)

    def test_llm_failure_sets_task_failed(self) -> None:
        """LLM errors move the task to FAILED."""
        agent = MusicAgent(tools=[LLMTool(provider=FailingMusicLLMProvider())])
        task = create_music_task()

        with self.assertRaises(RuntimeError):
            agent.run(task)

        self.assertIs(task.status, TaskStatus.FAILED)
        self.assertEqual(task.error_message, "music llm failed")

    def test_errors_are_propagated(self) -> None:
        """LLM errors are propagated unchanged."""
        agent = MusicAgent(tools=[LLMTool(provider=FailingMusicLLMProvider())])
        task = create_music_task()

        with self.assertRaisesRegex(RuntimeError, "music llm failed"):
            agent.run(task)


if __name__ == "__main__":
    unittest.main()
