"""Oracle prediction agent."""

from agents.learning.models import LearningReport
from agents.prediction.mock_llm_provider import MockPredictionLLMProvider
from agents.prediction.models import Prediction, PredictionReport
from engine.llm.models import LLMRequest, LLMResponse
from engine.runtime.base_agent import BaseAgent
from engine.runtime.capability import AgentCapability
from engine.tasks.status import TaskStatus
from engine.tasks.task import Task
from engine.tools.base_tool import BaseTool
from engine.tools.llm_tool import LLMTool


class PredictionAgent(BaseAgent):
    """Oracle agent for forecasting content opportunities from learnings."""

    last_prediction_report: PredictionReport | None

    def __init__(self, tools: list[BaseTool] | None = None) -> None:
        """Create the Oracle prediction agent."""
        super().__init__(
            agent_id="prediction",
            name="Oracle",
            capabilities={AgentCapability.PREDICTION},
        )
        self.last_prediction_report = None

        for tool in self._build_tools(tools):
            self.add_tool(tool)

    def run(self, task: Task) -> PredictionReport:
        """Create a prediction report from learning reports."""
        if task.required_capability is not AgentCapability.PREDICTION:
            msg = "PredictionAgent can only handle PREDICTION tasks."
            raise ValueError(msg)

        task.start()
        try:
            learning_reports = self._get_learning_reports(
                task.payload.get("learning_reports"),
            )
            llm_request = self._create_llm_request(learning_reports)
            llm_tool = self.get_tool("llm")
            llm_response = self._get_llm_response(llm_tool.execute(request=llm_request))
            report = self._create_prediction_report(llm_response)
            self.last_prediction_report = report
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
            selected_tools.append(LLMTool(provider=MockPredictionLLMProvider()))

        return selected_tools

    def _get_learning_reports(self, value: object) -> list[LearningReport]:
        if (
            not isinstance(value, list)
            or not value
            or not all(isinstance(report, LearningReport) for report in value)
        ):
            msg = "learning_reports must be a non-empty list of LearningReport items."
            raise ValueError(msg)

        return value

    def _get_llm_response(self, raw_response: object) -> LLMResponse:
        if not isinstance(raw_response, LLMResponse):
            msg = "llm tool must return an LLMResponse."
            raise ValueError(msg)

        return raw_response

    def _create_llm_request(
        self,
        learning_reports: list[LearningReport],
    ) -> LLMRequest:
        report_sections = "\n\n".join(
            self._format_learning_report(report) for report in learning_reports
        )
        return LLMRequest(
            system_prompt=(
                "Oracle erkennt zukünftige Content-Chancen anhand vergangener "
                "Learnings."
            ),
            user_prompt=report_sections,
        )

    def _format_learning_report(self, report: LearningReport) -> str:
        strengths = "\n".join(
            f"- {insight.category}: {insight.observation}"
            for insight in report.strengths
        )
        weaknesses = "\n".join(
            f"- {insight.category}: {insight.observation}"
            for insight in report.weaknesses
        )
        experiments = "\n".join(f"- {experiment}" for experiment in report.experiments)
        actions = "\n".join(f"- {action}" for action in report.recommended_actions)
        return (
            f"Video ID: {report.video_id}\n"
            f"Performance Summary: {report.performance_summary}\n"
            f"Strengths:\n{strengths}\n"
            f"Weaknesses:\n{weaknesses}\n"
            f"Experiments:\n{experiments}\n"
            f"Recommended Actions:\n{actions}"
        )

    def _create_prediction_report(self, llm_response: LLMResponse) -> PredictionReport:
        lines = self._response_lines(llm_response)
        return PredictionReport(
            predictions=self._parse_predictions(lines),
            summary=self._parse_single_value(lines, "Summary: "),
            generated_by=f"{llm_response.provider}:{llm_response.model}",
        )

    def _parse_predictions(self, lines: list[str]) -> list[Prediction]:
        predictions: list[Prediction] = []
        for line in lines:
            if not line.startswith("Prediction: "):
                continue

            parts = [
                part.strip()
                for part in line.removeprefix("Prediction: ").split("|")
            ]
            if len(parts) != 4:
                msg = "Prediction lines must contain title, probability and details."
                raise ValueError(msg)

            predictions.append(
                Prediction(
                    title=parts[0],
                    probability=float(parts[1]),
                    reasoning=parts[2],
                    recommendation=parts[3],
                ),
            )

        return predictions

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
