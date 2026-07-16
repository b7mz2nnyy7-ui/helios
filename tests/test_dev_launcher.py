"""Tests for the one-command local Helios development launcher."""

from collections.abc import Mapping, Sequence
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
import unittest

from config.dev import DevConfig
from engine.guardian.models import (
    CheckStatus,
    GuardianStatus,
    Severity,
    SystemCheckResult,
    SystemHealthReport,
)
from scripts.dev_launcher import (
    DevLauncher,
    LaunchResult,
    LauncherError,
    ProcessHandle,
    find_available_port,
    format_summary,
    process_group_options,
    terminate_process_tree,
    validate_python_version,
)


class FakeProcess:
    """Small process double with explicit lifecycle state."""

    def __init__(self, pid: int, return_code: int | None = None) -> None:
        self.pid = pid
        self.return_code = return_code
        self.signals: list[int] = []
        self.killed = False
        self.waited = False

    def poll(self) -> int | None:
        """Return the configured lifecycle state."""
        return self.return_code

    def wait(self, timeout: float | None = None) -> int:
        """Mark the process as reaped and return its exit code."""
        del timeout
        self.waited = True
        if self.return_code is None:
            self.return_code = 0
        return self.return_code

    def send_signal(self, sig: int) -> None:
        """Record a simulated process signal."""
        self.signals.append(sig)
        self.return_code = 0

    def kill(self) -> None:
        """Record an immediate simulated termination."""
        self.killed = True
        self.return_code = -9


def fake_http_payload(url: str) -> bytes:
    """Return deterministic local readiness and guardian responses."""
    if url.endswith("/api/videos"):
        return b'[{"id":"video-1"}]'
    if url.endswith("/health"):
        return b'{"status":"ok"}'
    return b'<html><div id="root"></div></html>'


def guardian_report(status: GuardianStatus) -> SystemHealthReport:
    """Create one launcher-focused guardian report."""
    check_status = {
        GuardianStatus.HEALTHY: CheckStatus.PASS,
        GuardianStatus.DEGRADED: CheckStatus.WARNING,
        GuardianStatus.UNHEALTHY: CheckStatus.FAIL,
    }[status]
    severity = (
        Severity.CRITICAL
        if status is GuardianStatus.UNHEALTHY
        else Severity.HIGH
    )
    check = SystemCheckResult(
        id="backend_api",
        name="Backend",
        severity=severity,
        status=check_status,
        summary="Launcher guardian check.",
    )
    counters = {
        candidate: int(candidate is check_status) for candidate in CheckStatus
    }
    return SystemHealthReport(
        guardian_version="0.1.0",
        overall_status=status,
        checks=(check,),
        counters=counters,
        summary="Launcher guardian report.",
    )


