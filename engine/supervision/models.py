"""Models for deterministic Helios supervision."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from engine.runtime.status import AgentStatus


class SupervisorStatus(StrEnum):
    """Overall status values produced by the system supervisor."""

    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"


@dataclass(frozen=True)
class AgentHealthReport:
    """Health report for one registered agent."""

    agent_id: str
    name: str
    healthy: bool
    status: AgentStatus


@dataclass(frozen=True)
class SupervisorReport:
    """Structured system health report produced by the supervisor."""

    status: SupervisorStatus
    runtime_running: bool
    agent_reports: list[AgentHealthReport]
    total_agents: int
    healthy_agents: int
    unhealthy_agents: int
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

