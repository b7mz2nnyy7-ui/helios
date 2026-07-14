"""Lumen storyboard agent."""

from agents.hook.models import OptimizedHook
from agents.script.models import VideoScript
from agents.storyboard.mock_llm_provider import MockStoryboardLLMProvider
from agents.storyboard.models import Storyboard, StoryboardScene
from engine.llm.models import LLMRequest, LLMResponse
from engine.runtime.base_agent import BaseAgent
from engine.runtime.capability import AgentCapability
from engine.tasks.status import TaskStatus
from engine.tasks.task import Task
from engine.tools.base_tool import BaseTool
from engine.tools.llm_tool import LLMTool


class StoryboardAgent(BaseAgent):
    """Lumen agent for creating short-form video storyboards."""

    last_storyboard: Storyboard | None

    def __init__(self, tools: list[BaseTool] | None = None) -> None:
        """Create the Lumen storyboard agent."""
        super().__init__(
            agent_id="storyboard",
            name="Lumen",
            capabilities={AgentCapability.STORYBOARD},
        )
        self.last_storyboard = None

        for tool in self._build_tools(tools):
            self.add_tool(tool)

    def run(self, task: Task) -> Storyboard:
        """Create a storyboard from a video script and optimized hook."""
        if task.required_capability is not AgentCapability.STORYBOARD:
            msg = "StoryboardAgent can only handle STORYBOARD tasks."
            raise ValueError(msg)

        task.start()
        try:
            video_script = self._get_video_script(task.payload.get("video_script"))
            optimized_hook = self._get_optimized_hook(
                task.payload.get("optimized_hook"),
            )
            target_duration_seconds = self._get_target_duration(
                task.payload.get("target_duration_seconds"),
            )
            llm_request = self._create_llm_request(
                video_script,
                optimized_hook,
                target_duration_seconds,
            )
            llm_tool = self.get_tool("llm")
            llm_response = self._get_llm_response(llm_tool.execute(request=llm_request))
            storyboard = self._create_storyboard(optimized_hook, llm_response)
            self.last_storyboard = storyboard
            task.complete(storyboard)
            return storyboard
        except Exception as error:
            if task.status is TaskStatus.RUNNING:
                task.fail(str(error))
            raise

    def _build_tools(self, tools: list[BaseTool] | None) -> list[BaseTool]:
        selected_tools = list(tools or [])
        tool_ids = {tool.tool_id for tool in selected_tools}

        if "llm" not in tool_ids:
            selected_tools.append(LLMTool(provider=MockStoryboardLLMProvider()))

        return selected_tools

    def _get_video_script(self, value: object) -> VideoScript:
        if not isinstance(value, VideoScript):
            msg = "video_script must be a VideoScript."
            raise ValueError(msg)

        return value

    def _get_optimized_hook(self, value: object) -> OptimizedHook:
        if not isinstance(value, OptimizedHook):
            msg = "optimized_hook must be an OptimizedHook."
            raise ValueError(msg)

        return value

    def _get_target_duration(self, value: object) -> float:
        if value is None:
            return 30.0

        if not isinstance(value, int | float) or value <= 0:
            msg = "target_duration_seconds must be greater than 0."
            raise ValueError(msg)

        return float(value)

    def _get_llm_response(self, raw_response: object) -> LLMResponse:
        if not isinstance(raw_response, LLMResponse):
            msg = "llm tool must return an LLMResponse."
            raise ValueError(msg)

        return raw_response

    def _create_llm_request(
        self,
        video_script: VideoScript,
        optimized_hook: OptimizedHook,
        target_duration_seconds: float,
    ) -> LLMRequest:
        sections = "\n".join(
            f"- {section.title}: {section.content}"
            for section in video_script.sections
        )
        return LLMRequest(
            system_prompt=(
                "Lumen erstellt präzise Storyboards für Short-Form-Videos."
            ),
            user_prompt=(
                f"Script-Titel: {video_script.title}\n"
                f"Ausgewählter Hook: {optimized_hook.selected_hook.text}\n"
                f"ScriptSections:\n{sections}\n"
                f"Call to Action: {video_script.call_to_action}\n"
                f"Zieldauer: {target_duration_seconds}s\n\n"
                "Erstelle Szenen mit Kamera, Visuals, Text und Übergängen."
            ),
        )

    def _create_storyboard(
        self,
        optimized_hook: OptimizedHook,
        llm_response: LLMResponse,
    ) -> Storyboard:
        lines = self._response_lines(llm_response)
        return Storyboard(
            title=self._parse_single_value(lines, "Title: "),
            selected_hook=optimized_hook.selected_hook.text,
            scenes=self._parse_scenes(lines),
            visual_style=self._parse_single_value(lines, "Style: "),
            summary=self._parse_single_value(lines, "Summary: "),
            generated_by=f"{llm_response.provider}:{llm_response.model}",
        )

    def _parse_single_value(self, lines: list[str], prefix: str) -> str:
        for line in lines:
            if line.startswith(prefix):
                return line.removeprefix(prefix)

        msg = f"LLM response must contain a {prefix.strip()} line."
        raise ValueError(msg)

    def _parse_scenes(self, lines: list[str]) -> list[StoryboardScene]:
        scenes: list[StoryboardScene] = []
        for line in lines:
            if not line.startswith("Scene: "):
                continue

            parts = [part.strip() for part in line.removeprefix("Scene: ").split("|")]
            if len(parts) != 7:
                msg = "LLM scene lines must contain seven fields."
                raise ValueError(msg)

            on_screen_text = parts[5] if parts[5] else None
            scenes.append(
                StoryboardScene(
                    scene_number=int(parts[0]),
                    duration_seconds=float(parts[1]),
                    narration=parts[2],
                    visual_description=parts[3],
                    camera_direction=parts[4],
                    on_screen_text=on_screen_text,
                    transition=parts[6],
                ),
            )

        return scenes

    def _response_lines(self, llm_response: LLMResponse) -> list[str]:
        return [
            line.strip()
            for line in llm_response.content.splitlines()
            if line.strip()
        ]
