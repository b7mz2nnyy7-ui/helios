"""Tests for ARGUS standard read-only system checks."""

from collections.abc import Mapping
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from typing import Any
import unittest

from engine.guardian.checks import (
    AgentRegistryCheck,
    AlertServiceCheck,
    BackendApiCheck,
    FrontendCheck,
    GuardianHTTPResponse,
    HealthEndpointCheck,
    OperationsMonitorCheck,
    OutputDirectoryCheck,
    ProviderConfigCheck,
    ProviderRegistryCheck,
    RuntimeCheck,
    StorageCheck,
    SupervisorCheck,
    VideoScannerCheck,
)
from engine.guardian.guardian import GuardianContext, create_guardian
from engine.guardian.models import CheckStatus
from engine.media.providers.config import ProviderConfig
from engine.media.providers.mock_provider import MockVideoProvider
from engine.media.providers.registry import MediaProviderRegistry
from engine.media.scanner import MediaStorageScanner
from engine.alerts.service import AlertService
from engine.operations.monitor import OperationsMonitor
from engine.runtime.base_agent import BaseAgent
from engine.runtime.registry import AgentRegistry
from engine.runtime.runtime import HeliosRuntime
from engine.supervision.supervisor import SystemSupervisor
from engine.tasks.task import Task


class FakeHTTPClient:
    """Route-based HTTP client that never touches the network."""

    def __init__(self, responses: Mapping[str, GuardianHTTPResponse]) -> None:
        self.responses = dict(responses)
        self.requested_urls: list[str] = []

    def get(self, url: str) -> GuardianHTTPResponse:
        """Return the configured response for one URL."""
        self.requested_urls.append(url)
        return self.responses[url]


class HealthyAgent(BaseAgent):
    """Minimal healthy agent used for registry observations."""

    def run(self, task: Task) -> Any:
        """Return no task result."""
        del task
        return None


class UnhealthyAgent(HealthyAgent):
    """Agent double reporting unhealthy state."""

    def health_check(self) -> bool:
        """Report deterministic unhealthy state."""
        return False


