"""Deterministic delegation planning for the Helios CEO agent."""

from agents.ceo.models import (
    DelegationPlan,
    DelegationTask,
    ExecutivePlan,
    ExecutivePlanItem,
)
from engine.runtime.capability import AgentCapability


def create_delegation_plan(executive_plan: ExecutivePlan) -> DelegationPlan:
    """Create a deterministic delegation plan from an executive plan."""
    _validate_executive_plan(executive_plan)
    tasks = [_create_delegation_task(item) for item in executive_plan.items]
    return DelegationPlan(
        tasks=tasks,
        summary=(
            "Helios prepared "
            f"{len(tasks)} delegation task(s) from the executive plan."
        ),
    )


def capability_for_department(department: object) -> AgentCapability:
    """Map a department identifier to the target agent capability."""
    department_key = _department_key(department)
    capability_by_department = {
        "CONTENT_STRATEGY": AgentCapability.STRATEGY,
        "STRATEGY": AgentCapability.STRATEGY,
        "CONTENT_PRODUCTION": AgentCapability.SCRIPT,
        "WRITING": AgentCapability.SCRIPT,
        "VIDEO": AgentCapability.VIDEO_PRODUCTION,
        "PRODUCTION": AgentCapability.VIDEO_PRODUCTION,
        "ANALYTICS": AgentCapability.ANALYTICS,
        "BUSINESS": AgentCapability.BUSINESS_INTELLIGENCE,
    }
    return capability_by_department.get(department_key, AgentCapability.CEO)


def _validate_executive_plan(plan: ExecutivePlan) -> None:
    if not isinstance(plan, ExecutivePlan):
        msg = "executive_plan must be an ExecutivePlan."
        raise ValueError(msg)

    if not plan.items:
        msg = "executive_plan must contain at least one item."
        raise ValueError(msg)


def _create_delegation_task(item: ExecutivePlanItem) -> DelegationTask:
    department = _department_key(item.goal.department)
    return DelegationTask(
        task_id=f"delegation-{item.goal.goal_id}",
        department=department,
        target_capability=capability_for_department(department),
        title=item.goal.title,
        description=item.goal.description,
        priority=item.priority,
        expected_output=item.expected_business_impact,
        rationale=item.rationale,
    )


def _department_key(department: object) -> str:
    value = getattr(department, "value", department)
    return str(value).strip().upper()
