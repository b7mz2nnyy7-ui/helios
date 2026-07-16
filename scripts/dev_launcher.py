"""Start the complete local Helios development stack with one command."""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
import json
import math
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import time
from typing import Protocol
from urllib.request import urlopen
import webbrowser

from config.dev import DEV_CONFIG, DevConfig
from engine.guardian.checks import GuardianHTTPResponse
from engine.guardian.guardian import GuardianContext, create_guardian
from engine.guardian.models import (
    CheckStatus,
    GuardianStatus,
    SystemHealthReport,
)
from engine.media.providers.registry import MediaProviderRegistry
from engine.media.scanner import MediaStorageScanner
from engine.runtime.registry import AgentRegistry

PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SEPARATOR = "\u2500" * 26
_READY_MARK = "\u2713"


class LauncherError(RuntimeError):
    """Base error for controlled local launcher failures."""


class ProcessHandle(Protocol):
    """Minimal subprocess contract required by the launcher."""

    pid: int

    def poll(self) -> int | None:
        """Return the exit code or None while running."""

    def wait(self, timeout: float | None = None) -> int:
        """Wait for process termination and return its exit code."""

    def send_signal(self, sig: int) -> None:
        """Send one operating-system signal to the process."""

    def kill(self) -> None:
        """Terminate the process immediately."""


ProcessStarter = Callable[
    [Sequence[str], Path, Mapping[str, str]],
    ProcessHandle,
]
CommandRunner = Callable[[Sequence[str], Path], None]
ProcessTerminator = Callable[[ProcessHandle, float], None]
HTTPGetter = Callable[[str], bytes]
BrowserOpener = Callable[[str], bool]
ExecutableFinder = Callable[[str], str | None]
GuardianInspector = Callable[[str, str, ProcessHandle], SystemHealthReport]


@dataclass(frozen=True)
class RuntimeDependencies:
    """Resolved local executables needed by the development stack."""

    python: str
    node: str
    npm: str


@dataclass(frozen=True)
class LaunchResult:
    """Ready-state details for a successfully started development stack."""

    backend_url: str
    frontend_url: str
    dashboard_url: str
    video_count: int
    browser_opened: bool
    guardian_report: SystemHealthReport


@dataclass
class ManagedProcess:
    """Named subprocess owned by the launcher."""

    name: str
    handle: ProcessHandle


class LauncherGuardianHTTPClient:
    """Adapt the launcher's readiness GET function for ARGUS checks."""

    def __init__(self, getter: HTTPGetter) -> None:
        """Create an adapter around the existing local HTTP getter."""
        self._getter = getter

    def get(self, url: str) -> GuardianHTTPResponse:
        """Return a successful response or propagate the getter failure."""
        return GuardianHTTPResponse(status_code=200, body=self._getter(url))


def validate_python_version(version: tuple[int, int]) -> None:
    """Require Python 3.12 or newer for local Helios development."""
    if version < (3, 12):
        msg = "Python 3.12 or newer is required."
        raise LauncherError(msg)


def find_available_port(host: str, preferred_port: int) -> int:
    """Return the preferred TCP port or the next available local port."""
    if not host.strip():
        msg = "Host must not be empty."
        raise ValueError(msg)
    if not 1 <= preferred_port <= 65535:
        msg = "Port must be between 1 and 65535."
        raise ValueError(msg)

    for port in range(preferred_port, 65536):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as candidate:
            try:
                candidate.bind((host, port))
            except OSError:
                continue
            return port
    msg = f"No free TCP port found at or above {preferred_port}."
    raise LauncherError(msg)


def process_group_options(platform_name: str | None = None) -> dict[str, object]:
    """Return platform-specific subprocess isolation options."""
    selected_platform = platform_name or os.name
    if selected_platform == "nt":
        creation_flags = int(
            getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
        )
        return {"creationflags": creation_flags}
    return {"start_new_session": True}


def terminate_process_tree(
    process: ProcessHandle,
    timeout_seconds: float,
    platform_name: str | None = None,
) -> None:
    """Stop and reap one process group without leaving child processes."""
    if process.poll() is not None:
        process.wait()
        return

    selected_platform = platform_name or os.name
    if selected_platform == "nt":
        _terminate_windows_process_tree(process, timeout_seconds)
        return
    _terminate_posix_process_tree(process, timeout_seconds)


