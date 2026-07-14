"""Helios CEO agent."""

from agents.business_intelligence.models import BusinessIntelligenceReport
from agents.ceo.mock_llm_provider import MockCEOLLMProvider
from agents.ceo.models import (
    CompanyPriority,
    ExecutiveDecision,
    ExecutiveDecisionReport,
)
from engine.llm.models import LLMRequest, LLMResponse
from engine.runtime.base_agent import BaseAgent
from engine.runtime.capability import AgentCapability
from engine.tasks.status import TaskStatus
from engine.tasks.task import Task
from engine.tools.base_tool import BaseTool
from engine.tools.llm_tool import LLMTool


class CEOAgent(BaseAgent):
    """Helios agent for creating structured executive decision reports."""

    last_decision_report: ExecutiveDecisionReport | None

    def __init__(self, tools: list[BaseTool] | None = None) -> None:
        """Create the Helios CEO agent."""
        super().__init__(
            agent_id="ceo",
            name="Helios",
            capabilities={AgentCapability.CEO},
        )
        self.last_decision_report = None

        for tool in self._build_tools(tools):
            self.add_tool(tool)

    def run(self, task: Task) -> ExecutiveDecisionReport:
        """Create an executive decision report from a business report."""
        if task.required_capability is not AgentCapability.CEO:
            msg = "CEOAgent can only handle CEO tasks."
            raise ValueError(msg)

        task.start()
        try:
            business_report = self._get_business_report(
                task.payload.get("business_report"),
            )
            llm_request = self._create_llm_request(business_report)
            llm_tool = self.get_tool("llm")
            llm_response = self._get_llm_response(llm_tool.execute(request=llm_request))
            report = self._create_report(llm_response)
            self.last_decision_report = report
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
            selected_tools.append(LLMTool(provider=MockCEOLLMProvider()))

        return selected_tools

    def _get_business_report(self, value: object) -> BusinessIntelligenceReport:
        if not isinstance(value, BusinessIntelligenceReport):
            msg = "business_report must be a BusinessIntelligenceReport."
            raise ValueError(msg)

        return value

    def _get_llm_response(self, raw_response: object) -> LLMResponse:
        if not isinstance(raw_response, LLMResponse):
            msg = "llm tool must return an LLMResponse."
            raise ValueError(msg)

        return raw_response

    def _create_llm_request(
        self,
        business_report: BusinessIntelligenceReport,
    ) -> LLMRequest:
        kpis = "\n".join(
            f"- {kpi.name}: {kpi.value} ({kpi.description})"
            for kpi in business_report.kpis
        )
        risks = "\n".join(
            f"- {risk.title}: {risk.severity.value} ({risk.mitigation})"
            for risk in business_report.risks
        )
        opportunities = "\n".join(
            (
                f"- {opportunity.title}: probability={opportunity.probability}, "
                f"impact={opportunity.impact}"
            )
            for opportunity in business_report.opportunities
        )
        priorities = "\n".join(
            f"- {priority}" for priority in business_report.priorities
        )
        return LLMRequest(
            system_prompt="Helios trifft strategische Unternehmensentscheidungen.",
            user_prompt=(
                f"Executive Summary:\n{business_report.executive_summary}\n\n"
                f"KPIs:\n{kpis}\n\n"
                f"Risiken:\n{risks}\n\n"
                f"Opportunities:\n{opportunities}\n\n"
                f"Priorities:\n{priorities}"
            ),
        )

    def _create_report(self, llm_response: LLMResponse) -> ExecutiveDecisionReport:
        lines = self._response_lines(llm_response)
        return ExecutiveDecisionReport(
            company_status=self._parse_single_value(lines, "CompanyStatus: "),
            priorities=self._parse_priorities(lines),
            decisions=self._parse_decisions(lines),
            executive_summary=self._parse_single_value(lines, "ExecutiveSummary: "),
            generated_by=f"{llm_response.provider}:{llm_response.model}",
        )

    def _parse_priorities(self, lines: list[str]) -> list[CompanyPriority]:
        priorities: list[CompanyPriority] = []
        for line in lines:
            if not line.startswith("Priority: "):
                continue

            parts = [part.strip() for part in line.removeprefix("Priority: ").split("|")]
            if len(parts) != 3:
                msg = "Priority lines must contain title, reason and score."
                raise ValueError(msg)

            priorities.append(
                CompanyPriority(
                    title=parts[0],
                    reason=parts[1],
                    priority_score=float(parts[2]),
                ),
            )

        return priorities

    def _parse_decisions(self, lines: list[str]) -> list[ExecutiveDecision]:
        decisions: list[ExecutiveDecision] = []
        for line in lines:
            if not line.startswith("Decision: "):
                continue

            parts = [part.strip() for part in line.removeprefix("Decision: ").split("|")]
            if len(parts) != 4:
                msg = "Decision lines must contain title, rationale, impact and confidence."
                raise ValueError(msg)

            decisions.append(
                ExecutiveDecision(
                    title=parts[0],
                    rationale=parts[1],
                    expected_impact=parts[2],
                    confidence=float(parts[3]),
                ),
            )

        return decisions

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
