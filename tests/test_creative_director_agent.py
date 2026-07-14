"""Tests for the Aether creative director agent."""

import unittest
from typing import Any

from agents.audience_research.models import AudiencePainPoint, AudienceProfile
from agents.creative_director.agent import CreativeDirectorAgent
from agents.creative_director.mock_llm_provider import MockCreativeLLMProvider
from agents.creative_director.models import CreativeBrief
from agents.storyboard.models import Storyboard, StoryboardScene
from agents.strategy.models import ContentIdea, ContentStrategy
from engine.llm.base_provider import BaseLLMProvider
from engine.llm.models import LLMRequest, LLMResponse
from engine.runtime.capability import AgentCapability
from engine.tasks.priority import TaskPriority
from engine.tasks.status import TaskStatus
from engine.tasks.task import Task
from engine.tools.llm_tool import LLMTool


class RecordingCreativeLLMProvider(BaseLLMProvider):
    """LLM provider that records creative direction requests."""

    def __init__(self) -> None:
        """Create a recording provider."""
        super().__init__(provider_id="recording", model="recording-creative-model")
        self.received_request: LLMRequest | None = None
        self.response = MockCreativeLLMProvider(
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


class FailingCreativeLLMProvider(BaseLLMProvider):
    """LLM provider that always fails."""

    def __init__(self) -> None:
        """Create a failing provider."""
        super().__init__(provider_id="failing", model="failing-creative-model")

    def generate(self, request: LLMRequest) -> LLMResponse:
        """Raise a runtime error."""
        msg = "creative llm failed"
        raise RuntimeError(msg)


def create_storyboard() -> Storyboard:
    """Create a storyboard for creative direction tests."""
    return Storyboard(
        title="AI Agents Workflow Storyboard",
        selected_hook="The fastest AI win is a workflow you stop repeating.",
        scenes=[
            StoryboardScene(
                1,
                6.0,
                "Open with the hook.",
                "Creator at desk surrounded by tool tabs.",
                "Fast push-in.",
                "Stop repeating this task",
                "Smash cut",
            ),
            StoryboardScene(
                2,
                8.0,
                "Show manual work.",
                "Split screen of planning and publishing.",
                "Side-by-side tracking shot.",
                "The old workflow",
                "Match cut",
            ),
            StoryboardScene(
                3,
                8.0,
                "Introduce the system.",
                "Node diagram connecting inputs and output.",
                "Slow zoom.",
                "Build one useful loop",
                "Swipe",
            ),
        ],
        visual_style="Clean kinetic captions",
        summary="Storyboard for practical AI workflow content.",
        generated_by="mock:mock-storyboard-model",
    )


def create_content_strategy() -> ContentStrategy:
    """Create a content strategy for creative direction tests."""
    return ContentStrategy(
        query="AI Agents",
        summary="Make practical AI workflows easy to understand.",
        ideas=[
            ContentIdea(
                "Workflow Demo",
                "Practical implementation",
                "YouTube",
                "Shows repeatable workflows.",
            ),
        ],
        generated_by="mock:mock-strategy-model",
    )


def create_audience_profile() -> AudienceProfile:
    """Create an audience profile for creative direction tests."""
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


def create_creative_payload() -> dict[str, Any]:
    """Create a valid creative direction payload."""
    return {
        "storyboard": create_storyboard(),
        "content_strategy": create_content_strategy(),
        "audience_profile": create_audience_profile(),
    }


def create_creative_task(payload: dict[str, Any] | None = None) -> Task:
    """Create a creative direction task."""
    return Task(
        task_id="creative-task-1",
        title="Creative Direction",
        description="Create a creative production brief.",
        priority=TaskPriority.MEDIUM,
        required_capability=AgentCapability.CREATIVE_DIRECTION,
        payload=create_creative_payload() if payload is None else payload,
    )


class CreativeDirectorAgentTestCase(unittest.TestCase):
    """Tests for CreativeDirectorAgent behavior."""

    def test_agent_has_creative_direction_capability(self) -> None:
        """Aether declares the CREATIVE_DIRECTION capability."""
        agent = CreativeDirectorAgent()

        self.assertTrue(agent.can_handle(AgentCapability.CREATIVE_DIRECTION))

    def test_agent_name_is_aether(self) -> None:
        """Aether has the expected display name."""
        agent = CreativeDirectorAgent()

        self.assertEqual(agent.name, "Aether")

    def test_default_llm_tool_exists(self) -> None:
        """Aether has a default LLM tool."""
        agent = CreativeDirectorAgent()

        self.assertIsInstance(agent.get_tool("llm"), LLMTool)

    def test_valid_payload_completes_task(self) -> None:
        """Valid creative direction inputs complete the task."""
        agent = CreativeDirectorAgent()
        task = create_creative_task()

        brief = agent.run(task)

        self.assertIsInstance(brief, CreativeBrief)
        self.assertIs(task.status, TaskStatus.COMPLETED)

    def test_missing_models_raise_value_error(self) -> None:
        """Aether rejects payloads missing required models."""
        required_fields = ["storyboard", "content_strategy", "audience_profile"]
        for field in required_fields:
            with self.subTest(field=field):
                payload = create_creative_payload()
                payload[field] = "invalid"
                agent = CreativeDirectorAgent()
                task = create_creative_task(payload)

                with self.assertRaises(ValueError):
                    agent.run(task)

    def test_task_result_and_last_brief_are_identical(self) -> None:
        """Aether stores the brief and writes it to the task."""
        agent = CreativeDirectorAgent()
        task = create_creative_task()

        brief = agent.run(task)

        self.assertIs(task.result, brief)
        self.assertIs(agent.last_brief, brief)

    def test_prompt_contains_storyboard_audience_and_strategy(self) -> None:
        """Aether prompt contains storyboard, audience and strategy data."""
        provider = RecordingCreativeLLMProvider()
        agent = CreativeDirectorAgent(tools=[LLMTool(provider=provider)])
        task = create_creative_task()

        agent.run(task)

        request = provider.received_request
        assert request is not None
        self.assertIn("Storyboard", request.user_prompt)
        self.assertIn("AI Agents Workflow Storyboard", request.user_prompt)
        self.assertIn("Creator at desk surrounded by tool tabs.", request.user_prompt)
        self.assertIn("ContentStrategy", request.user_prompt)
        self.assertIn("Make practical AI workflows easy to understand.", request.user_prompt)
        self.assertIn("AudienceProfile", request.user_prompt)
        self.assertIn("Zielgruppe: AI Agents", request.user_prompt)
        self.assertIn("Automation", request.user_prompt)
        self.assertIn("Sprache: de", request.user_prompt)
        self.assertEqual(
            request.system_prompt,
            "Aether entwickelt den visuellen Markenstil für hochwertige "
            "Social-Media-Inhalte.",
        )

    def test_mock_provider_is_deterministic(self) -> None:
        """MockCreativeLLMProvider returns deterministic content."""
        provider = MockCreativeLLMProvider()
        request = LLMRequest(system_prompt="Aether", user_prompt="Creative data")

        first_response = provider.generate(request)
        second_response = provider.generate(request)

        self.assertEqual(first_response, second_response)
        self.assertEqual(first_response.provider, "mock")
        self.assertEqual(first_response.model, "mock-creative-model")

    def test_brief_contains_required_fields(self) -> None:
        """Aether creates a complete CreativeBrief."""
        agent = CreativeDirectorAgent()
        task = create_creative_task()

        brief = agent.run(task)

        self.assertTrue(brief.visual_style)
        self.assertTrue(brief.color_palette)
        self.assertTrue(brief.typography)
        self.assertTrue(brief.camera_style)
        self.assertTrue(brief.lighting_style)
        self.assertTrue(brief.animation_style)
        self.assertTrue(brief.avatar_style)
        self.assertTrue(brief.editing_style)
        self.assertTrue(brief.music_style)
        self.assertTrue(brief.emotional_tone)
        self.assertTrue(brief.platform_style)
        self.assertTrue(brief.branding_notes)
        self.assertTrue(brief.summary)
        self.assertEqual(brief.generated_by, "mock:mock-creative-model")

    def test_brief_to_markdown(self) -> None:
        """CreativeBrief can be rendered as Markdown."""
        agent = CreativeDirectorAgent()
        task = create_creative_task()

        brief = agent.run(task)

        markdown = brief.to_markdown()
        self.assertIn("# Creative Brief", markdown)
        self.assertIn(brief.visual_style, markdown)
        self.assertIn(brief.summary, markdown)

    def test_llm_failure_sets_task_failed(self) -> None:
        """LLM errors move the task to FAILED."""
        agent = CreativeDirectorAgent(
            tools=[LLMTool(provider=FailingCreativeLLMProvider())],
        )
        task = create_creative_task()

        with self.assertRaises(RuntimeError):
            agent.run(task)

        self.assertIs(task.status, TaskStatus.FAILED)
        self.assertEqual(task.error_message, "creative llm failed")

    def test_errors_are_propagated(self) -> None:
        """LLM errors are propagated unchanged."""
        agent = CreativeDirectorAgent(
            tools=[LLMTool(provider=FailingCreativeLLMProvider())],
        )
        task = create_creative_task()

        with self.assertRaisesRegex(RuntimeError, "creative llm failed"):
            agent.run(task)


if __name__ == "__main__":
    unittest.main()
