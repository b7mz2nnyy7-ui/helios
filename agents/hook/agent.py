"""Apollo hook agent."""

from agents.hook.mock_llm_provider import MockHookLLMProvider
from agents.hook.models import HookCandidate, OptimizedHook
from agents.script.models import VideoScript
from engine.llm.models import LLMRequest, LLMResponse
from engine.runtime.base_agent import BaseAgent
from engine.runtime.capability import AgentCapability
from engine.tasks.status import TaskStatus
from engine.tasks.task import Task
from engine.tools.base_tool import BaseTool
from engine.tools.llm_tool import LLMTool


class HookAgent(BaseAgent):
    """Apollo agent for optimizing video hooks."""

    last_hook: OptimizedHook | None

    def __init__(self, tools: list[BaseTool] | None = None) -> None:
        """Create the Apollo hook agent."""
        super().__init__(
            agent_id="hook",
            name="Apollo",
            capabilities={AgentCapability.HOOK},
        )
        self.last_hook = None

        for tool in self._build_tools(tools):
            self.add_tool(tool)

    def run(self, task: Task) -> OptimizedHook:
        """Optimize the hook for a video script task."""
        if task.required_capability is not AgentCapability.HOOK:
            msg = "HookAgent can only handle HOOK tasks."
            raise ValueError(msg)

        task.start()
        try:
            video_script = self._get_video_script(task.payload.get("video_script"))
            llm_request = self._create_llm_request(video_script)
            llm_tool = self.get_tool("llm")
            llm_response = self._get_llm_response(llm_tool.execute(request=llm_request))
            candidates = self._parse_candidates(llm_response)
            selected_hook = max(candidates, key=lambda candidate: candidate.score)
            optimized_hook = OptimizedHook(
                original_hook=video_script.hook,
                selected_hook=selected_hook,
                candidates=candidates,
                summary=self._parse_summary(llm_response),
                generated_by=f"{llm_response.provider}:{llm_response.model}",
            )
            self.last_hook = optimized_hook
            task.complete(optimized_hook)
            return optimized_hook
        except Exception as error:
            if task.status is TaskStatus.RUNNING:
                task.fail(str(error))
            raise

    def _build_tools(self, tools: list[BaseTool] | None) -> list[BaseTool]:
        selected_tools = list(tools or [])
        tool_ids = {tool.tool_id for tool in selected_tools}

        if "llm" not in tool_ids:
            selected_tools.append(LLMTool(provider=MockHookLLMProvider()))

        return selected_tools

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

    def _create_llm_request(self, video_script: VideoScript) -> LLMRequest:
        sections = "\n".join(
            f"- {section.title}: {section.content}"
            for section in video_script.sections
        )
        return LLMRequest(
            system_prompt=(
                "Apollo optimiert ausschließlich Hooks für maximale Aufmerksamkeit."
            ),
            user_prompt=(
                f"Script Title: {video_script.title}\n"
                f"Original Hook: {video_script.hook}\n"
                f"Summary: {video_script.summary}\n\n"
                f"Script Sections:\n{sections}"
            ),
        )

    def _parse_summary(self, llm_response: LLMResponse) -> str:
        for line in self._response_lines(llm_response):
            if line.startswith("Summary: "):
                return line.removeprefix("Summary: ")

        msg = "LLM response must contain a Summary line."
        raise ValueError(msg)

    def _parse_candidates(self, llm_response: LLMResponse) -> list[HookCandidate]:
        candidates: list[HookCandidate] = []
        for line in self._response_lines(llm_response):
            if not line.startswith("Hook: "):
                continue

            parts = [part.strip() for part in line.removeprefix("Hook: ").split("|")]
            if len(parts) != 3:
                msg = "LLM hook lines must contain text, score and reason."
                raise ValueError(msg)

            candidates.append(
                HookCandidate(
                    text=parts[0],
                    score=float(parts[1]),
                    reason=parts[2],
                ),
            )

        if len(candidates) < 10:
            msg = "LLM response must contain at least 10 hook candidates."
            raise ValueError(msg)

        return candidates

    def _response_lines(self, llm_response: LLMResponse) -> list[str]:
        return [
            line.strip()
            for line in llm_response.content.splitlines()
            if line.strip()
        ]
