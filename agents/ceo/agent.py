"""Helios CEO agent."""

from agents.business_intelligence.models import BusinessIntelligenceReport
from agents.ceo.delegation import create_delegation_plan
from agents.ceo.mock_llm_provider import MockCEOLLMProvider
from agents.ceo.models import (
    CEOOperatingPlan,
    CompanyPriority,
    DelegationPlan,
    ExecutiveDecision,
    ExecutiveDecisionReport,
    ExecutivePlan,
    ResourcePlan,
)
from agents.ceo.orchestration import create_ceo_operating_plan
from agents.ceo.planning import create_executive_plan
from agents.ceo.resources import create_resource_plan
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
    last_plan: ExecutivePlan | None
    last_delegation_plan: DelegationPlan | None
    last_resource_plan: ResourcePlan | None
    last_operating_plan: CEOOperatingPlan | None

    def __init__(self, tools: list[BaseTool] | None = None) -> None:
        """Create the Helios CEO agent."""
        super().__init__(
            agent_id="ceo",
            name="Helios",
            capabilities={AgentCapability.CEO},
        )
        self.last_decision_report = None
        self.last_plan = None
        self.last_delegation_plan = None
        self.last_resource_plan = None
        self.last_operating_plan = None

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
            report = self._create_decision_report(business_report)
            self.last_decision_report = report
            task.complete(report)
            return report
        except Exception as error:
            if task.status is TaskStatus.RUNNING:
                task.fail(str(error))
            raise

    def create_plan(
        self,
        business_report: BusinessIntelligenceReport,
    ) -> ExecutivePlan:
        """Create a deterministic executive plan from a business report."""
        validated_report = self._get_business_report(business_report)
        decision_report = self._create_decision_report(validated_report)
        self.last_decision_report = decision_report
        plan = create_executive_plan(validated_report, decision_report)
        self.last_plan = plan
        return plan

    def create_delegation_plan(
        self,
        executive_plan: ExecutivePlan,
    ) -> DelegationPlan:
        """Create a deterministic delegation plan from an executive plan."""
        plan = create_delegation_plan(executive_plan)
        self.last_delegation_plan = plan
        return plan

    def create_resource_plan(
        self,
        delegation_plan: DelegationPlan,
    ) -> ResourcePlan:
        """Create a deterministic resource plan from a delegation plan."""
        plan = create_resource_plan(delegation_plan)
        self.last_resource_plan = plan
        return plan

    def create_operating_plan(
        self,
        business_report: BusinessIntelligenceReport,
    ) -> CEOOperatingPlan:
        """Create a deterministic CEO operating plan from business intelligence."""
        validated_report = self._get_business_report(business_report)
        executive_plan = self.create_plan(validated_report)
        decision_report = self.last_decision_report
        if decision_report is None:
            msg = "decision_report must be available after create_plan()."
            raise ValueError(msg)

        delegation_plan = self.create_delegation_plan(executive_plan)
        resource_plan = self.create_resource_plan(delegation_plan)
        operating_plan = create_ceo_operating_plan(
            business_report=validated_report,
            decision_report=decision_report,
            executive_plan=executive_plan,
            delegation_plan=delegation_plan,
            resource_plan=resource_plan,
        )
        self.last_operating_plan = operating_plan
        return operating_plan

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

    def _create_decision_report(
        self,
        business_report: BusinessIntelligenceReport,
    ) -> ExecutiveDecisionReport:
        llm_request = self._create_llm_request(business_report)
        llm_tool = self.get_tool("llm")
        llm_response = self._get_llm_response(llm_tool.execute(request=llm_request))
        return self._create_report(llm_response)

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
