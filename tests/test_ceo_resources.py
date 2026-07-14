"""Tests for Helios CEO resource and budget planning."""

import unittest

from agents.ceo.agent import CEOAgent
from agents.ceo.models import (
    DelegationPlan,
    DelegationTask,
    PriorityLevel,
    ResourceAllocation,
    ResourcePlan,
)
from engine.runtime.capability import AgentCapability


def create_delegation_task(
    task_id: str = "delegation-goal-1",
    priority: PriorityLevel = PriorityLevel.CRITICAL,
) -> DelegationTask:
    """Create a delegation task for resource tests."""
    return DelegationTask(
        task_id=task_id,
        department="STRATEGY",
        target_capability=AgentCapability.STRATEGY,
        title="Scale Checklist CTA Experiment",
        description="Focus execution on the strongest business signal.",
        priority=priority,
        expected_output="Higher save/share rate.",
        rationale="Business intelligence shows strong upside.",
    )


def create_delegation_plan() -> DelegationPlan:
    """Create a delegation plan containing all priority levels."""
    return DelegationPlan(
        tasks=[
            create_delegation_task("task-critical", PriorityLevel.CRITICAL),
            create_delegation_task("task-high", PriorityLevel.HIGH),
            create_delegation_task("task-medium", PriorityLevel.MEDIUM),
            create_delegation_task("task-low", PriorityLevel.LOW),
        ],
        summary="Delegate all priority levels.",
    )


def create_empty_delegation_plan() -> DelegationPlan:
    """Create an intentionally malformed empty delegation plan."""
    plan = object.__new__(DelegationPlan)
    plan.tasks = []
    plan.summary = ""
    return plan


def create_allocation() -> ResourceAllocation:
    """Create a resource allocation for model tests."""
    return ResourceAllocation(
        allocation_id="allocation-task-critical",
        task_id="task-critical",
        estimated_hours=8.0,
        budget_points=10,
        assigned_department="STRATEGY",
        rationale="CRITICAL priority receives the largest allocation.",
    )


class CEOResourcesTestCase(unittest.TestCase):
    """Tests for CEO resource planning models and behavior."""

    def test_resource_allocation_validation(self) -> None:
        """ResourceAllocation rejects invalid hours and budget."""
        with self.assertRaises(ValueError):
            ResourceAllocation(
                allocation_id="allocation-1",
                task_id="task-1",
                estimated_hours=0,
                budget_points=1,
                assigned_department="STRATEGY",
                rationale="Invalid hours.",
            )

        with self.assertRaises(ValueError):
            ResourceAllocation(
                allocation_id="allocation-1",
                task_id="task-1",
                estimated_hours=1,
                budget_points=-1,
                assigned_department="STRATEGY",
                rationale="Invalid budget.",
            )

    def test_resource_plan_validation(self) -> None:
        """ResourcePlan requires at least one allocation."""
        with self.assertRaises(ValueError):
            ResourcePlan(allocations=[], summary="No allocations.")

    def test_totals_are_calculated(self) -> None:
        """ResourcePlan calculates budget and hour totals."""
        plan = ResourcePlan(
            allocations=[
                create_allocation(),
                ResourceAllocation(
                    allocation_id="allocation-task-low",
                    task_id="task-low",
                    estimated_hours=1.0,
                    budget_points=1,
                    assigned_department="STRATEGY",
                    rationale="LOW priority receives the smallest allocation.",
                ),
            ],
            summary="Allocate resources.",
        )

        self.assertEqual(plan.total_budget_points, 11)
        self.assertEqual(plan.total_estimated_hours, 9.0)

    def test_to_markdown(self) -> None:
        """ResourcePlan renders to Markdown."""
        plan = ResourcePlan(
            allocations=[create_allocation()],
            summary="Allocate resources.",
        )

        markdown = plan.to_markdown()

        self.assertIn("# Resource Plan", markdown)
        self.assertIn("Total Budget Points: 10", markdown)
        self.assertIn("task-critical", markdown)

    def test_create_resource_plan(self) -> None:
        """CEOAgent creates a resource plan from a delegation plan."""
        agent = CEOAgent()

        plan = agent.create_resource_plan(create_delegation_plan())

        allocations_by_task = {
            allocation.task_id: allocation for allocation in plan.allocations
        }
        self.assertEqual(allocations_by_task["task-critical"].budget_points, 10)
        self.assertEqual(allocations_by_task["task-critical"].estimated_hours, 8.0)
        self.assertEqual(allocations_by_task["task-high"].budget_points, 6)
        self.assertEqual(allocations_by_task["task-high"].estimated_hours, 5.0)
        self.assertEqual(allocations_by_task["task-medium"].budget_points, 3)
        self.assertEqual(allocations_by_task["task-medium"].estimated_hours, 3.0)
        self.assertEqual(allocations_by_task["task-low"].budget_points, 1)
        self.assertEqual(allocations_by_task["task-low"].estimated_hours, 1.0)

    def test_last_resource_plan_is_stored(self) -> None:
        """CEOAgent stores the last resource plan."""
        agent = CEOAgent()

        plan = agent.create_resource_plan(create_delegation_plan())

        self.assertIs(agent.last_resource_plan, plan)

    def test_create_resource_plan_is_deterministic(self) -> None:
        """The same delegation plan produces the same resource content."""
        agent = CEOAgent()
        delegation_plan = create_delegation_plan()

        first_plan = agent.create_resource_plan(delegation_plan)
        second_plan = agent.create_resource_plan(delegation_plan)

        self.assertEqual(first_plan.to_markdown(), second_plan.to_markdown())

    def test_create_resource_plan_does_not_mutate_delegation_plan(self) -> None:
        """Resource planning leaves the delegation plan unchanged."""
        agent = CEOAgent()
        delegation_plan = create_delegation_plan()
        before = delegation_plan.to_markdown()

        agent.create_resource_plan(delegation_plan)

        self.assertEqual(delegation_plan.to_markdown(), before)

    def test_empty_delegation_plan_raises_value_error(self) -> None:
        """CEOAgent rejects an empty delegation plan."""
        agent = CEOAgent()

        with self.assertRaises(ValueError):
            agent.create_resource_plan(create_empty_delegation_plan())


if __name__ == "__main__":
    unittest.main()
