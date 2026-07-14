"""Deterministic resource planning for the Helios CEO agent."""

from agents.ceo.models import (
    DelegationPlan,
    DelegationTask,
    PriorityLevel,
    ResourceAllocation,
    ResourcePlan,
)


def create_resource_plan(delegation_plan: DelegationPlan) -> ResourcePlan:
    """Create deterministic resource allocations from a delegation plan."""
    _validate_delegation_plan(delegation_plan)
    allocations = [
        _create_allocation(task) for task in delegation_plan.tasks
    ]
    return ResourcePlan(
        allocations=allocations,
        summary=(
            "Helios allocated resources for "
            f"{len(allocations)} planned delegation task(s)."
        ),
    )


def _validate_delegation_plan(plan: DelegationPlan) -> None:
    if not isinstance(plan, DelegationPlan):
        msg = "delegation_plan must be a DelegationPlan."
        raise ValueError(msg)

    if not plan.tasks:
        msg = "delegation_plan must contain at least one task."
        raise ValueError(msg)


def _create_allocation(task: DelegationTask) -> ResourceAllocation:
    budget_points, estimated_hours = _resource_values(task.priority)
    return ResourceAllocation(
        allocation_id=f"allocation-{task.task_id}",
        task_id=task.task_id,
        estimated_hours=estimated_hours,
        budget_points=budget_points,
        assigned_department=task.department,
        rationale=(
            f"{task.priority.value} priority receives {budget_points} "
            f"budget points and {estimated_hours} estimated hours."
        ),
    )


def _resource_values(priority: PriorityLevel) -> tuple[int, float]:
    values = {
        PriorityLevel.CRITICAL: (10, 8.0),
        PriorityLevel.HIGH: (6, 5.0),
        PriorityLevel.MEDIUM: (3, 3.0),
        PriorityLevel.LOW: (1, 1.0),
    }
    return values[priority]
