"""Core runtime orchestration for Helios."""

from dataclasses import dataclass, field
from typing import Any

from engine.events.bus import EventBus
from engine.events.event import Event
from engine.runtime.base_agent import BaseAgent
from engine.runtime.dispatcher import TaskDispatcher
from engine.runtime.registry import AgentRegistry
from engine.tasks.task import Task


@dataclass
class RuntimeHealth:
    """Structured health snapshot for the Helios runtime."""

    running: bool
    agent_count: int
    healthy_agents: list[str]
    unhealthy_agents: list[str]

    @property
    def healthy(self) -> bool:
        """Return whether the runtime and all registered agents are healthy."""
        return self.running and not self.unhealthy_agents


@dataclass
class HeliosRuntime:
    """Runtime that manages agents and submits tasks to them."""

    registry: AgentRegistry = field(default_factory=AgentRegistry)
    event_bus: EventBus = field(default_factory=EventBus)
    running: bool = False
    dispatcher: TaskDispatcher = field(init=False)

    def __post_init__(self) -> None:
        """Create a dispatcher that uses the runtime registry."""
        self.dispatcher = TaskDispatcher(self.registry)

    def register(self, agent: BaseAgent) -> None:
        """Register an agent with the runtime."""
        self.registry.register(agent)

    def unregister(self, agent_id: str) -> None:
        """Unregister an agent from the runtime."""
        self.registry.unregister(agent_id)

    def submit_task(self, task: Task) -> Any:
        """Submit a task to an agent.

        Version 1 performs a synchronous handoff through the dispatcher.
        """
        try:
            result = self.dispatcher.dispatch(task)
        except Exception as error:
            self.event_bus.publish(
                Event(
                    event_type="task.failed",
                    payload={
                        "task_id": task.task_id,
                        "required_capability": task.required_capability.value,
                        "priority": task.priority.value,
                        "error_message": task.error_message or str(error),
                    },
                    source="helios_runtime",
                ),
            )
            raise

        self.event_bus.publish(
            Event(
                event_type="task.dispatched",
                payload={
                    "task_id": task.task_id,
                    "required_capability": task.required_capability.value,
                    "priority": task.priority.value,
                },
                source="helios_runtime",
            ),
        )
        return result

    def start(self) -> None:
        """Start the runtime."""
        self.running = True
        self.event_bus.publish(
            Event(
                event_type="runtime.started",
                source="helios_runtime",
            ),
        )

    def stop(self) -> None:
        """Stop the runtime."""
        self.running = False
        self.event_bus.publish(
            Event(
                event_type="runtime.stopped",
                source="helios_runtime",
            ),
        )

    def inspect_health(self) -> RuntimeHealth:
        """Return a structured health snapshot for the runtime."""
        healthy_agents: list[str] = []
        unhealthy_agents: list[str] = []

        for agent in self.registry.all():
            if agent.health_check():
                healthy_agents.append(agent.agent_id)
            else:
                unhealthy_agents.append(agent.agent_id)

        return RuntimeHealth(
            running=self.running,
            agent_count=self.registry.count(),
            healthy_agents=healthy_agents,
            unhealthy_agents=unhealthy_agents,
        )

    def health_check(self) -> bool:
        """Return whether the runtime and registered agents are healthy."""
        return self.inspect_health().healthy
