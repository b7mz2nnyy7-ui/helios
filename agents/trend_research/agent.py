"""Atlas trend research agent."""

import re

from agents.trend_research.mock_llm_provider import MockLLMProvider
from agents.trend_research.models import TrendResult
from agents.trend_research.mock_tool import MockTrendTool
from agents.trend_research.report import TrendReport
from engine.llm.models import LLMRequest, LLMResponse
from engine.memory.base_store import BaseMemoryStore
from engine.memory.models import MemoryEntry
from engine.runtime.base_agent import BaseAgent
from engine.runtime.capability import AgentCapability
from engine.tasks.status import TaskStatus
from engine.tasks.task import Task
from engine.tools.base_tool import BaseTool
from engine.tools.llm_tool import LLMTool


class TrendResearchAgent(BaseAgent):
    """Atlas agent for trend research tasks."""

    last_result: list[TrendResult] | None
    last_report: TrendReport | None
    memory_store: BaseMemoryStore | None

    def __init__(
        self,
        tools: list[BaseTool] | None = None,
        memory_store: BaseMemoryStore | None = None,
    ) -> None:
        """Create the Atlas trend research agent."""
        super().__init__(
            agent_id="trend_research",
            name="Atlas",
            capabilities={AgentCapability.TREND_RESEARCH},
        )
        self.last_result = None
        self.last_report = None
        self.memory_store = memory_store

        for tool in self._build_tools(tools):
            self.add_tool(tool)

    def run(self, task: Task) -> TrendReport:
        """Run trend research for a task."""
        if task.required_capability is not AgentCapability.TREND_RESEARCH:
            msg = "TrendResearchAgent can only handle TREND_RESEARCH tasks."
            raise ValueError(msg)

        task.start()
        try:
            query = task.payload.get("query")
            validated_query = self._get_query(query)
            trend_tool = self.get_tool("mock_trend_tool")
            trends = self._get_trends(trend_tool.execute(query=validated_query))
            llm_request = self._create_llm_request(validated_query, trends)
            llm_tool = self.get_tool("llm")
            llm_response = self._get_llm_response(llm_tool.execute(request=llm_request))
            report = TrendReport(
                query=validated_query,
                summary=llm_response.content,
                trends=trends,
                generated_by=f"{llm_response.provider}:{llm_response.model}",
            )
            self.last_result = trends
            self.last_report = report
            self._save_report_if_configured(task, report)
            task.complete(report)
            return report
        except Exception as error:
            if task.status is TaskStatus.RUNNING:
                task.fail(str(error))
            raise

    def _build_tools(self, tools: list[BaseTool] | None) -> list[BaseTool]:
        selected_tools = list(tools or [])
        tool_ids = {tool.tool_id for tool in selected_tools}

        if "mock_trend_tool" not in tool_ids:
            selected_tools.append(MockTrendTool())

        if "llm" not in tool_ids:
            selected_tools.append(LLMTool(provider=MockLLMProvider()))

        return selected_tools

    def _get_query(self, query: object) -> str:
        if not isinstance(query, str) or not query.strip():
            msg = "query must be a non-empty string."
            raise ValueError(msg)

        return query

    def _get_trends(self, raw_result: object) -> list[TrendResult]:
        if not isinstance(raw_result, list):
            msg = "trend tool must return a list of TrendResult."
            raise ValueError(msg)

        trends: list[TrendResult] = []
        for item in raw_result:
            if not isinstance(item, TrendResult):
                msg = "trend tool must return a list of TrendResult."
                raise ValueError(msg)
            trends.append(item)

        return trends

    def _get_llm_response(self, raw_response: object) -> LLMResponse:
        if not isinstance(raw_response, LLMResponse):
            msg = "llm tool must return an LLMResponse."
            raise ValueError(msg)

        return raw_response

    def _create_llm_request(self, query: str, trends: list[TrendResult]) -> LLMRequest:
        trend_lines = [
            (
                f"- {trend.topic} | score={trend.score} | "
                f"source={trend.source} | reason={trend.reason}"
            )
            for trend in trends
        ]
        trend_summary = "\n".join(trend_lines)
        user_prompt = (
            f"Query: {query}\n\n"
            "Trend candidates:\n"
            f"{trend_summary}\n\n"
            "Erstelle einen strukturierten Trendbericht."
        )

        return LLMRequest(
            system_prompt="Atlas analysiert Trends sachlich und kopiert keine Inhalte.",
            user_prompt=user_prompt,
        )

    def _save_report_if_configured(self, task: Task, report: TrendReport) -> None:
        if self.memory_store is None:
            return

        entry = MemoryEntry(
            memory_id=f"trend-report-{self._safe_task_id(task.task_id)}",
            title=f"Trend Report: {report.query}",
            content=report.to_markdown(),
            category="trend_research",
            metadata={
                "task_id": task.task_id,
                "query": report.query,
                "generated_by": report.generated_by,
                "trend_count": len(report.trends),
                "agent_id": self.agent_id,
            },
        )
        self.memory_store.save(entry)

    def _safe_task_id(self, task_id: str) -> str:
        safe_task_id = re.sub(r"[^A-Za-z0-9_-]+", "-", task_id).strip("-")
        if not safe_task_id:
            msg = "task_id must contain at least one safe character."
            raise ValueError(msg)

        return safe_task_id
