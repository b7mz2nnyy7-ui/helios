"""Deterministic system supervisor for Helios."""

from engine.events.bus import EventBus
from engine.events.event import Event
from engine.runtime.base_agent import BaseAgent
from engine.runtime.runtime import HeliosRuntime
from engine.supervision.models import (
    AgentHealthReport,
    SupervisorReport,
    SupervisorStatus,
)


class SystemSupervisor:
    """Inspects runtime and agent health without mutating system state."""

    def __init__(
        self,
        runtime: HeliosRuntime,
        event_bus: EventBus | None = None,
    ) -> None:
        """Create a supervisor for a Helios runtime."""
        self.runtime = runtime
        self.event_bus = event_bus

    def inspect(self) -> SupervisorReport:
        """Return a structured report for runtime and registered agent health."""
        agent_reports = [
            self._inspect_agent(agent) for agent in self.runtime.registry.all()
        ]
        healthy_agents = sum(1 for report in agent_reports if report.healthy)
        unhealthy_agents = len(agent_reports) - healthy_agents

        report = SupervisorReport(
            status=self._resolve_status(
                runtime_running=self.runtime.running,
                unhealthy_agents=unhealthy_agents,
            ),
            runtime_running=self.runtime.running,
            agent_reports=agent_reports,
            total_agents=len(agent_reports),
            healthy_agents=healthy_agents,
            unhealthy_agents=unhealthy_agents,
        )
        self._publish_report(report)
        return report

    def _inspect_agent(self, agent: BaseAgent) -> AgentHealthReport:
        try:
            healthy = bool(agent.health_check())
        except Exception:
            healthy = False

        return AgentHealthReport(
            agent_id=agent.agent_id,
            name=agent.name,
            healthy=healthy,
            status=agent.status,
        )

    def _resolve_status(
        self,
        runtime_running: bool,
        unhealthy_agents: int,
    ) -> SupervisorStatus:
        if not runtime_running:
            return SupervisorStatus.UNHEALTHY

        if unhealthy_agents > 0:
            return SupervisorStatus.DEGRADED

        return SupervisorStatus.HEALTHY

    def _publish_report(self, report: SupervisorReport) -> None:
        if self.event_bus is None:
            return

        self.event_bus.publish(
            Event(
                event_type=self._event_type_for(report.status),
                payload={
                    "status": report.status.value,
                    "runtime_running": report.runtime_running,
                    "total_agents": report.total_agents,
                    "healthy_agents": report.healthy_agents,
                    "unhealthy_agents": report.unhealthy_agents,
                },
                source="system_supervisor",
            ),
        )

    def _event_type_for(self, status: SupervisorStatus) -> str:
        event_types = {
            SupervisorStatus.HEALTHY: "supervisor.healthy",
            SupervisorStatus.DEGRADED: "supervisor.degraded",
            SupervisorStatus.UNHEALTHY: "supervisor.unhealthy",
        }
        return event_types[status]
