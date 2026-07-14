"""Tests for Helios CEO operating plan orchestration."""

import unittest
from datetime import UTC

from agents.business_intelligence.models import (
    BusinessIntelligenceReport,
    BusinessKPI,
    BusinessOpportunity,
    BusinessRisk,
    BusinessRiskSeverity,
)
from agents.ceo.agent import CEOAgent
from agents.ceo.models import (
    CEOOperatingPlan,
    DelegationPlan,
    ExecutiveDecisionReport,
    ExecutivePlan,
    ResourcePlan,
)
from engine.tasks.task import Task


def create_business_report() -> BusinessIntelligenceReport:
    """Create a business intelligence report for CEO orchestration tests."""
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


class RunFailingCEOAgent(CEOAgent):
    """CEO agent that fails if orchestration calls run()."""

    def run(self, task: Task) -> ExecutiveDecisionReport:
        """Fail when run is called."""
        msg = "run must not be called during operating plan creation"
        raise AssertionError(msg)


class CEOOrchestrationTestCase(unittest.TestCase):
    """Tests for CEO operating plan orchestration."""

    def test_operating_plan_requires_all_parts(self) -> None:
        """CEOOperatingPlan validates required report fields."""
        agent = CEOAgent()
        operating_plan = agent.create_operating_plan(create_business_report())

        with self.assertRaises(ValueError):
            CEOOperatingPlan(
                business_report=operating_plan.business_report,
                decision_report=None,  # type: ignore[arg-type]
                executive_plan=operating_plan.executive_plan,
                delegation_plan=operating_plan.delegation_plan,
                resource_plan=operating_plan.resource_plan,
                summary="Valid summary.",
            )

    def test_operating_plan_summary_must_not_be_empty(self) -> None:
        """CEOOperatingPlan rejects an empty summary."""
        agent = CEOAgent()
        operating_plan = agent.create_operating_plan(create_business_report())

        with self.assertRaises(ValueError):
            CEOOperatingPlan(
                business_report=operating_plan.business_report,
                decision_report=operating_plan.decision_report,
                executive_plan=operating_plan.executive_plan,
                delegation_plan=operating_plan.delegation_plan,
                resource_plan=operating_plan.resource_plan,
                summary="",
            )

    def test_created_at_uses_utc(self) -> None:
        """CEOOperatingPlan timestamps are UTC-aware."""
        agent = CEOAgent()

        operating_plan = agent.create_operating_plan(create_business_report())

        self.assertIs(operating_plan.created_at.tzinfo, UTC)

    def test_to_markdown_contains_all_five_layers(self) -> None:
        """CEOOperatingPlan Markdown contains every planning layer."""
        agent = CEOAgent()

        operating_plan = agent.create_operating_plan(create_business_report())
        markdown = operating_plan.to_markdown()

        self.assertIn("Business Intelligence Report", markdown)
        self.assertIn("Executive Decision Report", markdown)
        self.assertIn("Executive Plan", markdown)
        self.assertIn("Delegation Plan", markdown)
        self.assertIn("Resource Plan", markdown)

    def test_create_operating_plan_creates_all_parts(self) -> None:
        """CEOAgent creates every operating plan component."""
        agent = CEOAgent()

        operating_plan = agent.create_operating_plan(create_business_report())

        self.assertIsInstance(operating_plan, CEOOperatingPlan)
        self.assertIsInstance(operating_plan.decision_report, ExecutiveDecisionReport)
        self.assertIsInstance(operating_plan.executive_plan, ExecutivePlan)
        self.assertIsInstance(operating_plan.delegation_plan, DelegationPlan)
        self.assertIsInstance(operating_plan.resource_plan, ResourcePlan)

    def test_last_operating_plan_is_stored(self) -> None:
        """CEOAgent stores the last operating plan."""
        agent = CEOAgent()

        operating_plan = agent.create_operating_plan(create_business_report())

        self.assertIs(agent.last_operating_plan, operating_plan)

    def test_existing_last_values_are_updated(self) -> None:
        """CEOAgent updates all last planning attributes."""
        agent = CEOAgent()

        operating_plan = agent.create_operating_plan(create_business_report())

        self.assertIs(agent.last_decision_report, operating_plan.decision_report)
        self.assertIs(agent.last_plan, operating_plan.executive_plan)
        self.assertIs(agent.last_delegation_plan, operating_plan.delegation_plan)
        self.assertIs(agent.last_resource_plan, operating_plan.resource_plan)

    def test_same_input_produces_same_planning_content(self) -> None:
        """The same business report produces identical plan content."""
        agent = CEOAgent()
        report = create_business_report()

        first_plan = agent.create_operating_plan(report)
        second_plan = agent.create_operating_plan(report)

        self.assertEqual(first_plan.to_markdown(), second_plan.to_markdown())

    def test_business_report_is_not_mutated(self) -> None:
        """Operating plan creation leaves the business report unchanged."""
        agent = CEOAgent()
        report = create_business_report()
        before = report.to_markdown()

        agent.create_operating_plan(report)

        self.assertEqual(report.to_markdown(), before)

    def test_wrong_input_type_raises_value_error(self) -> None:
        """CEOAgent rejects non-business-report input."""
        agent = CEOAgent()

        with self.assertRaises(ValueError):
            agent.create_operating_plan("invalid")  # type: ignore[arg-type]

    def test_create_operating_plan_does_not_call_run(self) -> None:
        """Operating plan creation does not use Task-based agent execution."""
        agent = RunFailingCEOAgent()

        operating_plan = agent.create_operating_plan(create_business_report())

        self.assertIsInstance(operating_plan, CEOOperatingPlan)


if __name__ == "__main__":
    unittest.main()
