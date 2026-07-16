"""ARGUS guardian composition and system report generation."""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from engine.alerts.service import AlertService
from engine.guardian.checks import (
    AgentRegistryCheck,
    AlertServiceCheck,
    BackendApiCheck,
    FrontendCheck,
    GuardianHTTPClient,
    HealthEndpointCheck,
    OperationsMonitorCheck,
    OutputDirectoryCheck,
    PipelineCheck,
    ProviderConfigCheck,
    ProviderRegistryCheck,
    RenderQueueCheck,
    RuntimeCheck,
    StorageCheck,
    SupervisorCheck,
    VideoScannerCheck,
)
from engine.guardian.models import (
    CheckStatus,
    GuardianStatus,
    Severity,
    SystemCheckResult,
    SystemHealthReport,
)
from engine.guardian.registry import GuardianRegistry
from engine.media.providers.config import ProviderConfig
from engine.media.providers.registry import MediaProviderRegistry
from engine.media.render_job import RenderJob
from engine.media.scanner import MediaStorageScanner
from engine.media.storage import DEFAULT_MEDIA_OUTPUT_DIRECTORY
from engine.operations.monitor import OperationsMonitor
from engine.runtime.registry import AgentRegistry
from engine.runtime.runtime import HeliosRuntime
from engine.supervision.supervisor import SystemSupervisor

ARGUS_VERSION = "0.1.0"


@dataclass(frozen=True)
class GuardianContext:
    """Explicit read-only dependencies available to standard ARGUS checks."""

    runtime: HeliosRuntime | None = None
    runtime_probe: Callable[[], bool] | None = None
    agent_registry: AgentRegistry | None = None
    supervisor: SystemSupervisor | None = None
    operations_monitor: OperationsMonitor | None = None
    alert_service: AlertService | None = None
    provider_registry: MediaProviderRegistry | None = None
    provider_configs: Mapping[str, ProviderConfig] | None = None
    output_directory: Path = DEFAULT_MEDIA_OUTPUT_DIRECTORY
    video_scanner: MediaStorageScanner | None = None
    last_pipeline: object | None = None
    backend_url: str | None = None
    frontend_url: str | None = None
    http_client: GuardianHTTPClient | None = None
    render_queue: Sequence[RenderJob] | None = None


class ArgusGuardian:
    """Run registered observations and produce one system health report."""

    def __init__(
        self,
        registry: GuardianRegistry,
        version: str = ARGUS_VERSION,
    ) -> None:
        """Create ARGUS from an explicit, isolated check registry."""
        if not version.strip():
            msg = "version must not be empty."
            raise ValueError(msg)
        self.registry = registry
        self.version = version

    def inspect(self) -> SystemHealthReport:
        """Execute all checks and return a deterministic health report."""
        checks: tuple[SystemCheckResult, ...] = tuple(self.registry.run_all())
        counters = {
            status: sum(check.status is status for check in checks)
            for status in CheckStatus
        }
        overall_status = _overall_status(checks)
        summary = (
            f"ARGUS completed {len(checks)} checks: "
            f"{counters[CheckStatus.PASS]} passed, "
            f"{counters[CheckStatus.WARNING]} warning, "
            f"{counters[CheckStatus.FAIL]} failed, "
            f"{counters[CheckStatus.SKIPPED]} skipped."
        )
        return SystemHealthReport(
            guardian_version=self.version,
            overall_status=overall_status,
            checks=checks,
            counters=counters,
            summary=summary,
        )


def create_guardian(context: GuardianContext | None = None) -> ArgusGuardian:
    """Create ARGUS with all standard checks and no global state."""
    selected = context or GuardianContext()
    scanner = selected.video_scanner or MediaStorageScanner(
        selected.output_directory,
    )
    registry = GuardianRegistry()
    for check in (
        RuntimeCheck(selected.runtime, selected.runtime_probe),
        AgentRegistryCheck(selected.agent_registry),
        SupervisorCheck(selected.supervisor),
        OperationsMonitorCheck(selected.operations_monitor),
        AlertServiceCheck(selected.alert_service),
        ProviderRegistryCheck(selected.provider_registry),
        ProviderConfigCheck(selected.provider_configs),
        StorageCheck(selected.output_directory),
        VideoScannerCheck(scanner),
        PipelineCheck(selected.last_pipeline),
        BackendApiCheck(selected.http_client, selected.backend_url),
        FrontendCheck(selected.http_client, selected.frontend_url),
        RenderQueueCheck(selected.render_queue),
        OutputDirectoryCheck(selected.output_directory),
        HealthEndpointCheck(selected.http_client, selected.backend_url),
    ):
        registry.register(check)
    return ArgusGuardian(registry)


def _overall_status(checks: tuple[SystemCheckResult, ...]) -> GuardianStatus:
    if any(
        check.status is CheckStatus.FAIL and check.severity is Severity.CRITICAL
        for check in checks
    ):
        return GuardianStatus.UNHEALTHY
    if any(
        check.status in {CheckStatus.WARNING, CheckStatus.FAIL}
        for check in checks
    ):
        return GuardianStatus.DEGRADED
    return GuardianStatus.HEALTHY
