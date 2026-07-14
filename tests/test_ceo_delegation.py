"""Tests for Helios CEO delegation planning."""

import unittest

from agents.ceo.agent import CEOAgent
from agents.ceo.delegation import capability_for_department
from agents.ceo.models import (
    CompanyGoal,
    DelegationPlan,
    DelegationTask,
    ExecutivePlan,
    ExecutivePlanItem,
    GoalHorizon,
    PriorityLevel,
)
from engine.company.department import Department
from engine.runtime.capability import AgentCapability


def create_plan_item(
    goal_id: str = "goal-1",
    department: Department = Department.STRATEGY,
) -> ExecutivePlanItem:
    """Create an executive plan item for delegation tests."""
    return ExecutivePlanItem(
        goal=CompanyGoal(
            goal_id=goal_id,
            title="Scale Checklist CTA Experiment",
            description="Focus execution on the strongest business signal.",
            department=department,
            horizon=GoalHorizon.WEEK,
        ),
        priority=PriorityLevel.CRITICAL,
        rationale="Business intelligence shows strong upside.",
        expected_business_impact="Higher save/share rate.",
    )


def create_executive_plan() -> ExecutivePlan:
    """Create an executive plan for delegation tests."""
    return ExecutivePlan(
        items=[create_plan_item()],
        summary="Focus the company on the strongest growth signal.",
    )


def create_empty_executive_plan() -> ExecutivePlan:
    """Create an intentionally malformed empty executive plan."""
    plan = object.__new__(ExecutivePlan)
    plan.items = []
    plan.summary = ""
    return plan


def create_delegation_task() -> DelegationTask:
    """Create a delegation task for model tests."""
    return DelegationTask(
        task_id="delegation-goal-1",
        department="STRATEGY",
        target_capability=AgentCapability.STRATEGY,
        title="Scale Checklist CTA Experiment",
        description="Focus execution on the strongest business signal.",
        priority=PriorityLevel.CRITICAL,
        expected_output="Higher save/share rate.",
        rationale="Business intelligence shows strong upside.",
    )


class CEODelegationTestCase(unittest.TestCase):
    """Tests for CEO delegation models and behavior."""

    def test_delegation_task_validation(self) -> None:
        """DelegationTask rejects empty required fields."""
        with self.assertRaises(ValueError):
            DelegationTask(
                task_id="",
                department="STRATEGY",
                target_capability=AgentCapability.STRATEGY,
                title="Scale Checklist CTA Experiment",
                description="Focus execution.",
                priority=PriorityLevel.CRITICAL,
                expected_output="Higher growth.",
                rationale="Strong signal.",
            )

    def test_delegation_plan_validation(self) -> None:
        """DelegationPlan requires at least one task."""
        with self.assertRaises(ValueError):
            DelegationPlan(tasks=[], summary="No delegation.")

    def test_to_markdown(self) -> None:
        """DelegationPlan renders to Markdown."""
        plan = DelegationPlan(
            tasks=[create_delegation_task()],
            summary="Delegate the top company priority.",
        )

        markdown = plan.to_markdown()

        self.assertIn("# Delegation Plan", markdown)
        self.assertIn("Scale Checklist CTA Experiment", markdown)
        self.assertIn("STRATEGY", markdown)

    def test_create_delegation_plan(self) -> None:
        """CEOAgent creates delegation tasks from an executive plan."""
        agent = CEOAgent()

        plan = agent.create_delegation_plan(create_executive_plan())

        self.assertIsInstance(plan, DelegationPlan)
        self.assertEqual(len(plan.tasks), 1)
        self.assertEqual(plan.tasks[0].target_capability, AgentCapability.STRATEGY)

    def test_department_mapping(self) -> None:
        """Department identifiers map to the expected capabilities."""
        self.assertEqual(
            capability_for_department("CONTENT_STRATEGY"),
            AgentCapability.STRATEGY,
        )
        self.assertEqual(
            capability_for_department("CONTENT_PRODUCTION"),
            AgentCapability.SCRIPT,
        )
        self.assertEqual(
            capability_for_department("VIDEO"),
            AgentCapability.VIDEO_PRODUCTION,
        )
        self.assertEqual(
            capability_for_department("ANALYTICS"),
            AgentCapability.ANALYTICS,
        )
        self.assertEqual(
            capability_for_department("BUSINESS"),
            AgentCapability.BUSINESS_INTELLIGENCE,
        )
        self.assertEqual(
            capability_for_department("UNKNOWN"),
            AgentCapability.CEO,
        )

    def test_create_delegation_plan_is_deterministic(self) -> None:
        """The same executive plan produces the same delegation content."""
        agent = CEOAgent()
        executive_plan = create_executive_plan()

        first_plan = agent.create_delegation_plan(executive_plan)
        second_plan = agent.create_delegation_plan(executive_plan)

        self.assertEqual(first_plan.to_markdown(), second_plan.to_markdown())

    def test_last_delegation_plan_is_stored(self) -> None:
        """CEOAgent stores the last delegation plan."""
        agent = CEOAgent()

        plan = agent.create_delegation_plan(create_executive_plan())

        self.assertIs(agent.last_delegation_plan, plan)

    def test_create_delegation_plan_does_not_mutate_executive_plan(self) -> None:
        """Delegation planning leaves the executive plan unchanged."""
        agent = CEOAgent()
        executive_plan = create_executive_plan()
        before = executive_plan.to_markdown()

        agent.create_delegation_plan(executive_plan)

        self.assertEqual(executive_plan.to_markdown(), before)

    def test_empty_plan_raises_value_error(self) -> None:
        """CEOAgent rejects an empty executive plan."""
        agent = CEOAgent()

        with self.assertRaises(ValueError):
            agent.create_delegation_plan(create_empty_executive_plan())


if __name__ == "__main__":
    unittest.main()