class LauncherTestCase(unittest.TestCase):
    """Tests for deterministic startup, readiness, and shutdown."""

    def test_dev_config_has_requested_defaults(self) -> None:
        """Backend, frontend, and browser defaults live in one config model."""
        config = DevConfig()

        self.assertEqual(config.backend_port, 8001)
        self.assertEqual(config.frontend_port, 5173)
        self.assertTrue(config.open_browser)

    def test_python_version_requires_312(self) -> None:
        """The direct Python entry point rejects unsupported interpreters."""
        with self.assertRaisesRegex(LauncherError, "Python 3.12"):
            validate_python_version((3, 11))

        validate_python_version((3, 12))

    def test_missing_node_or_npm_is_reported(self) -> None:
        """Dependency checks provide a clear missing-tool error."""
        launcher = DevLauncher(executable_finder=lambda name: None)

        with self.assertRaisesRegex(LauncherError, "Node, npm"):
            launcher.check_dependencies()

    def test_port_switches_when_preferred_port_is_occupied(self) -> None:
        """An occupied configured port causes deterministic upward fallback."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as occupied:
            occupied.bind(("127.0.0.1", 0))
            port = occupied.getsockname()[1]

            selected = find_available_port("127.0.0.1", port)

        self.assertGreater(selected, port)

    def test_process_group_options_cover_posix_and_windows(self) -> None:
        """Launcher isolates child trees on all supported OS families."""
        self.assertEqual(
            process_group_options("posix"),
            {"start_new_session": True},
        )
        self.assertIn("creationflags", process_group_options("nt"))

    def test_windows_shutdown_signals_and_reaps_process_group(self) -> None:
        """The Windows path uses its process-group signal and waits."""
        process = FakeProcess(99)

        terminate_process_tree(process, 1.0, "nt")

        self.assertEqual(len(process.signals), 1)
        self.assertTrue(process.waited)
        self.assertIsNotNone(process.poll())

    def test_launcher_starts_backend_frontend_and_browser(self) -> None:
        """One start call coordinates both services and the dashboard."""
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "frontend" / "node_modules").mkdir(parents=True)
            commands: list[tuple[Sequence[str], Path, Mapping[str, str]]] = []
            processes = [FakeProcess(101), FakeProcess(102)]
            opened_urls: list[str] = []

            def start_process(
                command: Sequence[str],
                cwd: Path,
                environment: Mapping[str, str],
            ) -> FakeProcess:
                commands.append((command, cwd, environment))
                return processes[len(commands) - 1]

            def open_browser(url: str) -> bool:
                opened_urls.append(url)
                return True

            terminated: list[ProcessHandle] = []
            launcher = DevLauncher(
                config=DevConfig(backend_port=42101, frontend_port=42102),
                project_root=root,
                process_starter=start_process,
                process_terminator=lambda process, timeout: terminated.append(process),
                http_getter=fake_http_payload,
                browser_opener=open_browser,
                executable_finder=lambda name: f"/tools/{name}",
            )

            result = launcher.start()

            self.assertEqual(result.video_count, 1)
            self.assertEqual(
                result.guardian_report.overall_status,
                GuardianStatus.DEGRADED,
            )
            self.assertEqual(result.dashboard_url, opened_urls[0])
            self.assertIn("apps.api.app:app", commands[0][0])
            self.assertEqual(commands[0][1], root)
            self.assertEqual(commands[1][1], root / "frontend")
            self.assertEqual(
                commands[1][2]["HELIOS_API_TARGET"],
                result.backend_url,
            )
            self.assertIn("--strictPort", commands[1][0])

            launcher.shutdown()

            self.assertEqual(terminated, [processes[1], processes[0]])

    def test_frontend_dependencies_install_only_when_missing(self) -> None:
        """npm install runs once only for a fresh frontend checkout."""
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "frontend").mkdir()
            calls: list[tuple[Sequence[str], Path]] = []
            launcher = DevLauncher(
                project_root=root,
                command_runner=lambda command, cwd: calls.append((command, cwd)),
            )

            launcher._ensure_frontend_dependencies("/tools/npm")
            (root / "frontend" / "node_modules").mkdir()
            launcher._ensure_frontend_dependencies("/tools/npm")

            self.assertEqual(
                calls,
                [(("/tools/npm", "install"), root / "frontend")],
            )

    def test_frontend_setup_failure_stops_started_backend(self) -> None:
        """A failed npm install cleans up the already running backend."""
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "frontend").mkdir()
            backend = FakeProcess(150)
            terminated: list[ProcessHandle] = []

            def fail_install(command: Sequence[str], cwd: Path) -> None:
                del cwd
                raise subprocess.CalledProcessError(1, command)

            launcher = DevLauncher(
                config=DevConfig(backend_port=42301, frontend_port=42302),
                project_root=root,
                process_starter=lambda command, cwd, environment: backend,
                command_runner=fail_install,
                process_terminator=lambda process, timeout: terminated.append(process),
                http_getter=lambda url: b"[]",
                executable_finder=lambda name: f"/tools/{name}",
            )

            with self.assertRaisesRegex(LauncherError, "installation failed"):
                launcher.start()

            self.assertEqual(terminated, [backend])

    def test_backend_exit_before_ready_is_reported(self) -> None:
        """A failed backend never produces a false READY state."""
        launcher = DevLauncher(http_getter=lambda url: b"[]")
        process = FakeProcess(201, return_code=3)

        with self.assertRaisesRegex(LauncherError, "Backend exited"):
            launcher._wait_for_backend(process, "http://127.0.0.1:8001")

    def test_frontend_readiness_requires_application_root(self) -> None:
        """A generic HTTP response is not mistaken for the React app."""
        launcher = DevLauncher(http_getter=lambda url: b"<html></html>")

        with self.assertRaisesRegex(LauncherError, "application root"):
            launcher._wait_for_frontend(
                FakeProcess(301),
                "http://127.0.0.1:5173/videos",
            )

    def test_shutdown_reaps_every_managed_process(self) -> None:
        """Shutdown leaves no owned fake process running or unreaped."""
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "frontend" / "node_modules").mkdir(parents=True)
            processes = [FakeProcess(401), FakeProcess(402)]
            starts = 0

            def start_process(
                command: Sequence[str],
                cwd: Path,
                environment: Mapping[str, str],
            ) -> FakeProcess:
                nonlocal starts
                del command, cwd, environment
                process = processes[starts]
                starts += 1
                return process

            def terminate(process: ProcessHandle, timeout: float) -> None:
                del timeout
                process.send_signal(signal.SIGTERM)
                process.wait()

            launcher = DevLauncher(
                config=DevConfig(
                    backend_port=42201,
                    frontend_port=42202,
                    open_browser=False,
                ),
                project_root=root,
                process_starter=start_process,
                process_terminator=terminate,
                http_getter=fake_http_payload,
                executable_finder=lambda name: f"/tools/{name}",
            )
            launcher.start()

            launcher.shutdown()

            self.assertTrue(all(process.poll() is not None for process in processes))
            self.assertTrue(all(process.waited for process in processes))

    def test_browser_can_be_disabled_without_affecting_readiness(self) -> None:
        """Headless local environments can keep automatic browser opening off."""
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "frontend" / "node_modules").mkdir(parents=True)
            processes = [FakeProcess(501), FakeProcess(502)]
            starts = 0

            def start_process(
                command: Sequence[str],
                cwd: Path,
                environment: Mapping[str, str],
            ) -> FakeProcess:
                nonlocal starts
                del command, cwd, environment
                process = processes[starts]
                starts += 1
                return process

            launcher = DevLauncher(
                config=DevConfig(
                    backend_port=42401,
                    frontend_port=42402,
                    open_browser=False,
                ),
                project_root=root,
                process_starter=start_process,
                process_terminator=lambda process, timeout: None,
                http_getter=fake_http_payload,
                browser_opener=lambda url: self.fail("browser was opened"),
                executable_finder=lambda name: f"/tools/{name}",
            )

            result = launcher.start()

            self.assertFalse(result.browser_opened)
            launcher.shutdown()

    def test_unhealthy_argus_report_stops_launcher_before_browser(self) -> None:
        """Only an unhealthy ARGUS report aborts startup and cleans processes."""
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "frontend" / "node_modules").mkdir(parents=True)
            processes = [FakeProcess(601), FakeProcess(602)]
            starts = 0
            terminated: list[ProcessHandle] = []

            def start_process(
                command: Sequence[str],
                cwd: Path,
                environment: Mapping[str, str],
            ) -> FakeProcess:
                nonlocal starts
                del command, cwd, environment
                process = processes[starts]
                starts += 1
                return process

            launcher = DevLauncher(
                config=DevConfig(backend_port=42501, frontend_port=42502),
                project_root=root,
                process_starter=start_process,
                process_terminator=lambda process, timeout: terminated.append(process),
                http_getter=fake_http_payload,
                browser_opener=lambda url: self.fail("browser was opened"),
                executable_finder=lambda name: f"/tools/{name}",
                guardian_inspector=lambda backend, frontend, process: guardian_report(
                    GuardianStatus.UNHEALTHY,
                ),
            )

            with self.assertRaisesRegex(LauncherError, "UNHEALTHY"):
                launcher.start()

            self.assertEqual(terminated, [processes[1], processes[0]])

    @unittest.skipIf(os.name == "nt", "POSIX process-group assertion")
    def test_posix_shutdown_terminates_child_process_group(self) -> None:
        """A real parent and child process group is terminated and reaped."""
        command = (
            sys.executable,
            "-c",
            (
                "import subprocess,sys,time;"
                "subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)']);"
                "time.sleep(60)"
            ),
        )
        process = subprocess.Popen(command, start_new_session=True)
        process_group = os.getpgid(process.pid)
        time.sleep(0.05)

        try:
            terminate_process_tree(process, 1.0, "posix")
            self.assertIsNotNone(process.poll())
            for _ in range(20):
                try:
                    os.killpg(process_group, 0)
                except ProcessLookupError:
                    break
                time.sleep(0.05)
            else:
                self.fail("Child process group still exists after shutdown.")
        finally:
            try:
                os.killpg(process_group, signal.SIGKILL)
            except ProcessLookupError:
                pass
            if process.poll() is None:
                process.kill()
            process.wait(timeout=1.0)

    def test_console_summary_contains_ready_state(self) -> None:
        """The launcher prints the requested concise operational summary."""
        result = LaunchResult(
            backend_url="http://127.0.0.1:8001",
            frontend_url="http://127.0.0.1:5173",
            dashboard_url="http://127.0.0.1:5173/videos",
            video_count=1,
            browser_opened=True,
            guardian_report=guardian_report(GuardianStatus.HEALTHY),
        )

        summary = format_summary(result)

        self.assertIn("HELIOS DEV", summary)
        self.assertIn("Backend      \u2713", summary)
        self.assertIn("Frontend     \u2713", summary)
        self.assertIn("Browser      \u2713", summary)
        self.assertIn("API          \u2713", summary)
        self.assertIn("Videos       1 gefunden", summary)
        self.assertIn("ARGUS", summary)
        self.assertIn("Overall      HEALTHY", summary)
        self.assertIn(result.dashboard_url, summary)


if __name__ == "__main__":
    unittest.main()
