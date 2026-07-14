"""Pulse music and sound agent."""

from agents.audience_research.models import AudienceProfile
from agents.creative_director.models import CreativeBrief
from agents.music.mock_llm_provider import MockMusicLLMProvider
from agents.music.models import MusicProfile
from agents.script.models import VideoScript
from engine.llm.models import LLMRequest, LLMResponse
from engine.runtime.base_agent import BaseAgent
from engine.runtime.capability import AgentCapability
from engine.tasks.status import TaskStatus
from engine.tasks.task import Task
from engine.tools.base_tool import BaseTool
from engine.tools.llm_tool import LLMTool


class MusicAgent(BaseAgent):
    """Pulse agent for defining music and sound concepts."""

    last_music_profile: MusicProfile | None

    def __init__(self, tools: list[BaseTool] | None = None) -> None:
        """Create the Pulse music and sound agent."""
        super().__init__(
            agent_id="music",
            name="Pulse",
            capabilities={AgentCapability.MUSIC},
        )
        self.last_music_profile = None

        for tool in self._build_tools(tools):
            self.add_tool(tool)

    def run(self, task: Task) -> MusicProfile:
        """Create a music profile from creative, audience and script data."""
        if task.required_capability is not AgentCapability.MUSIC:
            msg = "MusicAgent can only handle MUSIC tasks."
            raise ValueError(msg)

        task.start()
        try:
            creative_brief = self._get_creative_brief(
                task.payload.get("creative_brief"),
            )
            audience_profile = self._get_audience_profile(
                task.payload.get("audience_profile"),
            )
            video_script = self._get_video_script(task.payload.get("video_script"))
            llm_request = self._create_llm_request(
                creative_brief,
                audience_profile,
                video_script,
            )
            llm_tool = self.get_tool("llm")
            llm_response = self._get_llm_response(llm_tool.execute(request=llm_request))
            profile = self._create_profile(llm_response)
            self.last_music_profile = profile
            task.complete(profile)
            return profile
        except Exception as error:
            if task.status is TaskStatus.RUNNING:
                task.fail(str(error))
            raise

    def _build_tools(self, tools: list[BaseTool] | None) -> list[BaseTool]:
        selected_tools = list(tools or [])
        tool_ids = {tool.tool_id for tool in selected_tools}

        if "llm" not in tool_ids:
            selected_tools.append(LLMTool(provider=MockMusicLLMProvider()))

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

    def _get_video_script(self, value: object) -> VideoScript:
        if not isinstance(value, VideoScript):
            msg = "video_script must be a VideoScript."
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
        video_script: VideoScript,
    ) -> LLMRequest:
        interests = "\n".join(
            f"- {interest}" for interest in audience_profile.interests
        )
        return LLMRequest(
            system_prompt=(
                "Pulse entwickelt Musik- und Soundkonzepte für hochwertige "
                "Short-Form-Videos."
            ),
            user_prompt=(
                "CreativeBrief\n"
                f"music_style: {creative_brief.music_style}\n"
                f"emotional_tone: {creative_brief.emotional_tone}\n"
                f"platform_style: {creative_brief.platform_style}\n\n"
                "AudienceProfile\n"
                f"Zielgruppe: {audience_profile.topic} "
                f"({audience_profile.target_age_range})\n"
                f"Sprache: {audience_profile.language}\n"
                f"Interessen:\n{interests}\n\n"
                "VideoScript\n"
                f"Titel: {video_script.title}\n"
                f"Hook: {video_script.hook}\n"
                f"Summary: {video_script.summary}"
            ),
        )

    def _create_profile(self, llm_response: LLMResponse) -> MusicProfile:
        lines = self._response_lines(llm_response)
        return MusicProfile(
            genre=self._parse_single_value(lines, "Genre: "),
            mood=self._parse_single_value(lines, "Mood: "),
            energy_level=self._parse_single_value(lines, "EnergyLevel: "),
            tempo_bpm=int(self._parse_single_value(lines, "TempoBPM: ")),
            transition_style=self._parse_single_value(lines, "TransitionStyle: "),
            sound_effect_style=self._parse_single_value(lines, "SoundEffectStyle: "),
            intro_style=self._parse_single_value(lines, "IntroStyle: "),
            outro_style=self._parse_single_value(lines, "OutroStyle: "),
            platform_fit=self._parse_single_value(lines, "PlatformFit: "),
            copyright_strategy=self._parse_single_value(lines, "CopyrightStrategy: "),
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
