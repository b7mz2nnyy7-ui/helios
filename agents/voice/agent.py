"""Vox voice agent."""

from agents.avatar.models import AvatarProfile
from agents.creative_director.models import CreativeBrief
from agents.script.models import VideoScript
from agents.voice.mock_llm_provider import MockVoiceLLMProvider
from agents.voice.models import VoiceProfile
from engine.llm.models import LLMRequest, LLMResponse
from engine.runtime.base_agent import BaseAgent
from engine.runtime.capability import AgentCapability
from engine.tasks.status import TaskStatus
from engine.tasks.task import Task
from engine.tools.base_tool import BaseTool
from engine.tools.llm_tool import LLMTool


class VoiceAgent(BaseAgent):
    """Vox agent for defining voice profiles for video scripts."""

    last_voice_profile: VoiceProfile | None

    def __init__(self, tools: list[BaseTool] | None = None) -> None:
        """Create the Vox voice agent."""
        super().__init__(
            agent_id="voice",
            name="Vox",
            capabilities={AgentCapability.VOICE},
        )
        self.last_voice_profile = None

        for tool in self._build_tools(tools):
            self.add_tool(tool)

    def run(self, task: Task) -> VoiceProfile:
        """Create a voice profile from script, avatar and creative brief data."""
        if task.required_capability is not AgentCapability.VOICE:
            msg = "VoiceAgent can only handle VOICE tasks."
            raise ValueError(msg)

        task.start()
        try:
            video_script = self._get_video_script(task.payload.get("video_script"))
            avatar_profile = self._get_avatar_profile(
                task.payload.get("avatar_profile"),
            )
            creative_brief = self._get_creative_brief(
                task.payload.get("creative_brief"),
            )
            language = self._get_language(task.payload.get("language"))
            llm_request = self._create_llm_request(
                video_script,
                avatar_profile,
                creative_brief,
                language,
            )
            llm_tool = self.get_tool("llm")
            llm_response = self._get_llm_response(llm_tool.execute(request=llm_request))
            profile = self._create_profile(language, llm_response)
            self.last_voice_profile = profile
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
            selected_tools.append(LLMTool(provider=MockVoiceLLMProvider()))

        return selected_tools

    def _get_video_script(self, value: object) -> VideoScript:
        if not isinstance(value, VideoScript):
            msg = "video_script must be a VideoScript."
            raise ValueError(msg)

        return value

    def _get_avatar_profile(self, value: object) -> AvatarProfile:
        if not isinstance(value, AvatarProfile):
            msg = "avatar_profile must be an AvatarProfile."
            raise ValueError(msg)

        return value

    def _get_creative_brief(self, value: object) -> CreativeBrief:
        if not isinstance(value, CreativeBrief):
            msg = "creative_brief must be a CreativeBrief."
            raise ValueError(msg)

        return value

    def _get_language(self, value: object) -> str:
        if value is None:
            return "de"

        if not isinstance(value, str) or not value.strip():
            msg = "language must be a non-empty string."
            raise ValueError(msg)

        return value.strip()

    def _get_llm_response(self, raw_response: object) -> LLMResponse:
        if not isinstance(raw_response, LLMResponse):
            msg = "llm tool must return an LLMResponse."
            raise ValueError(msg)

        return raw_response

    def _create_llm_request(
        self,
        video_script: VideoScript,
        avatar_profile: AvatarProfile,
        creative_brief: CreativeBrief,
        language: str,
    ) -> LLMRequest:
        sections = "\n".join(
            f"- {section.title}: {section.content}"
            for section in video_script.sections
        )
        return LLMRequest(
            system_prompt=(
                "Vox definiert konsistente Stimmen für hochwertige "
                "Social-Media-Videos."
            ),
            user_prompt=(
                "VideoScript\n"
                f"title: {video_script.title}\n"
                f"hook: {video_script.hook}\n"
                f"sections:\n{sections}\n"
                f"call_to_action: {video_script.call_to_action}\n\n"
                "AvatarProfile\n"
                f"voice_style: {avatar_profile.voice_style}\n"
                f"energy_level: {avatar_profile.energy_level}\n"
                f"age_group: {avatar_profile.age_group}\n"
                f"platform_fit: {avatar_profile.platform_fit}\n\n"
                "CreativeBrief\n"
                f"emotional_tone: {creative_brief.emotional_tone}\n"
                f"music_style: {creative_brief.music_style}\n"
                f"platform_style: {creative_brief.platform_style}\n"
                f"branding_notes: {creative_brief.branding_notes}\n\n"
                f"Gewünschte Sprache: {language}"
            ),
        )

    def _create_profile(self, language: str, llm_response: LLMResponse) -> VoiceProfile:
        lines = self._response_lines(llm_response)
        return VoiceProfile(
            language=language,
            voice_character=self._parse_single_value(lines, "VoiceCharacter: "),
            speaking_style=self._parse_single_value(lines, "SpeakingStyle: "),
            emotional_tone=self._parse_single_value(lines, "EmotionalTone: "),
            pace_words_per_minute=int(self._parse_single_value(lines, "PaceWPM: ")),
            pitch=self._parse_single_value(lines, "Pitch: "),
            emphasis_notes=self._parse_single_value(lines, "EmphasisNotes: "),
            pronunciation_notes=self._parse_single_value(lines, "PronunciationNotes: "),
            multilingual_notes=self._parse_single_value(lines, "MultilingualNotes: "),
            platform_fit=self._parse_single_value(lines, "PlatformFit: "),
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
