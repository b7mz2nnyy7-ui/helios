"""Tests for Helios CEO goal and priority planning."""

import unittest

from agents.business_intelligence.models import (
    BusinessIntelligenceReport,
    BusinessKPI,
    BusinessOpportunity,
    BusinessRisk,
    BusinessRiskSeverity,
)
from agents.ceo.agent import CEOAgent
from agents.ceo.models import (
    CompanyGoal,
    ExecutivePlan,
    ExecutivePlanItem,
    GoalHorizon,
    PriorityLevel,
)
from engine.company.department import Department


def create_business_report() -> BusinessIntelligenceReport:
    """Create a business intelligence report for planning tests."""
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


def create_empty_business_report() -> BusinessIntelligenceReport:
    """Create an intentionally malformed empty report."""
    report = object.__new__(BusinessIntelligenceReport)
    report.kpis = []
    report.opportunities = []
    report.risks = []
    report.priorities = []
    report.executive_summary = ""
    report.generated_by = "test"
    return report


def create_plan_item() -> ExecutivePlanItem:
    """Create an executive plan item for model tests."""
    return ExecutivePlanItem(
        goal=CompanyGoal(
            goal_id="goal-1",
            title="Scale Checklist CTA Experiment",
            description="Focus execution on the strongest business signal.",
            department=Department.EXECUTIVE,
            horizon=GoalHorizon.WEEK,
        ),
        priority=PriorityLevel.CRITICAL,
        rationale="Business intelligence shows strong upside.",
        expected_business_impact="Higher save/share rate.",
    )


class CEOPlanningTestCase(unittest.TestCase):
    """Tests for CEO planning models and behavior."""

    def test_goal_validation(self) -> None:
        """CompanyGoal rejects empty identifiers."""
        with self.assertRaises(ValueError):
            CompanyGoal(
                goal_id="",
                title="Scale content",
                description="Increase output quality.",
                department=Department.EXECUTIVE,
                horizon=GoalHorizon.WEEK,
            )

    def test_horizon_enum(self) -> None:
        """GoalHorizon exposes the required values."""
        self.assertEqual(GoalHorizon.TODAY.value, "TODAY")
        self.assertEqual(GoalHorizon.WEEK.value, "WEEK")
        self.assertEqual(GoalHorizon.MONTH.value, "MONTH")
        self.assertEqual(GoalHorizon.QUARTER.value, "QUARTER")
        self.assertEqual(GoalHorizon.YEAR.value, "YEAR")

    def test_priority_enum(self) -> None:
        """PriorityLevel exposes the required values."""
        self.assertEqual(PriorityLevel.CRITICAL.value, "CRITICAL")
        self.assertEqual(PriorityLevel.HIGH.value, "HIGH")
        self.assertEqual(PriorityLevel.MEDIUM.value, "MEDIUM")
        self.assertEqual(PriorityLevel.LOW.value, "LOW")

    def test_executive_plan_validation(self) -> None:
        """ExecutivePlan requires at least one item."""
        with self.assertRaises(ValueError):
            ExecutivePlan(items=[], summary="No priorities.")

    def test_to_markdown(self) -> None:
        """ExecutivePlan renders to Markdown."""
        plan = ExecutivePlan(
            items=[create_plan_item()],
            summary="Focus on the strongest execution path.",
        )

        markdown = plan.to_markdown()

        self.assertIn("# Executive Plan", markdown)
        self.assertIn("Scale Checklist CTA Experiment", markdown)
        self.assertIn("CRITICAL", markdown)

    def test_create_plan(self) -> None:
        """CEOAgent creates an executive plan from business intelligence."""
        agent = CEOAgent()

        plan = agent.create_plan(create_business_report())

        self.assertIsInstance(plan, ExecutivePlan)
        self.assertGreaterEqual(len(plan.items), 1)
        self.assertIn(
            plan.items[0].priority,
            {PriorityLevel.CRITICAL, PriorityLevel.HIGH},
        )

    def test_last_plan_is_stored(self) -> None:
        """CEOAgent stores the last executive plan."""
        agent = CEOAgent()

        plan = agent.create_plan(create_business_report())

        self.assertIs(agent.last_plan, plan)

    def test_create_plan_is_deterministic(self) -> None:
        """The same input produces the same executive plan content."""
        agent = CEOAgent()
        report = create_business_report()

        first_plan = agent.create_plan(report)
        second_plan = agent.create_plan(report)

        self.assertEqual(first_plan.to_markdown(), second_plan.to_markdown())

    def test_create_plan_does_not_mutate_report(self) -> None:
        """Planning leaves the business report unchanged."""
        agent = CEOAgent()
        report = create_business_report()
        before = report.to_markdown()

        agent.create_plan(report)

        self.assertEqual(report.to_markdown(), before)

    def test_empty_report_raises_value_error(self) -> None:
        """CEOAgent rejects an empty business report."""
        agent = CEOAgent()

        with self.assertRaises(ValueError):
            agent.create_plan(create_empty_business_report())


if __name__ == "__main__":
    unittest.main()
