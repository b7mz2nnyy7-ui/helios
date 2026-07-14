"""Operations monitor coordinating runtime, supervision and alerts."""

from typing import Any

from engine.alerts.service import AlertService
from engine.retries.coordinator import RetryCoordinator
from engine.runtime.runtime import HeliosRuntime
from engine.supervision.models import SupervisorReport
from engine.supervision.supervisor import SystemSupervisor
from engine.tasks.task import Task


class OperationsMonitor:
    """Coordinates runtime lifecycle, system supervision and alert collection."""

    def __init__(
        self,
        runtime: HeliosRuntime,
        supervisor: SystemSupervisor,
        alert_service: AlertService,
        retry_coordinator: RetryCoordinator | None = None,
    ) -> None:
        """Create an operations monitor from shared runtime services."""
        self._validate_consistency(
            runtime,
            supervisor,
            alert_service,
            retry_coordinator,
        )
        self.runtime = runtime
        self.supervisor = supervisor
        self.alert_service = alert_service
        self.retry_coordinator = retry_coordinator
        self.running = False

    def start(self) -> None:
        """Start alerting and then start the runtime if needed."""
        if self.running:
            return

        self.alert_service.start()
        if not self.runtime.running:
            self.runtime.start()

        self.running = True

    def inspect(self) -> SupervisorReport:
        """Inspect the system through the supervisor."""
        if not self.running:
            msg = "OperationsMonitor must be started before inspect()."
            raise RuntimeError(msg)

        return self.supervisor.inspect()

    def retry_task(self, task: Task) -> Any:
        """Retry a failed task through the configured retry coordinator."""
        if not self.running:
            msg = "OperationsMonitor must be started before retry_task()."
            raise RuntimeError(msg)

        if self.retry_coordinator is None:
            msg = "OperationsMonitor has no RetryCoordinator configured."
            raise RuntimeError(msg)

        return self.retry_coordinator.retry(task)

    def stop(self) -> None:
        """Stop the runtime and then stop alerting."""
        if self.runtime.running:
            self.runtime.stop()

        self.alert_service.stop()
        self.running = False

    def _validate_consistency(
        self,
        runtime: HeliosRuntime,
        supervisor: SystemSupervisor,
        alert_service: AlertService,
        retry_coordinator: RetryCoordinator | None,
    ) -> None:
        if supervisor.runtime is not runtime:
            msg = "Supervisor must use the same runtime instance as the monitor."
            raise ValueError(msg)

        if supervisor.event_bus is not runtime.event_bus:
            msg = "Supervisor must use the runtime event bus."
            raise ValueError(msg)

        if alert_service.event_bus is not runtime.event_bus:
            msg = "AlertService must use the runtime event bus."
            raise ValueError(msg)

        if retry_coordinator is not None and retry_coordinator.runtime is not runtime:
            msg = "RetryCoordinator must use the same runtime instance as the monitor."
            raise ValueError(msg)