def _terminate_posix_process_tree(
    process: ProcessHandle,
    timeout_seconds: float,
) -> None:
    try:
        process_group = os.getpgid(process.pid)
        os.killpg(process_group, signal.SIGTERM)
    except ProcessLookupError:
        process.wait()
        return

    try:
        process.wait(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process_group, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(timeout=timeout_seconds)


def _terminate_windows_process_tree(
    process: ProcessHandle,
    timeout_seconds: float,
) -> None:
    break_signal = int(getattr(signal, "CTRL_BREAK_EVENT", signal.SIGTERM))
    try:
        process.send_signal(break_signal)
        process.wait(timeout=timeout_seconds)
        return
    except (OSError, subprocess.TimeoutExpired):
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    if process.poll() is None:
        process.kill()
    process.wait(timeout=timeout_seconds)


def _start_process(
    command: Sequence[str],
    cwd: Path,
    environment: Mapping[str, str],
) -> ProcessHandle:
    options = process_group_options()
    if os.name == "nt":
        creation_flags = int(
            getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
        )
        return subprocess.Popen(
            list(command),
            cwd=cwd,
            env=dict(environment),
            creationflags=creation_flags,
        )
    return subprocess.Popen(
        list(command),
        cwd=cwd,
        env=dict(environment),
        start_new_session=bool(options["start_new_session"]),
    )


def _run_command(command: Sequence[str], cwd: Path) -> None:
    subprocess.run(list(command), cwd=cwd, check=True)


def _http_get(url: str) -> bytes:
    with urlopen(url, timeout=1.0) as response:
        return response.read()


class DevLauncher:
    """Coordinate backend, frontend, readiness, browser, and shutdown."""

    def __init__(
        self,
        config: DevConfig = DEV_CONFIG,
        project_root: Path = PROJECT_ROOT,
        process_starter: ProcessStarter = _start_process,
        command_runner: CommandRunner = _run_command,
        process_terminator: ProcessTerminator = terminate_process_tree,
        http_getter: HTTPGetter = _http_get,
        browser_opener: BrowserOpener = webbrowser.open,
        executable_finder: ExecutableFinder = shutil.which,
        clock: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
        guardian_inspector: GuardianInspector | None = None,
    ) -> None:
        """Create an isolated launcher with injectable operating-system edges."""
        self.config = config
        self.project_root = project_root
        self.frontend_directory = project_root / "frontend"
        self._process_starter = process_starter
        self._command_runner = command_runner
        self._process_terminator = process_terminator
        self._http_getter = http_getter
        self._browser_opener = browser_opener
        self._executable_finder = executable_finder
        self._clock = clock
        self._sleeper = sleeper
        self._guardian_inspector = guardian_inspector or self._inspect_guardian
        self._processes: list[ManagedProcess] = []
        self._started = False

    def check_dependencies(self) -> RuntimeDependencies:
        """Validate Python, Node, and npm before starting any process."""
        validate_python_version((sys.version_info.major, sys.version_info.minor))
        python = sys.executable
        if not python or not Path(python).is_file():
            msg = "Python executable could not be resolved."
            raise LauncherError(msg)

        node = self._executable_finder("node")
        npm = self._executable_finder("npm")
        missing = [name for name, path in (("Node", node), ("npm", npm)) if not path]
        if missing:
            msg = f"Missing development dependency: {', '.join(missing)}."
            raise LauncherError(msg)
        if node is None or npm is None:
            msg = "Node and npm executables could not be resolved."
            raise LauncherError(msg)
        return RuntimeDependencies(python=python, node=node, npm=npm)

    def start(self) -> LaunchResult:
        """Start both services, wait for readiness, and open the dashboard."""
        if self._started:
            msg = "Helios development stack is already running."
            raise LauncherError(msg)

        dependencies = self.check_dependencies()
        try:
            backend_port = find_available_port(
                self.config.backend_host,
                self.config.backend_port,
            )
            backend_url = f"http://{self.config.backend_host}:{backend_port}"
            backend = self._spawn_backend(dependencies.python, backend_port)
            video_count = self._wait_for_backend(backend, backend_url)

            self._ensure_frontend_dependencies(dependencies.npm)
            frontend_port = find_available_port(
                self.config.frontend_host,
                self.config.frontend_port,
            )
            frontend_url = f"http://{self.config.frontend_host}:{frontend_port}"
            frontend = self._spawn_frontend(
                dependencies.npm,
                frontend_port,
                backend_url,
            )
            dashboard_url = f"{frontend_url}/videos"
            self._wait_for_frontend(frontend, dashboard_url)
            guardian_report = self._guardian_inspector(
                backend_url,
                frontend_url,
                backend,
            )
            if guardian_report.overall_status is GuardianStatus.UNHEALTHY:
                msg = "ARGUS reported an UNHEALTHY system state."
                raise LauncherError(msg)
            browser_opened = self._open_browser(dashboard_url)
        except Exception:
            self.shutdown()
            raise

        self._started = True
        return LaunchResult(
            backend_url=backend_url,
            frontend_url=frontend_url,
            dashboard_url=dashboard_url,
            video_count=video_count,
            browser_opened=browser_opened,
            guardian_report=guardian_report,
        )

    def wait(self) -> None:
        """Block until interrupted or one managed process exits."""
        if not self._started:
            msg = "Helios development stack has not been started."
            raise LauncherError(msg)
        while True:
            for managed in self._processes:
                exit_code = managed.handle.poll()
                if exit_code is not None:
                    msg = f"{managed.name} exited unexpectedly with code {exit_code}."
                    raise LauncherError(msg)
            self._sleeper(0.5)

    def shutdown(self) -> None:
        """Stop frontend and backend process trees in reverse start order."""
        for managed in reversed(self._processes):
            try:
                self._process_terminator(
                    managed.handle,
                    self.config.shutdown_timeout_seconds,
                )
            except (OSError, subprocess.SubprocessError):
                if managed.handle.poll() is None:
                    managed.handle.kill()
                    managed.handle.wait(timeout=self.config.shutdown_timeout_seconds)
        self._processes.clear()
        self._started = False

    def _spawn_backend(self, python: str, port: int) -> ProcessHandle:
        command = (
            python,
            "-m",
            "uvicorn",
            "apps.api.app:app",
            "--host",
            self.config.backend_host,
            "--port",
            str(port),
        )
        return self._spawn("Backend", command, self.project_root, os.environ)

    def _spawn_frontend(
        self,
        npm: str,
        port: int,
        backend_url: str,
    ) -> ProcessHandle:
        environment = dict(os.environ)
        environment["HELIOS_API_TARGET"] = backend_url
        command = (
            npm,
            "run",
            "dev",
            "--",
            "--host",
            self.config.frontend_host,
            "--port",
            str(port),
            "--strictPort",
        )
        return self._spawn(
            "Frontend",
            command,
            self.frontend_directory,
            environment,
        )

    def _spawn(
        self,
        name: str,
        command: Sequence[str],
        cwd: Path,
        environment: Mapping[str, str],
    ) -> ProcessHandle:
        try:
            process = self._process_starter(command, cwd, environment)
        except OSError as error:
            msg = f"{name} could not be started: {error}."
            raise LauncherError(msg) from error
        self._processes.append(ManagedProcess(name=name, handle=process))
        return process

    def _ensure_frontend_dependencies(self, npm: str) -> None:
        if (self.frontend_directory / "node_modules").is_dir():
            return
        try:
            self._command_runner((npm, "install"), self.frontend_directory)
        except (OSError, subprocess.CalledProcessError) as error:
            msg = "Frontend dependency installation failed."
            raise LauncherError(msg) from error

    def _wait_for_backend(self, process: ProcessHandle, backend_url: str) -> int:
        payload = self._wait_for_http(
            f"{backend_url}/api/videos",
            process,
            "Backend",
        )
        try:
            videos: object = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            msg = "Backend readiness response is not valid JSON."
            raise LauncherError(msg) from error
        if not isinstance(videos, list):
            msg = "Backend readiness response must be a video list."
            raise LauncherError(msg)
        return len(videos)

    def _wait_for_frontend(
        self,
        process: ProcessHandle,
        dashboard_url: str,
    ) -> None:
        payload = self._wait_for_http(dashboard_url, process, "Frontend")
        if b'id="root"' not in payload:
            msg = "Frontend readiness response is missing the application root."
            raise LauncherError(msg)

    def _wait_for_http(
        self,
        url: str,
        process: ProcessHandle,
        name: str,
    ) -> bytes:
        timeout = self.config.readiness_timeout_seconds
        if not math.isfinite(timeout) or timeout <= 0:
            msg = "Readiness timeout must be finite and greater than zero."
            raise LauncherError(msg)
        deadline = self._clock() + timeout
        while True:
            exit_code = process.poll()
            if exit_code is not None:
                msg = f"{name} exited before becoming ready (code {exit_code})."
                raise LauncherError(msg)
            try:
                return self._http_getter(url)
            except (OSError, TimeoutError):
                if self._clock() >= deadline:
                    msg = f"{name} did not become ready within {timeout:.1f}s."
                    raise LauncherError(msg) from None
                self._sleeper(self.config.readiness_poll_interval_seconds)

    def _open_browser(self, dashboard_url: str) -> bool:
        if not self.config.open_browser:
            return False
        try:
            opened = self._browser_opener(dashboard_url)
        except webbrowser.Error as error:
            msg = "Dashboard browser could not be opened."
            raise LauncherError(msg) from error
        if not opened:
            msg = "Dashboard browser could not be opened."
            raise LauncherError(msg)
        return True

    def _inspect_guardian(
        self,
        backend_url: str,
        frontend_url: str,
        backend_process: ProcessHandle,
    ) -> SystemHealthReport:
        output_directory = self.project_root / "output" / "videos"
        context = GuardianContext(
            runtime_probe=lambda: backend_process.poll() is None,
            agent_registry=AgentRegistry(),
            provider_registry=MediaProviderRegistry(),
            output_directory=output_directory,
            video_scanner=MediaStorageScanner(output_directory),
            backend_url=backend_url,
            frontend_url=frontend_url,
            http_client=LauncherGuardianHTTPClient(self._http_getter),
        )
        return create_guardian(context).inspect()


def format_summary(result: LaunchResult) -> str:
    """Format the concise ready-state console output."""
    browser_status = _READY_MARK if result.browser_opened else "disabled"
    guardian = result.guardian_report
    return "\n".join(
        (
            _SEPARATOR,
            "",
            "HELIOS DEV",
            "",
            f"Backend      {_READY_MARK}",
            f"Frontend     {_READY_MARK}",
            f"Browser      {browser_status}",
            f"API          {_READY_MARK}",
            f"Videos       {result.video_count} gefunden",
            "",
            "Dashboard:",
            result.dashboard_url,
            "",
            _SEPARATOR,
            "",
            "ARGUS",
            "",
            f"Backend      {_guardian_mark(guardian, 'backend_api')}",
            f"Frontend     {_guardian_mark(guardian, 'frontend')}",
            f"Runtime      {_guardian_mark(guardian, 'runtime')}",
            f"Agents       {_guardian_mark(guardian, 'agent_registry')}",
            f"Storage      {_guardian_mark(guardian, 'storage')}",
            f"Providers    {_provider_mark(guardian)}",
            f"Videos       {result.video_count}",
            f"Overall      {guardian.overall_status.value}",
            "",
            _SEPARATOR,
        ),
    )


def _guardian_mark(report: SystemHealthReport, check_id: str) -> str:
    check = next((item for item in report.checks if item.id == check_id), None)
    if check is None or check.status is CheckStatus.SKIPPED:
        return "-"
    if check.status is CheckStatus.PASS:
        return _READY_MARK
    return check.status.value


def _provider_mark(report: SystemHealthReport) -> str:
    statuses = {
        check.status
        for check in report.checks
        if check.id in {"provider_registry", "provider_config"}
    }
    if not statuses or statuses == {CheckStatus.SKIPPED}:
        return "-"
    if CheckStatus.FAIL in statuses:
        return CheckStatus.FAIL.value
    if CheckStatus.WARNING in statuses:
        return CheckStatus.WARNING.value
    return _READY_MARK


def main() -> int:
    """Run the development stack until interrupted or a service fails."""
    launcher = DevLauncher()
    try:
        result = launcher.start()
        print(format_summary(result), flush=True)
        launcher.wait()
    except KeyboardInterrupt:
        print("\nStopping Helios development stack...", flush=True)
        return 0
    except LauncherError as error:
        print(f"HELIOS DEV ERROR: {error}", file=sys.stderr, flush=True)
        return 1
    finally:
        launcher.shutdown()
    return 0
