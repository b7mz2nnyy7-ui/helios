"""Athena business intelligence agent."""

from agents.analytics.models import AnalyticsReport
from agents.business_intelligence.mock_llm_provider import MockBusinessLLMProvider
from agents.business_intelligence.models import (
    BusinessIntelligenceReport,
    BusinessKPI,
    BusinessOpportunity,
    BusinessRisk,
    BusinessRiskSeverity,
)
from agents.learning.models import LearningReport
from agents.prediction.models import PredictionReport
from engine.llm.models import LLMRequest, LLMResponse
from engine.runtime.base_agent import BaseAgent
from engine.runtime.capability import AgentCapability
from engine.tasks.status import TaskStatus
from engine.tasks.task import Task
from engine.tools.base_tool import BaseTool
from engine.tools.llm_tool import LLMTool


class BusinessIntelligenceAgent(BaseAgent):
    """Athena agent for creating CEO-level business intelligence reports."""

    last_report: BusinessIntelligenceReport | None

    def __init__(self, tools: list[BaseTool] | None = None) -> None:
        """Create the Athena business intelligence agent."""
        super().__init__(
            agent_id="business_intelligence",
            name="Athena",
            capabilities={AgentCapability.BUSINESS_INTELLIGENCE},
        )
        self.last_report = None

        for tool in self._build_tools(tools):
            self.add_tool(tool)

    def run(self, task: Task) -> BusinessIntelligenceReport:
        """Create a business intelligence report from operational reports."""
        if task.required_capability is not AgentCapability.BUSINESS_INTELLIGENCE:
            msg = (
                "BusinessIntelligenceAgent can only handle "
                "BUSINESS_INTELLIGENCE tasks."
            )
            raise ValueError(msg)

        task.start()
        try:
            analytics_report = self._get_analytics_report(
                task.payload.get("analytics_report"),
            )
            learning_report = self._get_learning_report(
                task.payload.get("learning_report"),
            )
            prediction_report = self._get_prediction_report(
                task.payload.get("prediction_report"),
            )
            llm_request = self._create_llm_request(
                analytics_report,
                learning_report,
                prediction_report,
            )
            llm_tool = self.get_tool("llm")
            llm_response = self._get_llm_response(llm_tool.execute(request=llm_request))
            report = self._create_report(llm_response)
            self.last_report = report
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
            selected_tools.append(LLMTool(provider=MockBusinessLLMProvider()))

        return selected_tools

    def _get_analytics_report(self, value: object) -> AnalyticsReport:
        if not isinstance(value, AnalyticsReport):
            msg = "analytics_report must be an AnalyticsReport."
            raise ValueError(msg)

        return value

    def _get_learning_report(self, value: object) -> LearningReport:
        if not isinstance(value, LearningReport):
            msg = "learning_report must be a LearningReport."
            raise ValueError(msg)

        return value

    def _get_prediction_report(self, value: object) -> PredictionReport:
        if not isinstance(value, PredictionReport):
            msg = "prediction_report must be a PredictionReport."
            raise ValueError(msg)

        return value

    def _get_llm_response(self, raw_response: object) -> LLMResponse:
        if not isinstance(raw_response, LLMResponse):
            msg = "llm tool must return an LLMResponse."
            raise ValueError(msg)

        return raw_response

    def _create_llm_request(
        self,
        analytics_report: AnalyticsReport,
        learning_report: LearningReport,
        prediction_report: PredictionReport,
    ) -> LLMRequest:
        strengths = "\n".join(
            f"- {insight.category}: {insight.recommendation}"
            for insight in learning_report.strengths
        )
        weaknesses = "\n".join(
            f"- {insight.category}: {insight.recommendation}"
            for insight in learning_report.weaknesses
        )
        actions = "\n".join(
            f"- {action}" for action in learning_report.recommended_actions
        )
        predictions = "\n".join(
            (
                f"- {prediction.title}: probability={prediction.probability}, "
                f"recommendation={prediction.recommendation}"
            )
            for prediction in prediction_report.predictions
        )
        return LLMRequest(
            system_prompt="Athena erstellt Management-Reports für den CEO.",
            user_prompt=(
                "Analytics\n"
                f"Gesamtviews: {analytics_report.total_views}\n"
                f"Engagement: {analytics_report.total_engagement}\n"
                f"Stärkste Plattform: {analytics_report.strongest_platform}\n\n"
                "Learning\n"
                f"Strengths:\n{strengths}\n"
                f"Weaknesses:\n{weaknesses}\n"
                f"Recommendations:\n{actions}\n\n"
                "Prediction\n"
                f"Predictions:\n{predictions}\n"
                "Probabilities included above.\n"
                f"strongest_prediction: "
                f"{prediction_report.strongest_prediction.title}"
            ),
        )

    def _create_report(self, llm_response: LLMResponse) -> BusinessIntelligenceReport:
        lines = self._response_lines(llm_response)
        return BusinessIntelligenceReport(
            kpis=self._parse_kpis(lines),
            opportunities=self._parse_opportunities(lines),
            risks=self._parse_risks(lines),
            priorities=self._parse_prefixed_values(lines, "Priority: "),
            executive_summary=self._parse_single_value(lines, "ExecutiveSummary: "),
            generated_by=f"{llm_response.provider}:{llm_response.model}",
        )

    def _parse_kpis(self, lines: list[str]) -> list[BusinessKPI]:
        kpis: list[BusinessKPI] = []
        for line in lines:
            if not line.startswith("KPI: "):
                continue

            parts = [part.strip() for part in line.removeprefix("KPI: ").split("|")]
            if len(parts) != 3:
                msg = "KPI lines must contain name, value and description."
                raise ValueError(msg)

            kpis.append(
                BusinessKPI(
                    name=parts[0],
                    value=parts[1],
                    description=parts[2],
                ),
            )

        return kpis

    def _parse_opportunities(self, lines: list[str]) -> list[BusinessOpportunity]:
        opportunities: list[BusinessOpportunity] = []
        for line in lines:
            if not line.startswith("Opportunity: "):
                continue

            parts = [
                part.strip()
                for part in line.removeprefix("Opportunity: ").split("|")
            ]
            if len(parts) != 4:
                msg = "Opportunity lines must contain four fields."
                raise ValueError(msg)

            opportunities.append(
                BusinessOpportunity(
                    title=parts[0],
                    probability=float(parts[1]),
                    impact=parts[2],
                    recommendation=parts[3],
                ),
            )

        return opportunities

    def _parse_risks(self, lines: list[str]) -> list[BusinessRisk]:
        risks: list[BusinessRisk] = []
        for line in lines:
            if not line.startswith("Risk: "):
                continue

            parts = [part.strip() for part in line.removeprefix("Risk: ").split("|")]
            if len(parts) != 3:
                msg = "Risk lines must contain title, severity and mitigation."
                raise ValueError(msg)

            risks.append(
                BusinessRisk(
                    title=parts[0],
                    severity=BusinessRiskSeverity(parts[1]),
                    mitigation=parts[2],
                ),
            )

        return risks

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
