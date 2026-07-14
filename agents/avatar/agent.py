"""Echo avatar agent."""

from agents.audience_research.models import AudienceProfile
from agents.avatar.mock_llm_provider import MockAvatarLLMProvider
from agents.avatar.models import AvatarProfile
from agents.creative_director.models import CreativeBrief
from engine.llm.models import LLMRequest, LLMResponse
from engine.runtime.base_agent import BaseAgent
from engine.runtime.capability import AgentCapability
from engine.tasks.status import TaskStatus
from engine.tasks.task import Task
from engine.tools.base_tool import BaseTool
from engine.tools.llm_tool import LLMTool


class AvatarAgent(BaseAgent):
    """Echo agent for defining consistent AI avatar profiles."""

    last_avatar: AvatarProfile | None

    def __init__(self, tools: list[BaseTool] | None = None) -> None:
        """Create the Echo avatar agent."""
        super().__init__(
            agent_id="avatar",
            name="Echo",
            capabilities={AgentCapability.AVATAR},
        )
        self.last_avatar = None

        for tool in self._build_tools(tools):
            self.add_tool(tool)

    def run(self, task: Task) -> AvatarProfile:
        """Create an avatar profile from a creative brief and audience profile."""
        if task.required_capability is not AgentCapability.AVATAR:
            msg = "AvatarAgent can only handle AVATAR tasks."
            raise ValueError(msg)

        task.start()
        try:
            creative_brief = self._get_creative_brief(
                task.payload.get("creative_brief"),
            )
            audience_profile = self._get_audience_profile(
                task.payload.get("audience_profile"),
            )
            llm_request = self._create_llm_request(creative_brief, audience_profile)
            llm_tool = self.get_tool("llm")
            llm_response = self._get_llm_response(llm_tool.execute(request=llm_request))
            avatar = self._create_avatar(llm_response)
            self.last_avatar = avatar
            task.complete(avatar)
            return avatar
        except Exception as error:
            if task.status is TaskStatus.RUNNING:
                task.fail(str(error))
            raise

    def _build_tools(self, tools: list[BaseTool] | None) -> list[BaseTool]:
        selected_tools = list(tools or [])
        tool_ids = {tool.tool_id for tool in selected_tools}

        if "llm" not in tool_ids:
            selected_tools.append(LLMTool(provider=MockAvatarLLMProvider()))

        return selected_tools

    def _get_creative_brief(self, value: object) -> CreativeBrief:
        if not isinstance(value, CreativeBrief):
            msg = "creative_brief must be a CreativeBrief."
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
        creative_brief: CreativeBrief,
        audience_profile: AudienceProfile,
    ) -> LLMRequest:
        interests = "\n".join(
            f"- {interest}" for interest in audience_profile.interests
        )
        pain_points = "\n".join(
            f"- {point.problem}: {point.emotional_driver}"
            for point in audience_profile.pain_points
        )
        return LLMRequest(
            system_prompt=(
                "Echo entwickelt konsistente KI-Avatare für hochwertige "
                "Social-Media-Marken."
            ),
            user_prompt=(
                "CreativeBrief\n"
                f"visual_style: {creative_brief.visual_style}\n"
                f"avatar_style: {creative_brief.avatar_style}\n"
                f"emotional_tone: {creative_brief.emotional_tone}\n"
                f"branding_notes: {creative_brief.branding_notes}\n\n"
                "AudienceProfile\n"
                f"Zielgruppe: {audience_profile.topic} "
                f"({audience_profile.target_age_range})\n"
                f"Sprache: {audience_profile.language}\n"
                f"Interessen:\n{interests}\n"
                f"Probleme:\n{pain_points}"
            ),
        )

    def _create_avatar(self, llm_response: LLMResponse) -> AvatarProfile:
        lines = self._response_lines(llm_response)
        return AvatarProfile(
            name=self._parse_single_value(lines, "Name: "),
            age_group=self._parse_single_value(lines, "AgeGroup: "),
            appearance=self._parse_single_value(lines, "Appearance: "),
            clothing_style=self._parse_single_value(lines, "ClothingStyle: "),
            hairstyle=self._parse_single_value(lines, "Hairstyle: "),
            facial_expression=self._parse_single_value(lines, "FacialExpression: "),
            body_language=self._parse_single_value(lines, "BodyLanguage: "),
            voice_style=self._parse_single_value(lines, "VoiceStyle: "),
            energy_level=self._parse_single_value(lines, "EnergyLevel: "),
            platform_fit=self._parse_single_value(lines, "PlatformFit: "),
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
