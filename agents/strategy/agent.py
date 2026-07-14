"""Nova strategy agent."""

from agents.strategy.mock_llm_provider import MockStrategyLLMProvider
from agents.strategy.models import ContentIdea, ContentStrategy
from agents.trend_research.report import TrendReport
from engine.llm.models import LLMRequest, LLMResponse
from engine.runtime.base_agent import BaseAgent
from engine.runtime.capability import AgentCapability
from engine.tasks.status import TaskStatus
from engine.tasks.task import Task
from engine.tools.base_tool import BaseTool
from engine.tools.llm_tool import LLMTool


class StrategyAgent(BaseAgent):
    """Nova agent for turning trend reports into content strategy."""

    last_strategy: ContentStrategy | None

    def __init__(self, tools: list[BaseTool] | None = None) -> None:
        """Create the Nova strategy agent."""
        super().__init__(
            agent_id="strategy",
            name="Nova",
            capabilities={AgentCapability.STRATEGY},
        )
        self.last_strategy = None

        for tool in self._build_tools(tools):
            self.add_tool(tool)

    def run(self, task: Task) -> ContentStrategy:
        """Create a content strategy from a trend report task."""
        if task.required_capability is not AgentCapability.STRATEGY:
            msg = "StrategyAgent can only handle STRATEGY tasks."
            raise ValueError(msg)

        task.start()
        try:
            trend_report = self._get_trend_report(task.payload.get("trend_report"))
            llm_request = self._create_llm_request(trend_report)
            llm_tool = self.get_tool("llm")
            llm_response = self._get_llm_response(llm_tool.execute(request=llm_request))
            strategy = self._create_strategy(trend_report, llm_response)
            self.last_strategy = strategy
            task.complete(strategy)
            return strategy
        except Exception as error:
            if task.status is TaskStatus.RUNNING:
                task.fail(str(error))
            raise

    def _build_tools(self, tools: list[BaseTool] | None) -> list[BaseTool]:
        selected_tools = list(tools or [])
        tool_ids = {tool.tool_id for tool in selected_tools}

        if "llm" not in tool_ids:
            selected_tools.append(LLMTool(provider=MockStrategyLLMProvider()))

        return selected_tools

    def _get_trend_report(self, trend_report: object) -> TrendReport:
        if not isinstance(trend_report, TrendReport):
            msg = "trend_report must be a TrendReport."
            raise ValueError(msg)

        return trend_report

    def _get_llm_response(self, raw_response: object) -> LLMResponse:
        if not isinstance(raw_response, LLMResponse):
            msg = "llm tool must return an LLMResponse."
            raise ValueError(msg)

        return raw_response

    def _create_llm_request(self, trend_report: TrendReport) -> LLMRequest:
        trend_lines = [
            f"- {trend.topic} | score={trend.score}" for trend in trend_report.trends
        ]
        trend_summary = "\n".join(trend_lines)
        return LLMRequest(
            system_prompt=(
                "Nova erstellt skalierbare Content-Strategien "
                "für Social-Media-Unternehmen."
            ),
            user_prompt=(
                f"Query: {trend_report.query}\n\n"
                f"Trend Summary: {trend_report.summary}\n\n"
                "Trend Topics and Scores:\n"
                f"{trend_summary}\n\n"
                "Erstelle eine strukturierte Content-Strategie."
            ),
        )

    def _create_strategy(
        self,
        trend_report: TrendReport,
        llm_response: LLMResponse,
    ) -> ContentStrategy:
        lines = [
            line.strip()
            for line in llm_response.content.splitlines()
            if line.strip()
        ]
        summary = self._parse_summary(lines)
        ideas = self._parse_ideas(lines)
        return ContentStrategy(
            query=trend_report.query,
            summary=summary,
            ideas=ideas,
            generated_by=f"{llm_response.provider}:{llm_response.model}",
        )

    def _parse_summary(self, lines: list[str]) -> str:
        for line in lines:
            if line.startswith("Summary: "):
                return line.removeprefix("Summary: ")

        msg = "LLM response must contain a Summary line."
        raise ValueError(msg)

    def _parse_ideas(self, lines: list[str]) -> list[ContentIdea]:
        ideas: list[ContentIdea] = []
        for line in lines:
            if not line.startswith("Idea: "):
                continue

            parts = [part.strip() for part in line.removeprefix("Idea: ").split("|")]
            if len(parts) != 4:
                msg = "LLM idea lines must contain title, angle, platform and reason."
                raise ValueError(msg)

            ideas.append(
                ContentIdea(
                    title=parts[0],
                    angle=parts[1],
                    target_platform=parts[2],
                    reason=parts[3],
                ),
            )

        if len(ideas) != 5:
            msg = "LLM response must contain exactly 5 content ideas."
            raise ValueError(msg)

        return ideas
