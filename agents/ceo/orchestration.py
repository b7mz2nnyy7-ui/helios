"""Deterministic orchestration helpers for the Helios CEO agent."""

from agents.business_intelligence.models import BusinessIntelligenceReport
from agents.ceo.models import (
    CEOOperatingPlan,
    DelegationPlan,
    ExecutiveDecisionReport,
    ExecutivePlan,
    ResourcePlan,
)


def create_ceo_operating_plan(
    business_report: BusinessIntelligenceReport,
    decision_report: ExecutiveDecisionReport,
    executive_plan: ExecutivePlan,
    delegation_plan: DelegationPlan,
    resource_plan: ResourcePlan,
) -> CEOOperatingPlan:
    """Create a complete CEO operating plan from existing planning layers."""
    return CEOOperatingPlan(
        business_report=business_report,
        decision_report=decision_report,
        executive_plan=executive_plan,
        delegation_plan=delegation_plan,
        resource_plan=resource_plan,
        summary=(
            "Helios operating plan connects executive decisions, company goals, "
            "delegation and resource allocation into one deterministic plan."
        ),
    )
