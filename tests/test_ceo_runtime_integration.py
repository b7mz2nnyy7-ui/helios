"""Runtime integration tests for Helios CEO agent."""

import unittest

from agents.business_intelligence.models import (
    BusinessIntelligenceReport,
    BusinessKPI,
    BusinessOpportunity,
    BusinessRisk,
    BusinessRiskSeverity,
)
from agents.ceo.agent import CEOAgent
from agents.ceo.models import ExecutiveDecisionReport
from engine.runtime.capability import AgentCapability
from engine.runtime.runtime import HeliosRuntime
from engine.tasks.priority import TaskPriority
from engine.tasks.status import TaskStatus
from engine.tasks.task import Task


def create_business_report() -> BusinessIntelligenceReport:
    """Create a business intelligence report for runtime integration tests."""
    return BusinessIntelligenceReport(
        kpis=[
            BusinessKPI(
                name="Total Views",
                value="1750",
                description="Current portfolio-level demand signal.",
            ),
        ],
        opportunities=[
            BusinessOpportunity(
                title="Checklist CTA Lift",
                probability=0.82,
                impact="High near-term growth upside",
                recommendation="Prioritize checklist-led variants.",
            ),
        ],
        risks=[
            BusinessRisk(
                title="Platform Engagement Gap",
                severity=BusinessRiskSeverity.MEDIUM,
                mitigation="Recut weak-platform pacing.",
            ),
        ],
        priorities=["Launch the checklist CTA experiment first."],
        executive_summary=(
            "Athena recommends prioritizing Checklist CTA Lift because it is "
            "the strongest prediction."
        ),
        generated_by="mock:mock-business-model",
    )


def create_ceo_task(payload: dict[str, object] | None = None) -> Task:
    """Create a CEO task for runtime integration tests."""
    return Task(
        task_id="ceo-task-1",
        title="CEO Decision",
        description="Create executive decision report.",
        priority=TaskPriority.MEDIUM,
        required_capability=AgentCapability.CEO,
        payload=(
            {"business_report": create_business_report()}
            if payload is None
            else payload
        ),
    )


class CEORuntimeIntegrationTestCase(unittest.TestCase):
    """Integration tests for Helios CEO through HeliosRuntime."""

    def test_runtime_dispatches_ceo_task_to_helios(self) -> None:
        """Runtime can dispatch CEO tasks to Helios."""
        runtime = HeliosRuntime()
        helios = CEOAgent()
        task = create_ceo_task()
        runtime.register(helios)

        result = runtime.submit_task(task)

        self.assertIsInstance(result, ExecutiveDecisionReport)
        self.assertIs(result, task.result)
        self.assertIs(task.status, TaskStatus.COMPLETED)
        self.assertIs(helios.last_decision_report, result)

    def test_runtime_returns_executive_decision_report(self) -> None:
        """Runtime returns the ExecutiveDecisionReport from Helios."""
        runtime = HeliosRuntime()
        runtime.register(CEOAgent())
        task = create_ceo_task()

        result = runtime.submit_task(task)

        self.assertIsInstance(result, ExecutiveDecisionReport)

    def test_runtime_propagates_helios_errors(self) -> None:
        """Runtime propagates Helios validation errors."""
        runtime = HeliosRuntime()
        runtime.register(CEOAgent())
        task = create_ceo_task({"business_report": "invalid"})

        with self.assertRaises(ValueError):
            runtime.submit_task(task)

        self.assertIs(task.status, TaskStatus.FAILED)


if __name__ == "__main__":
    unittest.main()
