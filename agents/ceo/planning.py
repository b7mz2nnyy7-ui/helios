"""Deterministic planning helpers for the Helios CEO agent."""

from agents.business_intelligence.models import BusinessIntelligenceReport
from agents.ceo.models import (
    CompanyGoal,
    CompanyPriority,
    ExecutiveDecisionReport,
    ExecutivePlan,
    ExecutivePlanItem,
    GoalHorizon,
    PriorityLevel,
)
from engine.company.department import Department


def create_executive_plan(
    business_report: BusinessIntelligenceReport,
    decision_report: ExecutiveDecisionReport,
) -> ExecutivePlan:
    """Create a deterministic executive plan from business intelligence."""
    _validate_business_report(business_report)

    items = [
        _create_plan_item(index, priority, decision_report)
        for index, priority in enumerate(decision_report.priorities, start=1)
    ]
    if not items:
        msg = "decision_report must contain at least one priority."
        raise ValueError(msg)

    items.sort(key=_priority_sort_key)
    return ExecutivePlan(
        items=items,
        summary=(
            "Helios executive plan prioritizes "
            f"{items[0].goal.title} based on {decision_report.company_status}."
        ),
    )


def _validate_business_report(report: BusinessIntelligenceReport) -> None:
    if not isinstance(report, BusinessIntelligenceReport):
        msg = "business_report must be a BusinessIntelligenceReport."
        raise ValueError(msg)

    if (
        not report.kpis
        or not report.opportunities
        or not report.risks
        or not report.priorities
    ):
        msg = "business_report must contain KPIs, opportunities, risks and priorities."
        raise ValueError(msg)


def _create_plan_item(
    index: int,
    priority: CompanyPriority,
    decision_report: ExecutiveDecisionReport,
) -> ExecutivePlanItem:
    decision = decision_report.decisions[0]
    goal = CompanyGoal(
        goal_id=f"goal-{index}",
        title=priority.title,
        description=priority.reason,
        department=Department.EXECUTIVE,
        horizon=_horizon_for_score(priority.priority_score),
    )
    return ExecutivePlanItem(
        goal=goal,
        priority=_priority_for_score(priority.priority_score),
        rationale=priority.reason,
        expected_business_impact=decision.expected_impact,
    )


def _priority_for_score(score: float) -> PriorityLevel:
    if score >= 0.9:
        return PriorityLevel.CRITICAL
    if score >= 0.75:
        return PriorityLevel.HIGH
    if score >= 0.45:
        return PriorityLevel.MEDIUM
    return PriorityLevel.LOW


def _horizon_for_score(score: float) -> GoalHorizon:
    if score >= 0.9:
        return GoalHorizon.WEEK
    if score >= 0.75:
        return GoalHorizon.MONTH
    if score >= 0.45:
        return GoalHorizon.QUARTER
    return GoalHorizon.YEAR


def _priority_sort_key(item: ExecutivePlanItem) -> tuple[int, str]:
    order = {
        PriorityLevel.CRITICAL: 0,
        PriorityLevel.HIGH: 1,
        PriorityLevel.MEDIUM: 2,
        PriorityLevel.LOW: 3,
    }
    return (order[item.priority], item.goal.goal_id)
