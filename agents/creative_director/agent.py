"""Aether creative director agent."""

from agents.audience_research.models import AudienceProfile
from agents.creative_director.mock_llm_provider import MockCreativeLLMProvider
from agents.creative_director.models import CreativeBrief
from agents.storyboard.models import Storyboard
from agents.strategy.models import ContentStrategy
from engine.llm.models import LLMRequest, LLMResponse
from engine.runtime.base_agent import BaseAgent
from engine.runtime.capability import AgentCapability
from engine.tasks.status import TaskStatus
from engine.tasks.task import Task
from engine.tools.base_tool import BaseTool
from engine.tools.llm_tool import LLMTool


class CreativeDirectorAgent(BaseAgent):
    """Aether agent for creating production-ready creative briefs."""

    last_brief: CreativeBrief | None

    def __init__(self, tools: list[BaseTool] | None = None) -> None:
        """Create the Aether creative director agent."""
        super().__init__(
            agent_id="creative_director",
            name="Aether",
            capabilities={AgentCapability.CREATIVE_DIRECTION},
        )
        self.last_brief = None

        for tool in self._build_tools(tools):
            self.add_tool(tool)

    def run(self, task: Task) -> CreativeBrief:
        """Create a creative brief from storyboard, strategy and audience data."""
        if task.required_capability is not AgentCapability.CREATIVE_DIRECTION:
            msg = "CreativeDirectorAgent can only handle CREATIVE_DIRECTION tasks."
            raise ValueError(msg)

        task.start()
        try:
            storyboard = self._get_storyboard(task.payload.get("storyboard"))
            content_strategy = self._get_content_strategy(
                task.payload.get("content_strategy"),
            )
            audience_profile = self._get_audience_profile(
                task.payload.get("audience_profile"),
            )
            llm_request = self._create_llm_request(
                storyboard,
                content_strategy,
                audience_profile,
            )
            llm_tool = self.get_tool("llm")
            llm_response = self._get_llm_response(llm_tool.execute(request=llm_request))
            brief = self._create_brief(llm_response)
            self.last_brief = brief
            task.complete(brief)
            return brief
        except Exception as error:
            if task.status is TaskStatus.RUNNING:
                task.fail(str(error))
            raise

    def _build_tools(self, tools: list[BaseTool] | None) -> list[BaseTool]:
        selected_tools = list(tools or [])
        tool_ids = {tool.tool_id for tool in selected_tools}

        if "llm" not in tool_ids:
            selected_tools.append(LLMTool(provider=MockCreativeLLMProvider()))

        return selected_tools

    def _get_storyboard(self, value: object) -> Storyboard:
        if not isinstance(value, Storyboard):
            msg = "storyboard must be a Storyboard."
            raise ValueError(msg)

        return value

    def _get_content_strategy(self, value: object) -> ContentStrategy:
        if not isinstance(value, ContentStrategy):
            msg = "content_strategy must be a ContentStrategy."
            raise ValueError(msg)

        return value

    def _get_audience_profile(self, value: object) -> AudienceProfile:
        if not isinstance(value, AudienceProfile):
            msg = "audience_profile must be an AudienceProfile."
            raise ValueError(msg)

        return value

    def _get_llm_response(self, raw_response: object) -> LLMResponse:
        if not isinstance(raw_response, LLMResponse):
            msg = "llm tool must return an LLMResponse."
            raise ValueError(msg)

        return raw_response

    def _create_llm_request(
        self,
        storyboard: Storyboard,
        content_strategy: ContentStrategy,
        audience_profile: AudienceProfile,
    ) -> LLMRequest:
        scenes = "\n".join(
            (
                f"- Scene {scene.scene_number}: {scene.visual_description} | "
                f"{scene.camera_direction}"
            )
            for scene in storyboard.scenes
        )
        ideas = "\n".join(
            f"- {idea.title}: {idea.angle}" for idea in content_strategy.ideas
        )
        interests = "\n".join(
            f"- {interest}" for interest in audience_profile.interests
        )
        return LLMRequest(
            system_prompt=(
                "Aether entwickelt den visuellen Markenstil für hochwertige "
                "Social-Media-Inhalte."
            ),
            user_prompt=(
                "Storyboard\n"
                f"Titel: {storyboard.title}\n"
                f"Szenen und Visuals:\n{scenes}\n\n"
                "ContentStrategy\n"
                f"Zusammenfassung: {content_strategy.summary}\n"
                f"Ideen:\n{ideas}\n\n"
                "AudienceProfile\n"
                f"Zielgruppe: {audience_profile.topic} "
                f"({audience_profile.target_age_range})\n"
                f"Sprache: {audience_profile.language}\n"
                f"Interessen:\n{interests}"
            ),
        )

    def _create_brief(self, llm_response: LLMResponse) -> CreativeBrief:
        lines = self._response_lines(llm_response)
        return CreativeBrief(
            visual_style=self._parse_single_value(lines, "VisualStyle: "),
            color_palette=self._parse_single_value(lines, "ColorPalette: "),
            typography=self._parse_single_value(lines, "Typography: "),
            camera_style=self._parse_single_value(lines, "CameraStyle: "),
            lighting_style=self._parse_single_value(lines, "LightingStyle: "),
            animation_style=self._parse_single_value(lines, "AnimationStyle: "),
            avatar_style=self._parse_single_value(lines, "AvatarStyle: "),
            editing_style=self._parse_single_value(lines, "EditingStyle: "),
            music_style=self._parse_single_value(lines, "MusicStyle: "),
            emotional_tone=self._parse_single_value(lines, "EmotionalTone: "),
            platform_style=self._parse_single_value(lines, "PlatformStyle: "),
            branding_notes=self._parse_single_value(lines, "BrandingNotes: "),
            summary=self._parse_single_value(lines, "Summary: "),
            generated_by=f"{llm_response.provider}:{llm_response.model}",
        )

    def _parse_single_value(self, lines: list[str], prefix: str) -> str:
        for line in lines:
            if line.startswith(prefix):
                return line.removeprefix(prefix)

        msg = f"LLM response must contain a {prefix.strip()} line."
        raise ValueError(msg)

    def _response_lines(self, llm_response: LLMResponse) -> list[str]:
        return [
            line.strip()
            for line in llm_response.content.splitlines()
            if line.strip()
        ]
