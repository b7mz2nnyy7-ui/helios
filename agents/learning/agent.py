"""Mentor learning agent."""

from agents.analytics.models import AnalyticsReport
from agents.learning.mock_llm_provider import MockLearningLLMProvider
from agents.learning.models import LearningInsight, LearningReport
from engine.llm.models import LLMRequest, LLMResponse
from engine.runtime.base_agent import BaseAgent
from engine.runtime.capability import AgentCapability
from engine.tasks.status import TaskStatus
from engine.tasks.task import Task
from engine.tools.base_tool import BaseTool
from engine.tools.llm_tool import LLMTool


class LearningAgent(BaseAgent):
    """Mentor agent for deriving learnings from analytics reports."""

    last_learning_report: LearningReport | None

    def __init__(self, tools: list[BaseTool] | None = None) -> None:
        """Create the Mentor learning agent."""
        super().__init__(
            agent_id="learning",
            name="Mentor",
            capabilities={AgentCapability.LEARNING},
        )
        self.last_learning_report = None

        for tool in self._build_tools(tools):
            self.add_tool(tool)

    def run(self, task: Task) -> LearningReport:
        """Create a learning report from an analytics report."""
        if task.required_capability is not AgentCapability.LEARNING:
            msg = "LearningAgent can only handle LEARNING tasks."
            raise ValueError(msg)

        task.start()
        try:
            analytics_report = self._get_analytics_report(
                task.payload.get("analytics_report"),
            )
            llm_request = self._create_llm_request(analytics_report)
            llm_tool = self.get_tool("llm")
            llm_response = self._get_llm_response(llm_tool.execute(request=llm_request))
            report = self._create_learning_report(analytics_report, llm_response)
            self.last_learning_report = report
            task.complete(report)
            return report
        except Exception as error:
            if task.status is TaskStatus.RUNNING:
                task.fail(str(error))
            raise

    def _build_tools(self, tools: list[BaseTool] | None) -> list[BaseTool]:
        selected_tools = list(tools or [])
        tool_ids = {tool.tool_id for tool in selected_tools}

        if "llm" not in tool_ids:
            selected_tools.append(LLMTool(provider=MockLearningLLMProvider()))

        return selected_tools

    def _get_analytics_report(self, value: object) -> AnalyticsReport:
        if not isinstance(value, AnalyticsReport):
            msg = "analytics_report must be an AnalyticsReport."
            raise ValueError(msg)

        return value

    def _get_llm_response(self, raw_response: object) -> LLMResponse:
        if not isinstance(raw_response, LLMResponse):
            msg = "llm tool must return an LLMResponse."
            raise ValueError(msg)

        return raw_response

    def _create_llm_request(self, analytics_report: AnalyticsReport) -> LLMRequest:
        metrics = "\n".join(
            (
                f"- {metric.platform}: views={metric.views}, "
                f"watch_percentage={metric.average_watch_percentage}, "
                f"ctr={metric.ctr}, engagement_rate={metric.engagement_rate}, "
                f"shares={metric.shares}, saves={metric.saves}"
            )
            for metric in analytics_report.metrics
        )
        return LLMRequest(
            system_prompt=(
                "Mentor analysiert Content-Performance und leitet belastbare "
                "Learnings und Experimente ab."
            ),
            user_prompt=(
                f"Video ID: {analytics_report.video_id}\n"
                f"Gesamtviews: {analytics_report.total_views}\n"
                f"Gesamtengagement: {analytics_report.total_engagement}\n"
                f"Stärkste Plattform: {analytics_report.strongest_platform}\n"
                f"Schwächste Plattform: {analytics_report.weakest_platform}\n\n"
                f"PlatformMetrics:\n{metrics}"
            ),
        )

    def _create_learning_report(
        self,
        analytics_report: AnalyticsReport,
        llm_response: LLMResponse,
    ) -> LearningReport:
        lines = self._response_lines(llm_response)
        return LearningReport(
            video_id=analytics_report.video_id,
            performance_summary=self._parse_single_value(
                lines,
                "PerformanceSummary: ",
            ),
            strengths=self._parse_insights(lines, "Strength: "),
            weaknesses=self._parse_insights(lines, "Weakness: "),
            experiments=self._parse_prefixed_values(lines, "Experiment: "),
            recommended_actions=self._parse_prefixed_values(lines, "Action: "),
            generated_by=f"{llm_response.provider}:{llm_response.model}",
        )

    def _parse_single_value(self, lines: list[str], prefix: str) -> str:
        for line in lines:
            if line.startswith(prefix):
                return line.removeprefix(prefix)

        msg = f"LLM response must contain a {prefix.strip()} line."
        raise ValueError(msg)

    def _parse_prefixed_values(self, lines: list[str], prefix: str) -> list[str]:
        values = [
            line.removeprefix(prefix)
            for line in lines
            if line.startswith(prefix)
        ]
        if not values:
            msg = f"LLM response must contain at least one {prefix.strip()} line."
            raise ValueError(msg)

        return values

    def _parse_insights(self, lines: list[str], prefix: str) -> list[LearningInsight]:
        insights: list[LearningInsight] = []
        for line in lines:
            if not line.startswith(prefix):
                continue

            parts = [part.strip() for part in line.removeprefix(prefix).split("|")]
            if len(parts) != 5:
                msg = "Learning insight lines must contain five fields."
                raise ValueError(msg)

            insights.append(
                LearningInsight(
                    category=parts[0],
                    observation=parts[1],
                    evidence=parts[2],
                    recommendation=parts[3],
                    confidence=float(parts[4]),
                ),
            )

        return insights

    def _response_lines(self, llm_response: LLMResponse) -> list[str]:
        return [
            line.strip()
            for line in llm_response.content.splitlines()
            if line.strip()
        ]