class GuardianChecksTestCase(unittest.TestCase):
    """Tests for local observations, status mapping, and non-mutation."""

    def test_runtime_check_passes_fails_and_skips(self) -> None:
        """Runtime liveness maps directly to documented statuses."""
        self.assertEqual(
            RuntimeCheck(running_probe=lambda: True).run().status,
            CheckStatus.PASS,
        )
        self.assertEqual(
            RuntimeCheck(running_probe=lambda: False).run().status,
            CheckStatus.FAIL,
        )
        self.assertEqual(RuntimeCheck().run().status, CheckStatus.SKIPPED)

    def test_agent_registry_reports_unhealthy_agents_without_mutation(self) -> None:
        """Agent health is observed while registry order and state stay intact."""
        registry = AgentRegistry()
        healthy = HealthyAgent("healthy", "Healthy")
        unhealthy = UnhealthyAgent("unhealthy", "Unhealthy")
        registry.register(healthy)
        registry.register(unhealthy)
        before = registry.all()

        result = AgentRegistryCheck(registry).run()

        self.assertEqual(result.status, CheckStatus.WARNING)
        self.assertEqual(result.details["healthy_agents"], 1)
        self.assertEqual(registry.all(), before)

    def test_provider_config_checks_keys_without_exposing_them(self) -> None:
        """Provider readiness records booleans and IDs, never API keys."""
        secret = "provider-secret"
        ready = ProviderConfig(
            provider_id="ready",
            api_key=secret,
            model="video-model",
        )
        missing = ProviderConfig(provider_id="missing", model="video-model")

        result = ProviderConfigCheck({"ready": ready, "missing": missing}).run()

        self.assertEqual(result.status, CheckStatus.WARNING)
        self.assertNotIn(secret, str(result.details))
        self.assertEqual(result.details["missing_api_key_for"], ("missing",))

    def test_storage_reads_existing_files_without_writing(self) -> None:
        """Storage observation preserves file content and directory entries."""
        with TemporaryDirectory() as directory:
            output = Path(directory)
            video = output / "video.mp4"
            video.write_bytes(b"video-content")
            before = (tuple(output.iterdir()), video.read_bytes(), video.stat().st_mtime_ns)

            result = StorageCheck(output).run()

            after = (tuple(output.iterdir()), video.read_bytes(), video.stat().st_mtime_ns)
            self.assertEqual(result.status, CheckStatus.PASS)
            self.assertEqual(before, after)

    def test_storage_rejects_empty_video(self) -> None:
        """Zero-byte videos fail storage health without being modified."""
        with TemporaryDirectory() as directory:
            output = Path(directory)
            (output / "empty.mp4").touch()

            result = StorageCheck(output).run()

            self.assertEqual(result.status, CheckStatus.FAIL)
            self.assertEqual(result.details["empty_count"], 1)

    def test_backend_and_health_checks_use_injected_http_client(self) -> None:
        """Backend checks parse local contracts without real HTTP requests."""
        client = FakeHTTPClient(
            {
                "http://backend/api/videos": GuardianHTTPResponse(
                    200,
                    b'[{"id":"one"}]',
                ),
                "http://backend/health": GuardianHTTPResponse(
                    200,
                    b'{"status":"ok"}',
                ),
            },
        )

        backend = BackendApiCheck(client, "http://backend").run()
        health = HealthEndpointCheck(client, "http://backend").run()

        self.assertEqual(backend.status, CheckStatus.PASS)
        self.assertEqual(backend.details["video_count"], 1)
        self.assertEqual(health.status, CheckStatus.PASS)
        self.assertEqual(len(client.requested_urls), 2)

    def test_frontend_checks_root_and_video_html(self) -> None:
        """Frontend inspection validates both routes without a browser."""
        html = b'<html><div id="root"></div></html>'
        client = FakeHTTPClient(
            {
                "http://frontend/": GuardianHTTPResponse(200, html),
                "http://frontend/videos": GuardianHTTPResponse(200, html),
            },
        )

        result = FrontendCheck(client, "http://frontend").run()

        self.assertEqual(result.status, CheckStatus.PASS)
        self.assertEqual(
            client.requested_urls,
            ["http://frontend/", "http://frontend/videos"],
        )

    def test_malformed_http_payload_is_isolated_as_failure(self) -> None:
        """Invalid JSON becomes a safe failed result rather than escaping."""
        client = FakeHTTPClient(
            {
                "http://backend/api/videos": GuardianHTTPResponse(200, b"secret"),
            },
        )

        result = BackendApiCheck(client, "http://backend").run()

        self.assertEqual(result.status, CheckStatus.FAIL)
        self.assertEqual(result.details["error_type"], "JSONDecodeError")
        self.assertNotIn("secret", result.summary)

    def test_all_standard_checks_run_without_network_or_provider_calls(self) -> None:
        """Full ARGUS composition executes all checks against injected state."""
        with TemporaryDirectory() as directory:
            output = Path(directory)
            (output / "video.mp4").write_bytes(b"video")
            registry = MediaProviderRegistry()
            provider = MockVideoProvider()
            registry.register(provider)
            provider_config = ProviderConfig(
                provider_id=provider.provider_id,
                api_key="not-exposed",
                model="mock-model",
            )
            html = b'<html><div id="root"></div></html>'
            client = FakeHTTPClient(
                {
                    "http://backend/api/videos": GuardianHTTPResponse(200, b"[]"),
                    "http://backend/health": GuardianHTTPResponse(
                        200,
                        b'{"status":"ok"}',
                    ),
                    "http://frontend/": GuardianHTTPResponse(200, html),
                    "http://frontend/videos": GuardianHTTPResponse(200, html),
                },
            )
            context = GuardianContext(
                runtime_probe=lambda: True,
                agent_registry=AgentRegistry(),
                provider_registry=registry,
                provider_configs={provider.provider_id: provider_config},
                output_directory=output,
                backend_url="http://backend",
                frontend_url="http://frontend",
                http_client=client,
                render_queue=(),
                last_pipeline=None,
            )

            report = create_guardian(context).inspect()

        self.assertEqual(len(report.checks), 15)
        self.assertNotIn(CheckStatus.FAIL, {check.status for check in report.checks})
        self.assertEqual(len(client.requested_urls), 4)
        self.assertNotIn("not-exposed", report.to_json())

    def test_configured_component_checks_are_read_only(self) -> None:
        """Configured system services are observed without lifecycle changes."""
        with TemporaryDirectory() as directory:
            output = Path(directory)
            (output / "video.mp4").write_bytes(b"video")
            runtime = HeliosRuntime(running=True)
            supervisor = SystemSupervisor(runtime, runtime.event_bus)
            alerts = AlertService(runtime.event_bus)
            monitor = OperationsMonitor(runtime, supervisor, alerts)
            provider_registry = MediaProviderRegistry()
            provider_registry.register(MockVideoProvider())
            scanner = MediaStorageScanner(output)
            before = {
                "runtime_running": runtime.running,
                "monitor_running": monitor.running,
                "alert_count": alerts.count(),
                "provider_count": len(provider_registry.all()),
            }

            results = (
                SupervisorCheck(supervisor).run(),
                OperationsMonitorCheck(monitor).run(),
                AlertServiceCheck(alerts).run(),
                ProviderRegistryCheck(provider_registry).run(),
                VideoScannerCheck(scanner).run(),
                OutputDirectoryCheck(output).run(),
            )

            after = {
                "runtime_running": runtime.running,
                "monitor_running": monitor.running,
                "alert_count": alerts.count(),
                "provider_count": len(provider_registry.all()),
            }
        self.assertEqual(
            [result.status for result in results],
            [
                CheckStatus.PASS,
                CheckStatus.WARNING,
                CheckStatus.PASS,
                CheckStatus.PASS,
                CheckStatus.PASS,
                CheckStatus.PASS,
            ],
        )
        self.assertEqual(before, after)

    def test_pipeline_check_does_not_execute_pipeline_object(self) -> None:
        """Invalid snapshots are inspected structurally without method calls."""
        snapshot = SimpleNamespace(
            render_job="not-a-render-job",
            completed_task_ids=[],
            run=lambda: self.fail("pipeline was executed"),
        )

        report = create_guardian(
            GuardianContext(last_pipeline=snapshot, output_directory=Path("missing")),
        ).inspect()
        pipeline = next(check for check in report.checks if check.id == "pipeline")

        self.assertEqual(pipeline.status, CheckStatus.FAIL)


if __name__ == "__main__":
    unittest.main()
