"""Orion script agent."""

from typing import TypeVar

from agents.audience_research.models import AudienceProfile
from agents.knowledge.models import KnowledgeResponse
from agents.script.mock_llm_provider import MockScriptLLMProvider
from agents.script.models import ScriptSection, VideoScript
from agents.strategy.models import ContentStrategy
from agents.trend_research.report import TrendReport
from engine.llm.models import LLMRequest, LLMResponse
from engine.runtime.base_agent import BaseAgent
from engine.runtime.capability import AgentCapability
from engine.tasks.status import TaskStatus
from engine.tasks.task import Task
from engine.tools.base_tool import BaseTool
from engine.tools.llm_tool import LLMTool


ModelT = TypeVar("ModelT")


class ScriptAgent(BaseAgent):
    """Orion agent for writing scripts from multi-agent results."""

    last_script: VideoScript | None

    def __init__(self, tools: list[BaseTool] | None = None) -> None:
        """Create the Orion script agent."""
        super().__init__(
            agent_id="script",
            name="Orion",
            capabilities={AgentCapability.SCRIPT},
        )
        self.last_script = None

        for tool in self._build_tools(tools):
            self.add_tool(tool)

    def run(self, task: Task) -> VideoScript:
        """Create a video script from trend, audience, knowledge and strategy data."""
        if task.required_capability is not AgentCapability.SCRIPT:
            msg = "ScriptAgent can only handle SCRIPT tasks."
            raise ValueError(msg)

        task.start()
        try:
            trend_report = self._get_model(
                task.payload.get("trend_report"),
                TrendReport,
                "trend_report",
            )
            audience_profile = self._get_model(
                task.payload.get("audience_profile"),
                AudienceProfile,
                "audience_profile",
            )
            knowledge_response = self._get_model(
                task.payload.get("knowledge_response"),
                KnowledgeResponse,
                "knowledge_response",
            )
            content_strategy = self._get_model(
                task.payload.get("content_strategy"),
                ContentStrategy,
                "content_strategy",
            )
            llm_request = self._create_llm_request(
                trend_report,
                audience_profile,
                knowledge_response,
                content_strategy,
            )
            llm_tool = self.get_tool("llm")
            llm_response = self._get_llm_response(llm_tool.execute(request=llm_request))
            script = self._create_script(llm_response)
            self.last_script = script
            task.complete(script)
            return script
        except Exception as error:
            if task.status is TaskStatus.RUNNING:
                task.fail(str(error))
            raise

    def _build_tools(self, tools: list[BaseTool] | None) -> list[BaseTool]:
        selected_tools = list(tools or [])
        tool_ids = {tool.tool_id for tool in selected_tools}

        if "llm" not in tool_ids:
            selected_tools.append(LLMTool(provider=MockScriptLLMProvider()))

        return selected_tools

    def _get_model(
        self,
        value: object,
        model_type: type[ModelT],
        field_name: str,
    ) -> ModelT:
        if not isinstance(value, model_type):
            msg = f"{field_name} must be a {model_type.__name__}."
            raise ValueError(msg)

        return value

    def _get_llm_response(self, raw_response: object) -> LLMResponse:
        if not isinstance(raw_response, LLMResponse):
            msg = "llm tool must return an LLMResponse."
            raise ValueError(msg)

        return raw_response

    def _create_llm_request(
        self,
        trend_report: TrendReport,
        audience_profile: AudienceProfile,
        knowledge_response: KnowledgeResponse,
        content_strategy: ContentStrategy,
    ) -> LLMRequest:
        trend_topics = "\n".join(f"- {trend.topic}" for trend in trend_report.trends)
        interests = "\n".join(
            f"- {interest}" for interest in audience_profile.interests
        )
        pain_points = "\n".join(
            f"- {point.problem}: {point.emotional_driver}"
            for point in audience_profile.pain_points
        )
        knowledge_items = "\n".join(
            f"- {item.title} ({item.category.value})"
            for item in knowledge_response.items
        )
        content_ideas = "\n".join(
            f"- {idea.title}: {idea.angle}" for idea in content_strategy.ideas
        )

        return LLMRequest(
            system_prompt=(
                "Orion schreibt hochwertige Social-Media-Skripte auf Basis "
                "aller Unternehmensdaten."
            ),
            user_prompt=(
                "TrendReport\n"
                f"Query: {trend_report.query}\n"
                f"Summary: {trend_report.summary}\n"
                f"Topics:\n{trend_topics}\n\n"
                "AudienceProfile\n"
                f"Zielgruppe: {audience_profile.topic} "
                f"({audience_profile.target_age_range})\n"
                f"Sprache: {audience_profile.language}\n"
                f"Interessen:\n{interests}\n"
                f"Probleme:\n{pain_points}\n\n"
                "KnowledgeResponse\n"
                f"KnowledgeItems:\n{knowledge_items}\n\n"
                "ContentStrategy\n"
                f"Zusammenfassung: {content_strategy.summary}\n"
                f"Content-Ideen:\n{content_ideas}"
            ),
        )

    def _create_script(self, llm_response: LLMResponse) -> VideoScript:
        lines = [
            line.strip()
            for line in llm_response.content.splitlines()
            if line.strip()
        ]
        sections = self._parse_sections(lines)
        if len(sections) < 3:
            msg = "LLM response must contain at least 3 script sections."
            raise ValueError(msg)

        return VideoScript(
            title=self._parse_single_value(lines, "Title: "),
            hook=self._parse_single_value(lines, "Hook: "),
            sections=sections,
            call_to_action=self._parse_single_value(lines, "CTA: "),
            summary=self._parse_single_value(lines, "Summary: "),
            generated_by=f"{llm_response.provider}:{llm_response.model}",
        )

    def _parse_single_value(self, lines: list[str], prefix: str) -> str:
        for line in lines:
            if line.startswith(prefix):
                return line.removeprefix(prefix)

        msg = f"LLM response must contain a {prefix.strip()} line."
        raise ValueError(msg)

    def _parse_sections(self, lines: list[str]) -> list[ScriptSection]:
        sections: list[ScriptSection] = []
        for line in lines:
            if not line.startswith("Section: "):
                continue

            parts = [part.strip() for part in line.removeprefix("Section: ").split("|")]
            if len(parts) != 2:
                msg = "LLM section lines must contain title and content."
                raise ValueError(msg)

            sections.append(ScriptSection(title=parts[0], content=parts[1]))

        return sections
