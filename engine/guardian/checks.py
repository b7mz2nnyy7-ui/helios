"""Deterministic, read-only system checks used by ARGUS."""

from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
import json
from pathlib import Path
import time
from types import MappingProxyType
from typing import Any, Protocol, cast
from urllib.request import Request, urlopen

from engine.alerts.service import AlertService
from engine.media.providers.config import ProviderConfig
from engine.media.providers.registry import MediaProviderRegistry
from engine.media.render_job import RenderJob, RenderJobStatus
from engine.media.scanner import MediaStorageScanner
from engine.media.storage import DEFAULT_MEDIA_OUTPUT_DIRECTORY
from engine.operations.monitor import OperationsMonitor
from engine.runtime.registry import AgentRegistry
from engine.runtime.runtime import HeliosRuntime
from engine.supervision.supervisor import SystemSupervisor
from engine.guardian.models import CheckStatus, Severity, SystemCheckResult


@dataclass(frozen=True)
class GuardianHTTPResponse:
    """Minimal immutable HTTP response consumed by guardian checks."""

    status_code: int
    body: bytes
    headers: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate and protect the HTTP response metadata."""
        if not 100 <= self.status_code <= 599:
            msg = "status_code must be between 100 and 599."
            raise ValueError(msg)
        if not isinstance(self.body, bytes):
            msg = "body must be bytes."
            raise ValueError(msg)
        protected_headers = MappingProxyType(dict(self.headers))
        object.__setattr__(
            self,
            "headers",
            cast(Mapping[str, str], protected_headers),
        )


class GuardianHTTPClient(Protocol):
    """Injected synchronous HTTP client used only for health observations."""

    def get(self, url: str) -> GuardianHTTPResponse:
        """Return one HTTP response without mutating remote state."""


class StandardLibraryGuardianHTTPClient:
    """Small standard-library HTTP client for local guardian checks."""

    def __init__(self, timeout_seconds: float = 2.0) -> None:
        """Create a read-only HTTP client with a finite timeout."""
        if timeout_seconds <= 0:
            msg = "timeout_seconds must be greater than 0."
            raise ValueError(msg)
        self.timeout_seconds = timeout_seconds

    def get(self, url: str) -> GuardianHTTPResponse:
        """Execute one local GET request and return a bounded response."""
        request = Request(url, headers={"Accept": "application/json"}, method="GET")
        with urlopen(request, timeout=self.timeout_seconds) as response:
            return GuardianHTTPResponse(
                status_code=response.status,
                body=response.read(),
                headers=dict(response.headers.items()),
            )


class SystemCheck(Protocol):
    """Contract implemented by every ARGUS system check."""

    id: str
    name: str
    severity: Severity

    def run(self) -> SystemCheckResult:
        """Execute one deterministic, read-only check."""


@dataclass(frozen=True)
class CheckObservation:
    """Internal status returned by one check implementation."""

    status: CheckStatus
    summary: str
    details: Mapping[str, Any] = field(default_factory=dict)


class BaseGuardianCheck(ABC):
    """Measure and isolate one deterministic system observation."""

    id: str
    name: str
    severity: Severity

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        """Create a check with an injectable monotonic clock."""
        self._clock = clock

    def run(self) -> SystemCheckResult:
        """Execute the check and convert failures into secret-safe results."""
        started_at = self._clock()
        try:
            observation = self._inspect()
        except Exception as error:
            observation = CheckObservation(
                status=CheckStatus.FAIL,
                summary=f"{self.name} check failed.",
                details={"error_type": type(error).__name__},
            )
        duration = max(0.0, self._clock() - started_at)
        return SystemCheckResult(
            id=self.id,
            name=self.name,
            severity=self.severity,
            status=observation.status,
            summary=observation.summary,
            details=observation.details,
            duration_seconds=duration,
        )

    @abstractmethod
    def _inspect(self) -> CheckObservation:
        """Return the implementation-specific observation."""


class RuntimeCheck(BaseGuardianCheck):
    """Inspect the Helios runtime or an injected runtime liveness probe."""

    id = "runtime"
    name = "Runtime"
    severity = Severity.CRITICAL

    def __init__(
        self,
        runtime: HeliosRuntime | None = None,
        running_probe: Callable[[], bool] | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        super().__init__(clock)
        self.runtime = runtime
        self.running_probe = running_probe

    def _inspect(self) -> CheckObservation:
        if self.runtime is None and self.running_probe is None:
            return _skipped("Runtime is not configured for this inspection.")
        running = (
            self.runtime.running
            if self.runtime is not None
            else bool(self.running_probe and self.running_probe())
        )
        if not running:
            return CheckObservation(
                CheckStatus.FAIL,
                "Runtime is not running.",
                {"running": False},
            )
        return CheckObservation(
            CheckStatus.PASS,
            "Runtime is running.",
            {"running": True},
        )


class AgentRegistryCheck(BaseGuardianCheck):
    """Inspect registered agents without changing their state."""

    id = "agent_registry"
    name = "Agents"
    severity = Severity.HIGH

    def __init__(
        self,
        registry: AgentRegistry | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        super().__init__(clock)
        self.registry = registry

    def _inspect(self) -> CheckObservation:
        if self.registry is None:
            return _skipped("Agent registry is not configured.")
        agents = self.registry.all()
        unhealthy: list[str] = []
        for agent in agents:
            try:
                if not agent.health_check():
                    unhealthy.append(agent.agent_id)
            except Exception:
                unhealthy.append(agent.agent_id)
        details = {
            "total_agents": len(agents),
            "healthy_agents": len(agents) - len(unhealthy),
            "unhealthy_agents": tuple(unhealthy),
        }
        if unhealthy:
            return CheckObservation(
                CheckStatus.WARNING,
                f"{len(unhealthy)} registered agent(s) are unhealthy.",
                details,
            )
        return CheckObservation(
            CheckStatus.PASS,
            f"All {len(agents)} registered agent(s) are healthy.",
            details,
        )


class SupervisorCheck(BaseGuardianCheck):
    """Inspect supervisor wiring without triggering events."""

    id = "supervisor"
    name = "Supervisor"
    severity = Severity.HIGH

    def __init__(
        self,
        supervisor: SystemSupervisor | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        super().__init__(clock)
        self.supervisor = supervisor

    def _inspect(self) -> CheckObservation:
        if self.supervisor is None:
            return _skipped("System supervisor is not configured.")
        running = self.supervisor.runtime.running
        status = CheckStatus.PASS if running else CheckStatus.WARNING
        summary = "Supervisor runtime is available." if running else "Supervisor runtime is stopped."
        return CheckObservation(status, summary, {"runtime_running": running})


class OperationsMonitorCheck(BaseGuardianCheck):
    """Inspect operations monitor state without starting it."""

    id = "operations_monitor"
    name = "Operations Monitor"
    severity = Severity.HIGH

    def __init__(
        self,
        monitor: OperationsMonitor | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        super().__init__(clock)
        self.monitor = monitor

    def _inspect(self) -> CheckObservation:
        if self.monitor is None:
            return _skipped("Operations monitor is not configured.")
        if not self.monitor.running:
            return CheckObservation(
                CheckStatus.WARNING,
                "Operations monitor is stopped.",
                {"running": False},
            )
        return CheckObservation(
            CheckStatus.PASS,
            "Operations monitor is running.",
            {"running": True},
        )


class AlertServiceCheck(BaseGuardianCheck):
    """Inspect the alert service's accessible in-memory state."""

    id = "alert_service"
    name = "Alert Service"
    severity = Severity.MEDIUM

    def __init__(
        self,
        service: AlertService | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        super().__init__(clock)
        self.service = service

    def _inspect(self) -> CheckObservation:
        if self.service is None:
            return _skipped("Alert service is not configured.")
        count = self.service.count()
        if count != len(self.service.all()):
            return CheckObservation(
                CheckStatus.FAIL,
                "Alert service state is inconsistent.",
                {"alert_count": count},
            )
        return CheckObservation(
            CheckStatus.PASS,
            "Alert service state is accessible.",
            {"alert_count": count},
        )


class ProviderRegistryCheck(BaseGuardianCheck):
    """Inspect the provider registry without invoking providers."""

    id = "provider_registry"
    name = "Provider Registry"
    severity = Severity.MEDIUM

    def __init__(
        self,
        registry: MediaProviderRegistry | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        super().__init__(clock)
        self.registry = registry

    def _inspect(self) -> CheckObservation:
        if self.registry is None:
            return _skipped("Provider registry is not configured.")
        providers = self.registry.all()
        if not providers:
            return _skipped("No media providers are registered.", {"provider_count": 0})
        return CheckObservation(
            CheckStatus.PASS,
            f"{len(providers)} media provider(s) are registered.",
            {
                "provider_count": len(providers),
                "provider_ids": tuple(provider.provider_id for provider in providers),
            },
        )


class ProviderConfigCheck(BaseGuardianCheck):
    """Inspect provider configuration without exposing or using API keys."""

    id = "provider_config"
    name = "Provider Configuration"
    severity = Severity.HIGH

    def __init__(
        self,
        configs: Mapping[str, ProviderConfig] | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        super().__init__(clock)
        self.configs = None if configs is None else dict(configs)

    def _inspect(self) -> CheckObservation:
        if not self.configs:
            return _skipped("No provider configurations are loaded.")
        enabled = [config for config in self.configs.values() if config.enabled]
        missing_keys = [
            config.provider_id
            for config in enabled
            if config.api_key is None or not config.api_key.strip()
        ]
        missing_models = [
            config.provider_id
            for config in enabled
            if config.model is None or not config.model.strip()
        ]
        details = {
            "configured_providers": len(self.configs),
            "enabled_providers": len(enabled),
            "missing_api_key_for": tuple(missing_keys),
            "missing_model_for": tuple(missing_models),
        }
        if missing_keys or missing_models:
            return CheckObservation(
                CheckStatus.WARNING,
                "One or more enabled providers are not ready.",
                details,
            )
        return CheckObservation(
            CheckStatus.PASS,
            "All enabled provider configurations are ready.",
            details,
        )


class StorageCheck(BaseGuardianCheck):
    """Inspect existing video files without writing or downloading data."""

    id = "storage"
    name = "Storage"
    severity = Severity.HIGH

    def __init__(
        self,
        output_directory: Path = DEFAULT_MEDIA_OUTPUT_DIRECTORY,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        super().__init__(clock)
        self.output_directory = output_directory

    def _inspect(self) -> CheckObservation:
        if not self.output_directory.is_dir():
            return CheckObservation(
                CheckStatus.FAIL,
                "Video storage directory is unavailable.",
                {"directory_exists": self.output_directory.exists()},
            )
        videos = [
            path
            for path in self.output_directory.glob("*.mp4")
            if path.is_file() and not path.is_symlink()
        ]
        unreadable = []
        empty = []
        for video in videos:
            try:
                size = video.stat().st_size
                with video.open("rb") as video_file:
                    video_file.read(1)
            except OSError:
                unreadable.append(video.name)
                continue
            if size <= 0:
                empty.append(video.name)
        details = {
            "video_count": len(videos),
            "unreadable_count": len(unreadable),
            "empty_count": len(empty),
        }
        if unreadable or empty:
            return CheckObservation(
                CheckStatus.FAIL,
                "One or more stored videos are unreadable or empty.",
                details,
            )
        return CheckObservation(
            CheckStatus.PASS,
            f"{len(videos)} stored video(s) are readable.",
            details,
        )


class VideoScannerCheck(BaseGuardianCheck):
    """Inspect the filesystem scanner and its current video inventory."""

    id = "video_scanner"
    name = "Video Scanner"
    severity = Severity.MEDIUM

    def __init__(
        self,
        scanner: MediaStorageScanner | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        super().__init__(clock)
        self.scanner = scanner

    def _inspect(self) -> CheckObservation:
        if self.scanner is None:
            return _skipped("Video scanner is not configured.")
        videos = self.scanner.scan()
        return CheckObservation(
            CheckStatus.PASS,
            f"Video scanner found {len(videos)} video(s).",
            {
                "video_count": len(videos),
                "total_size_bytes": sum(video.size_bytes for video in videos),
            },
        )


class PipelineCheck(BaseGuardianCheck):
    """Inspect the last pipeline result without running a new pipeline."""

    id = "pipeline"
    name = "Pipeline"
    severity = Severity.HIGH

    def __init__(
        self,
        last_pipeline: object | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        super().__init__(clock)
        self.last_pipeline = last_pipeline

    def _inspect(self) -> CheckObservation:
        if self.last_pipeline is None:
            return _skipped("No completed pipeline result is available.")
        render_job = getattr(self.last_pipeline, "render_job", None)
        completed_task_ids = getattr(self.last_pipeline, "completed_task_ids", None)
        if not isinstance(render_job, RenderJob) or not isinstance(
            completed_task_ids,
            list,
        ):
            return CheckObservation(
                CheckStatus.FAIL,
                "Last pipeline result is structurally invalid.",
            )
        status = (
            CheckStatus.FAIL
            if render_job.status is RenderJobStatus.FAILED
            else CheckStatus.PASS
        )
        return CheckObservation(
            status,
            f"Last pipeline render job is {render_job.status.value}.",
            {
                "completed_task_count": len(completed_task_ids),
                "render_job_id": render_job.job_id,
                "render_job_status": render_job.status.value,
                "has_media_asset": render_job.result_asset is not None,
            },
        )


class BackendApiCheck(BaseGuardianCheck):
    """Inspect the local video API through an injected HTTP client."""

    id = "backend_api"
    name = "Backend"
    severity = Severity.CRITICAL

    def __init__(
        self,
        client: GuardianHTTPClient | None = None,
        backend_url: str | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        super().__init__(clock)
        self.client = client
        self.backend_url = backend_url

    def _inspect(self) -> CheckObservation:
        if self.client is None or not self.backend_url:
            return _skipped("Backend API check is not configured.")
        response = self.client.get(_url(self.backend_url, "/api/videos"))
        if response.status_code != 200:
            return CheckObservation(
                CheckStatus.FAIL,
                f"Video API returned HTTP {response.status_code}.",
                {"status_code": response.status_code},
            )
        payload: object = json.loads(response.body)
        if not isinstance(payload, list):
            return CheckObservation(
                CheckStatus.FAIL,
                "Video API returned an invalid payload.",
            )
        return CheckObservation(
            CheckStatus.PASS,
            "Video API is healthy.",
            {"status_code": 200, "video_count": len(payload)},
        )


class FrontendCheck(BaseGuardianCheck):
    """Inspect the local frontend root and video route without a browser."""

    id = "frontend"
    name = "Frontend"
    severity = Severity.HIGH

    def __init__(
        self,
        client: GuardianHTTPClient | None = None,
        frontend_url: str | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        super().__init__(clock)
        self.client = client
        self.frontend_url = frontend_url

    def _inspect(self) -> CheckObservation:
        if self.client is None or not self.frontend_url:
            return _skipped("Frontend check is not configured.")
        responses = (
            self.client.get(_url(self.frontend_url, "/")),
            self.client.get(_url(self.frontend_url, "/videos")),
        )
        if any(response.status_code != 200 for response in responses):
            return CheckObservation(
                CheckStatus.FAIL,
                "Frontend route returned a non-success status.",
                {"status_codes": tuple(response.status_code for response in responses)},
            )
        if any(b'id="root"' not in response.body for response in responses):
            return CheckObservation(
                CheckStatus.FAIL,
                "Frontend HTML is missing the application root.",
            )
        return CheckObservation(
            CheckStatus.PASS,
            "Frontend root and video route are healthy.",
            {"checked_routes": ("/", "/videos")},
        )


class RenderQueueCheck(BaseGuardianCheck):
    """Inspect an optional render queue snapshot without consuming it."""

    id = "render_queue"
    name = "Render Queue"
    severity = Severity.MEDIUM

    def __init__(
        self,
        queue: Sequence[RenderJob] | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        super().__init__(clock)
        self.queue = queue

    def _inspect(self) -> CheckObservation:
        if self.queue is None:
            return _skipped("No render queue is configured.")
        jobs = tuple(self.queue)
        failed = sum(job.status is RenderJobStatus.FAILED for job in jobs)
        status = CheckStatus.WARNING if failed else CheckStatus.PASS
        summary = (
            f"Render queue contains {failed} failed job(s)."
            if failed
            else f"Render queue contains {len(jobs)} job(s)."
        )
        return CheckObservation(
            status,
            summary,
            {"job_count": len(jobs), "failed_jobs": failed},
        )


class OutputDirectoryCheck(BaseGuardianCheck):
    """Inspect whether the configured output directory can be read."""

    id = "output_directory"
    name = "Output Directory"
    severity = Severity.HIGH

    def __init__(
        self,
        output_directory: Path = DEFAULT_MEDIA_OUTPUT_DIRECTORY,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        super().__init__(clock)
        self.output_directory = output_directory

    def _inspect(self) -> CheckObservation:
        if not self.output_directory.exists():
            return CheckObservation(
                CheckStatus.FAIL,
                "Output directory does not exist.",
                {"exists": False},
            )
        if not self.output_directory.is_dir():
            return CheckObservation(
                CheckStatus.FAIL,
                "Output path is not a directory.",
                {"exists": True, "is_directory": False},
            )
        try:
            entry_count = sum(1 for _ in self.output_directory.iterdir())
        except OSError:
            return CheckObservation(
                CheckStatus.FAIL,
                "Output directory is not readable.",
                {"exists": True, "is_directory": True},
            )
        return CheckObservation(
            CheckStatus.PASS,
            "Output directory is readable.",
            {"entry_count": entry_count},
        )


class HealthEndpointCheck(BaseGuardianCheck):
    """Inspect the backend health endpoint through an injected client."""

    id = "health_endpoint"
    name = "Health Endpoint"
    severity = Severity.CRITICAL

    def __init__(
        self,
        client: GuardianHTTPClient | None = None,
        backend_url: str | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        super().__init__(clock)
        self.client = client
        self.backend_url = backend_url

    def _inspect(self) -> CheckObservation:
        if self.client is None or not self.backend_url:
            return _skipped("Health endpoint check is not configured.")
        response = self.client.get(_url(self.backend_url, "/health"))
        if response.status_code != 200:
            return CheckObservation(
                CheckStatus.FAIL,
                f"Health endpoint returned HTTP {response.status_code}.",
                {"status_code": response.status_code},
            )
        payload: object = json.loads(response.body)
        if not isinstance(payload, dict) or payload.get("status") != "ok":
            return CheckObservation(
                CheckStatus.FAIL,
                "Health endpoint returned an invalid status.",
            )
        return CheckObservation(
            CheckStatus.PASS,
            "Health endpoint is healthy.",
            {"status_code": 200},
        )


def _skipped(
    summary: str,
    details: Mapping[str, Any] | None = None,
) -> CheckObservation:
    return CheckObservation(CheckStatus.SKIPPED, summary, details or {})


def _url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"
