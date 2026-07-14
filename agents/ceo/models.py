"""Models for the Helios CEO agent."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from agents.business_intelligence.models import BusinessIntelligenceReport
from engine.company.department import Department
from engine.runtime.capability import AgentCapability


class GoalHorizon(StrEnum):
    """Time horizon for company goals."""

    TODAY = "TODAY"
    WEEK = "WEEK"
    MONTH = "MONTH"
    QUARTER = "QUARTER"
    YEAR = "YEAR"


class PriorityLevel(StrEnum):
    """Priority levels for executive planning."""

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


@dataclass
class CompanyGoal:
    """A structured company goal for executive planning."""

    goal_id: str
    title: str
    description: str
    department: Department
    horizon: GoalHorizon

    def __post_init__(self) -> None:
        """Validate company goal values."""
        for field_name, value in {
            "goal_id": self.goal_id,
            "title": self.title,
            "description": self.description,
        }.items():
            if not value.strip():
                msg = f"{field_name} must not be empty."
                raise ValueError(msg)


@dataclass
class ExecutivePlanItem:
    """A prioritized company goal with executive rationale."""

    goal: CompanyGoal
    priority: PriorityLevel
    rationale: str
    expected_business_impact: str

    def __post_init__(self) -> None:
        """Validate executive plan item values."""
        for field_name, value in {
            "rationale": self.rationale,
            "expected_business_impact": self.expected_business_impact,
        }.items():
            if not value.strip():
                msg = f"{field_name} must not be empty."
                raise ValueError(msg)


@dataclass
class ExecutivePlan:
    """Deterministic CEO plan made of prioritized goals."""

    items: list[ExecutivePlanItem]
    summary: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        """Validate executive plan values."""
        if not self.items:
            msg = "items must contain at least one ExecutivePlanItem."
            raise ValueError(msg)

        if not self.summary.strip():
            msg = "summary must not be empty."
            raise ValueError(msg)

    def to_markdown(self) -> str:
        """Return the executive plan as Markdown."""
        items = "\n".join(
            (
                f"- {item.priority.value}: {item.goal.title} "
                f"({item.goal.department.value}, {item.goal.horizon.value}) - "
                f"{item.expected_business_impact}"
            )
            for item in self.items
        )
        return (
            "# Executive Plan\n\n"
            f"## Summary\n\n{self.summary}\n\n"
            f"## Priorities\n\n{items}"
        )


@dataclass
class DelegationTask:
    """A structured task that Helios can delegate later."""

    task_id: str
    department: str
    target_capability: AgentCapability
    title: str
    description: str
    priority: PriorityLevel
    expected_output: str
    rationale: str

    def __post_init__(self) -> None:
        """Validate delegation task values."""
        for field_name, value in {
            "task_id": self.task_id,
            "department": self.department,
            "title": self.title,
            "description": self.description,
            "expected_output": self.expected_output,
            "rationale": self.rationale,
        }.items():
            if not value.strip():
                msg = f"{field_name} must not be empty."
                raise ValueError(msg)


@dataclass
class DelegationPlan:
    """A deterministic collection of planned delegation tasks."""

    tasks: list[DelegationTask]
    summary: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        """Validate delegation plan values."""
        if not self.tasks:
            msg = "tasks must contain at least one DelegationTask."
            raise ValueError(msg)

        if not self.summary.strip():
            msg = "summary must not be empty."
            raise ValueError(msg)

    def to_markdown(self) -> str:
        """Return the delegation plan as Markdown."""
        tasks = "\n".join(
            (
                f"- {task.priority.value}: {task.title} "
                f"({task.department} -> {task.target_capability.value}) - "
                f"{task.expected_output}"
            )
            for task in self.tasks
        )
        return (
            "# Delegation Plan\n\n"
            f"## Summary\n\n{self.summary}\n\n"
            f"## Tasks\n\n{tasks}"
        )


@dataclass
class ResourceAllocation:
    """Resource allocation for one planned delegation task."""

    allocation_id: str
    task_id: str
    estimated_hours: float
    budget_points: int
    assigned_department: str
    rationale: str

    def __post_init__(self) -> None:
        """Validate resource allocation values."""
        for field_name, value in {
            "allocation_id": self.allocation_id,
            "task_id": self.task_id,
            "assigned_department": self.assigned_department,
            "rationale": self.rationale,
        }.items():
            if not value.strip():
                msg = f"{field_name} must not be empty."
                raise ValueError(msg)

        if self.estimated_hours <= 0:
            msg = "estimated_hours must be greater than 0."
            raise ValueError(msg)

        if self.budget_points < 0:
            msg = "budget_points must be greater than or equal to 0."
            raise ValueError(msg)


@dataclass
class ResourcePlan:
    """Deterministic resource and budget plan."""

    allocations: list[ResourceAllocation]
    summary: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    total_budget_points: int = field(init=False)
    total_estimated_hours: float = field(init=False)

    def __post_init__(self) -> None:
        """Validate resource plan values and calculate totals."""
        if not self.allocations:
            msg = "allocations must contain at least one ResourceAllocation."
            raise ValueError(msg)

        if not self.summary.strip():
            msg = "summary must not be empty."
            raise ValueError(msg)

        self.total_budget_points = sum(
            allocation.budget_points for allocation in self.allocations
        )
        self.total_estimated_hours = sum(
            allocation.estimated_hours for allocation in self.allocations
        )

    def to_markdown(self) -> str:
        """Return the resource plan as Markdown."""
        allocations = "\n".join(
            (
                f"- {allocation.task_id}: {allocation.budget_points} budget points, "
                f"{allocation.estimated_hours}h "
                f"({allocation.assigned_department})"
            )
            for allocation in self.allocations
        )
        return (
            "# Resource Plan\n\n"
            f"## Summary\n\n{self.summary}\n\n"
            f"Total Budget Points: {self.total_budget_points}\n\n"
            f"Total Estimated Hours: {self.total_estimated_hours}\n\n"
            f"## Allocations\n\n{allocations}"
        )


@dataclass
class CEOOperatingPlan:
    """Complete deterministic operating plan for the Helios CEO agent."""

    business_report: BusinessIntelligenceReport
    decision_report: "ExecutiveDecisionReport"
    executive_plan: ExecutivePlan
    delegation_plan: DelegationPlan
    resource_plan: ResourcePlan
    summary: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        """Validate CEO operating plan values."""
        required_parts = {
            "business_report": self.business_report,
            "decision_report": self.decision_report,
            "executive_plan": self.executive_plan,
            "delegation_plan": self.delegation_plan,
            "resource_plan": self.resource_plan,
        }
        for field_name, value in required_parts.items():
            if value is None:
                msg = f"{field_name} is required."
                raise ValueError(msg)

        if not self.summary.strip():
            msg = "summary must not be empty."
            raise ValueError(msg)

    def to_markdown(self) -> str:
        """Return the full CEO operating plan as Markdown."""
        return (
            "# CEO Operating Plan\n\n"
            f"## Summary\n\n{self.summary}\n\n"
            "## Business Intelligence Report\n\n"
            f"{self.business_report.to_markdown()}\n\n"
            "## Executive Decision Report\n\n"
            f"{self.decision_report.to_markdown()}\n\n"
            "## Executive Plan\n\n"
            f"{self.executive_plan.to_markdown()}\n\n"
            "## Delegation Plan\n\n"
            f"{self.delegation_plan.to_markdown()}\n\n"
            "## Resource Plan\n\n"
            f"{self.resource_plan.to_markdown()}"
        )


@dataclass
class CompanyPriority:
    """A company priority proposed by the CEO agent."""

    title: str
    reason: str
    priority_score: float

    def __post_init__(self) -> None:
        """Validate company priority values."""
        if not 0.0 <= self.priority_score <= 1.0:
            msg = "priority_score must be between 0.0 and 1.0."
            raise ValueError(msg)


@dataclass
class ExecutiveDecision:
    """A strategic decision proposed by the CEO agent."""

    title: str
    rationale: str
    expected_impact: str
    confidence: float

    def __post_init__(self) -> None:
        """Validate executive decision values."""
        if not 0.0 <= self.confidence <= 1.0:
            msg = "confidence must be between 0.0 and 1.0."
            raise ValueError(msg)


@dataclass
class ExecutiveDecisionReport:
    """Structured CEO decision report."""

    company_status: str
    priorities: list[CompanyPriority]
    decisions: list[ExecutiveDecision]
    executive_summary: str
    generated_by: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        """Validate executive decision report values."""
        if not self.priorities:
            msg = "priorities must contain at least one CompanyPriority."
            raise ValueError(msg)

        if not self.decisions:
            msg = "decisions must contain at least one ExecutiveDecision."
            raise ValueError(msg)

    def to_markdown(self) -> str:
        """Return the executive decision report as Markdown."""
        priorities = "\n".join(
            (
                f"- {priority.title}: {priority.priority_score} "
                f"({priority.reason})"
            )
            for priority in self.priorities
        )
        decisions = "\n".join(
            (
                f"- {decision.title}: {decision.expected_impact} "
                f"(confidence: {decision.confidence})"
            )
            for decision in self.decisions
        )
        return (
            "# Executive Decision Report\n\n"
            f"Generated by: {self.generated_by}\n\n"
            f"Company Status: {self.company_status}\n\n"
            f"## Executive Summary\n\n{self.executive_summary}\n\n"
            f"## Priorities\n\n{priorities}\n\n"
            f"## Decisions\n\n{decisions}"
        )
