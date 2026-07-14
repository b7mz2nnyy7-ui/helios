"""Forge video production agent."""

from agents.avatar.models import AvatarProfile
from agents.creative_director.models import CreativeBrief
from agents.music.models import MusicProfile
from agents.storyboard.models import Storyboard
from agents.video_production.mock_llm_provider import MockVideoProductionLLMProvider
from agents.voice.models import VoiceProfile
from engine.llm.models import LLMRequest, LLMResponse
from engine.media.render_job import RenderJob
from engine.media.render_plan import RenderScene, VideoProductionPlan
from engine.runtime.base_agent import BaseAgent
from engine.runtime.capability import AgentCapability
from engine.tasks.status import TaskStatus
from engine.tasks.task import Task
from engine.tools.base_tool import BaseTool
from engine.tools.llm_tool import LLMTool


class VideoProductionAgent(BaseAgent):
    """Forge agent for creating provider-neutral video production plans."""

    last_render_job: RenderJob | None

    def __init__(self, tools: list[BaseTool] | None = None) -> None:
        """Create the Forge video production agent."""
        super().__init__(
            agent_id="video_production",
            name="Forge",
            capabilities={AgentCapability.VIDEO_PRODUCTION},
        )
        self.last_render_job = None

        for tool in self._build_tools(tools):
            self.add_tool(tool)

    def run(self, task: Task) -> RenderJob:
        """Create a render job from production-ready creative inputs."""
        if task.required_capability is not AgentCapability.VIDEO_PRODUCTION:
            msg = "VideoProductionAgent can only handle VIDEO_PRODUCTION tasks."
            raise ValueError(msg)

        task.start()
        try:
            storyboard = self._get_storyboard(task.payload.get("storyboard"))
            creative_brief = self._get_creative_brief(
                task.payload.get("creative_brief"),
            )
            avatar_profile = self._get_avatar_profile(
                task.payload.get("avatar_profile"),
            )
            voice_profile = self._get_voice_profile(task.payload.get("voice_profile"))
            music_profile = self._get_music_profile(task.payload.get("music_profile"))
            llm_request = self._create_llm_request(
                storyboard,
                creative_brief,
                avatar_profile,
                voice_profile,
                music_profile,
            )
            llm_tool = self.get_tool("llm")
            llm_response = self._get_llm_response(llm_tool.execute(request=llm_request))
            render_job = self._create_render_job(
                storyboard,
                creative_brief,
                avatar_profile,
                voice_profile,
                music_profile,
                llm_response,
            )
            self.last_render_job = render_job
            task.complete(render_job)
            return render_job
        except Exception as error:
            if task.status is TaskStatus.RUNNING:
                task.fail(str(error))
            raise

    def _build_tools(self, tools: list[BaseTool] | None) -> list[BaseTool]:
        selected_tools = list(tools or [])
        tool_ids = {tool.tool_id for tool in selected_tools}

        if "llm" not in tool_ids:
            selected_tools.append(LLMTool(provider=MockVideoProductionLLMProvider()))

        return selected_tools

    def _get_storyboard(self, value: object) -> Storyboard:
        if not isinstance(value, Storyboard):
            msg = "storyboard must be a Storyboard."
            raise ValueError(msg)

        return value

    def _get_creative_brief(self, value: object) -> CreativeBrief:
        if not isinstance(value, CreativeBrief):
            msg = "creative_brief must be a CreativeBrief."
            raise ValueError(msg)

        return value

    def _get_avatar_profile(self, value: object) -> AvatarProfile:
        if not isinstance(value, AvatarProfile):
            msg = "avatar_profile must be an AvatarProfile."
            raise ValueError(msg)

        return value

    def _get_voice_profile(self, value: object) -> VoiceProfile:
        if not isinstance(value, VoiceProfile):
            msg = "voice_profile must be a VoiceProfile."
            raise ValueError(msg)

        return value

    def _get_music_profile(self, value: object) -> MusicProfile:
        if not isinstance(value, MusicProfile):
            msg = "music_profile must be a MusicProfile."
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
        creative_brief: CreativeBrief,
        avatar_profile: AvatarProfile,
        voice_profile: VoiceProfile,
        music_profile: MusicProfile,
    ) -> LLMRequest:
        scenes = "\n".join(
            (
                f"- Scene {scene.scene_number}: {scene.visual_description} | "
                f"{scene.camera_direction}"
            )
            for scene in storyboard.scenes
        )
        return LLMRequest(
            system_prompt="Forge erstellt providerneutrale Produktionspläne für KI-Videos.",
            user_prompt=(
                "Storyboard\n"
                f"Title: {storyboard.title}\n"
                f"Scenes:\n{scenes}\n\n"
                "CreativeBrief\n"
                f"Visual Style: {creative_brief.visual_style}\n"
                f"Editing Style: {creative_brief.editing_style}\n"
                f"Platform Style: {creative_brief.platform_style}\n\n"
                "AvatarProfile\n"
                f"Name: {avatar_profile.name}\n"
                f"Body Language: {avatar_profile.body_language}\n\n"
                "VoiceProfile\n"
                f"Language: {voice_profile.language}\n"
                f"Speaking Style: {voice_profile.speaking_style}\n\n"
                "MusicProfile\n"
                f"Genre: {music_profile.genre}\n"
                f"Transition Style: {music_profile.transition_style}"
            ),
        )

    def _create_render_job(
        self,
        storyboard: Storyboard,
        creative_brief: CreativeBrief,
        avatar_profile: AvatarProfile,
        voice_profile: VoiceProfile,
        music_profile: MusicProfile,
        llm_response: LLMResponse,
    ) -> RenderJob:
        scenes = [
            RenderScene(
                scene_number=scene.scene_number,
                duration_seconds=scene.duration_seconds,
                camera_instruction=scene.camera_direction,
                visual_instruction=(
                    f"{scene.visual_description} "
                    f"Style: {creative_brief.visual_style}. "
                    f"Avatar: {avatar_profile.appearance}."
                ),
                voice_instruction=(
                    f"{scene.narration} Voice: {voice_profile.speaking_style}."
                ),
                music_instruction=(
                    f"{music_profile.genre}; {music_profile.transition_style}."
                ),
                transition=scene.transition,
            )
            for scene in storyboard.scenes
        ]
        plan = VideoProductionPlan(
            plan_id=f"plan-{storyboard.title.lower().replace(' ', '-')}",
            title=storyboard.title,
            target_platform=self._parse_single_value(llm_response, "TargetPlatform: "),
            scenes=scenes,
            summary=self._parse_single_value(llm_response, "Summary: "),
        )
        return RenderJob(
            job_id=f"render-{plan.plan_id}",
            plan=plan,
            provider=self._parse_single_value(llm_response, "Provider: "),
        )

    def _parse_single_value(self, llm_response: LLMResponse, prefix: str) -> str:
        for line in self._response_lines(llm_response):
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
