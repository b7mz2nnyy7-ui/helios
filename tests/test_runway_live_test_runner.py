"""Tests for the guarded local Runway live-test runner."""

import json
import socket
import unittest
from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from engine.media.asset import MediaAsset
from engine.media.providers.base import MediaProviderError
from engine.media.storage import MediaStorage, MediaStorageError, StoredMediaAsset
from integrations.runway.http_transport import HTTPExecutor, HTTPResponse
from integrations.runway.models import (
    RunwayGenerationMode,
    RunwayGenerationRequest,
    RunwayTask,
)
from scripts.run_runway_live_test import (
    RUNWAY_API_KEY_ENV,
    RUNWAY_API_VERSION_ENV,
    estimate_runway_cost_usd,
    parse_args,
    run_guarded_live_test,
)

MODEL = "gen4.5"
SECRET = "synthetic-runway-test-key"
PRICING = {MODEL: Decimal("0.10")}


class NoNetworkExecutor:
    """Executor that fails if a transport attempts real HTTP execution."""

    def execute(
        self,
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: bytes | None,
        timeout_seconds: float,
    ) -> HTTPResponse:
        """Reject every attempted HTTP operation."""
        raise AssertionError("HTTP executor must not be called in tests")


class RecordingExecutorFactory:
    """Factory counting delayed executor construction."""

    def __init__(self) -> None:
        """Create a factory with no constructions."""
        self.calls = 0

    def __call__(self) -> HTTPExecutor:
        """Create one executor without performing a request."""
        self.calls += 1
        return NoNetworkExecutor()


class SuccessfulRecordingExecutor:
    """Record an HTTP request and return an immediate successful task."""

    def __init__(self) -> None:
        """Create an executor without recorded requests."""
        self.calls: list[
            tuple[str, str, Mapping[str, str], bytes | None]
        ] = []

    def execute(
        self,
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: bytes | None,
        timeout_seconds: float,
    ) -> HTTPResponse:
        """Record create or download requests without network access."""
        self.calls.append((method, url, dict(headers), body))
        if method == "GET":
            return HTTPResponse(
                status_code=200,
                headers={"Content-Type": "video/mp4"},
                body=b"fake-runway-mp4",
            )
        return HTTPResponse(
            status_code=200,
            headers={"Content-Type": "application/json"},
            body=json.dumps(
                {
                    "id": "runway-live-task-1",
                    "status": "SUCCEEDED",
                    "output": ["https://example.invalid/runway-live.mp4"],
                },
            ).encode("utf-8"),
        )


class FakeRunwayTransport:
    """Deterministic transport for one create and queued task reads."""

    def __init__(
        self,
        created_task: RunwayTask,
        polled_tasks: list[RunwayTask] | None = None,
    ) -> None:
        """Create a fake transport with fixed provider responses."""
        self.created_task = created_task
        self.polled_tasks = list(polled_tasks or [])
        self.create_calls: list[RunwayGenerationRequest] = []
        self.get_calls: list[str] = []
        self.error: Exception | None = None

    def create_video(
        self,
        request: RunwayGenerationRequest,
        api_key: str,
        base_url: str,
        timeout_seconds: float,
    ) -> RunwayTask:
        """Record exactly one generation request."""
        self.create_calls.append(request)
        if self.error is not None:
            raise self.error
        return self.created_task

    def get_task(
        self,
        task_id: str,
        api_key: str,
        base_url: str,
        timeout_seconds: float,
    ) -> RunwayTask:
        """Return the next queued task status."""
        self.get_calls.append(task_id)
        if not self.polled_tasks:
            msg = "No fake polling response remains."
            raise AssertionError(msg)
        return self.polled_tasks.pop(0)


class FakeClock:
    """Monotonic clock advanced by the fake sleeper."""

    def __init__(self) -> None:
        """Start fake time at zero."""
        self.current = 0.0

    def monotonic(self) -> float:
        """Return current fake time."""
        return self.current


class FakeSleeper:
    """Non-blocking sleeper advancing one fake clock."""

    def __init__(self, clock: FakeClock) -> None:
        """Create a sleeper with an empty call history."""
        self.clock = clock
        self.calls: list[float] = []

    def sleep(self, seconds: float) -> None:
        """Advance fake time without blocking."""
        self.calls.append(seconds)
        self.clock.current += seconds


class FakeMediaStorage(MediaStorage):
    """Store asset metadata without file or network access."""

    def __init__(self) -> None:
        """Create an empty recording store."""
        self.download_calls: list[MediaAsset] = []

    def download_asset(self, asset: MediaAsset) -> StoredMediaAsset:
        """Record one asset and return deterministic storage metadata."""
        self.download_calls.append(asset)
        return StoredMediaAsset(
            local_path=Path("output/videos/runway-live-task-1.mp4").resolve(),
            size_bytes=24,
            download_duration_seconds=0.25,
            sha256="a" * 64,
            mime_type="video/mp4",
            created_at=datetime.now(UTC),
            original_asset=asset,
        )


class FailingMediaStorage(FakeMediaStorage):
    """Reject every attempted local download."""

    def download_asset(self, asset: MediaAsset) -> StoredMediaAsset:
        """Raise a safe storage error without exposing the source URL."""
        del asset
        raise MediaStorageError("local video storage failed")


def runway_task(
    status: str,
    output_urls: tuple[str, ...] = (),
) -> RunwayTask:
    """Create a deterministic Runway task response."""
    return RunwayTask(
        task_id="runway-live-task-1",
        status=status,
        output_urls=output_urls,
    )


def live_args(
    *,
    confirm: bool = True,
    cost_limit: str | None = "0.50",
    model: str = MODEL,
) -> list[str]:
    """Return CLI arguments for an otherwise authorized live run."""
    values = [
        "A calm cinematic sunrise over a modern city",
        "--duration",
        "5",
        "--ratio",
        "1280:720",
        "--model",
        model,
    ]
    if cost_limit is not None:
        values.extend(["--max-estimated-cost-usd", cost_limit])
    if confirm:
        values.append("--confirm-live-runway-request")
    return values


def live_env(
    *,
    enabled: str = "true",
    api_key: str = SECRET,
    price: str | None = None,
    api_version: str | None = None,
) -> dict[str, str]:
    """Return explicit fake live configuration."""
    env = {
        "HELIOS_RUNWAY_LIVE_ENABLED": enabled,
        RUNWAY_API_KEY_ENV: api_key,
        "HELIOS_MEDIA_RUNWAY_MODEL": MODEL,
    }
    if price is not None:
        env["HELIOS_MEDIA_RUNWAY_PRICE_PER_SECOND_USD"] = price
    if api_version is not None:
        env[RUNWAY_API_VERSION_ENV] = api_version
    return env


def invoke(
    argv: list[str],
    env: Mapping[str, str],
    transport: FakeRunwayTransport,
    pricing: Mapping[str, Decimal] | None = PRICING,
) -> tuple[int, str, str, RecordingExecutorFactory, FakeClock, FakeSleeper]:
    """Invoke the runner with fakes and captured terminal output."""
    stdout = StringIO()
    stderr = StringIO()
    executor_factory = RecordingExecutorFactory()
    clock = FakeClock()
    sleeper = FakeSleeper(clock)
    exit_code = run_guarded_live_test(
        parse_args(argv),
        env=env,
        pricing_table=pricing,
        executor_factory=executor_factory,
        transport_factory=lambda executor: transport,
        storage_factory=lambda executor: FakeMediaStorage(),
        clock=clock,
        sleeper=sleeper,
        stdout=stdout,
        stderr=stderr,
    )
    return (
        exit_code,
        stdout.getvalue(),
        stderr.getvalue(),
        executor_factory,
        clock,
        sleeper,
    )


class RunwayLiveTestRunnerTestCase(unittest.TestCase):
    """Tests for live guards, cost limits and fake execution."""

    def test_standard_run_is_disabled_without_request(self) -> None:
        """Default CLI usage remains a no-cost dry run."""
        transport = FakeRunwayTransport(runway_task("SUCCEEDED"))

        code, stdout, _, factory, _, _ = invoke(
            ["A safe dry run prompt"],
            {},
            transport,
            pricing={},
        )

        self.assertEqual(code, 2)
        self.assertIn("LIVE REQUEST DISABLED", stdout)
        self.assertEqual(factory.calls, 0)
        self.assertEqual(transport.create_calls, [])
        self.assertEqual(transport.get_calls, [])

    def test_missing_confirmation_flag_blocks(self) -> None:
        """Live environment alone never authorizes generation."""
        transport = FakeRunwayTransport(runway_task("SUCCEEDED"))

        code, stdout, _, factory, _, _ = invoke(
            live_args(confirm=False),
            live_env(),
            transport,
        )

        self.assertEqual(code, 2)
        self.assertIn("missing --confirm-live-runway-request", stdout)
        self.assertEqual(factory.calls, 0)
        self.assertEqual(transport.create_calls, [])

    def test_missing_live_environment_blocks(self) -> None:
        """Confirmation flag requires the independent environment gate."""
        transport = FakeRunwayTransport(runway_task("SUCCEEDED"))

        code, stdout, _, factory, _, _ = invoke(
            live_args(),
            live_env(enabled="false"),
            transport,
        )

        self.assertEqual(code, 2)
        self.assertIn("HELIOS_RUNWAY_LIVE_ENABLED must be true", stdout)
        self.assertEqual(factory.calls, 0)

    def test_missing_api_key_blocks(self) -> None:
        """No executor is created without environment credentials."""
        transport = FakeRunwayTransport(runway_task("SUCCEEDED"))

        code, stdout, _, factory, _, _ = invoke(
            live_args(),
            live_env(api_key=""),
            transport,
        )

        self.assertEqual(code, 2)
        self.assertIn("HELIOS_MEDIA_RUNWAY_API_KEY is not configured", stdout)
        self.assertEqual(factory.calls, 0)

    def test_missing_or_non_positive_cost_limit_blocks(self) -> None:
        """A finite positive maximum cost is mandatory."""
        for cost_limit in (None, "0", "-1", "nan", "inf"):
            with self.subTest(cost_limit=cost_limit):
                transport = FakeRunwayTransport(runway_task("SUCCEEDED"))
                code, stdout, _, factory, _, _ = invoke(
                    live_args(cost_limit=cost_limit),
                    live_env(),
                    transport,
                )

                self.assertEqual(code, 2)
                self.assertIn("max-estimated-cost-usd", stdout)
                self.assertEqual(factory.calls, 0)
                self.assertEqual(transport.create_calls, [])

    def test_unknown_model_blocks_without_fallback_price(self) -> None:
        """Models absent from the explicit table cannot run live."""
        transport = FakeRunwayTransport(runway_task("SUCCEEDED"))

        code, stdout, _, factory, _, _ = invoke(
            live_args(model="unknown-model"),
            live_env(),
            transport,
        )

        self.assertEqual(code, 2)
        self.assertIn("no explicit pricing", stdout)
        self.assertEqual(factory.calls, 0)

    def test_estimated_cost_above_limit_blocks(self) -> None:
        """The exact decimal estimate cannot exceed the user limit."""
        transport = FakeRunwayTransport(runway_task("SUCCEEDED"))

        code, stdout, _, factory, _, _ = invoke(
            live_args(cost_limit="0.499999"),
            live_env(),
            transport,
        )

        self.assertEqual(code, 2)
        self.assertIn("exceeds limit", stdout)
        self.assertEqual(factory.calls, 0)

    def test_exact_cost_limit_is_accepted(self) -> None:
        """An estimate exactly equal to the limit is authorized."""
        transport = FakeRunwayTransport(
            runway_task(
                "SUCCEEDED",
                ("https://example.invalid/runway-live.mp4",),
            ),
        )

        code, stdout, stderr, factory, _, sleeper = invoke(
            live_args(cost_limit="0.50"),
            live_env(),
            transport,
        )

        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        self.assertIn("Final status: SUCCEEDED", stdout)
        self.assertIn("Estimated maximum cost: $0.500000", stdout)
        self.assertEqual(factory.calls, 1)
        self.assertEqual(len(transport.create_calls), 1)
        self.assertEqual(sleeper.calls, [])

    def test_live_runner_uses_gen45_text_endpoint_for_prompt_only(self) -> None:
        """Pure Gen-4.5 prompts use text_to_video without promptImage."""
        executor = SuccessfulRecordingExecutor()
        stdout = StringIO()
        stderr = StringIO()
        clock = FakeClock()

        code = run_guarded_live_test(
            parse_args(live_args()),
            env=live_env(),
            pricing_table=PRICING,
            executor_factory=lambda: executor,
            storage_factory=lambda configured_executor: FakeMediaStorage(),
            clock=clock,
            sleeper=FakeSleeper(clock),
            stdout=stdout,
            stderr=stderr,
        )

        self.assertEqual(code, 0)
        self.assertEqual(stderr.getvalue(), "")
        self.assertEqual(len(executor.calls), 1)
        method, url, headers, body = executor.calls[0]
        self.assertEqual(method, "POST")
        self.assertEqual(
            url,
            "https://api.dev.runwayml.com/v1/text_to_video",
        )
        self.assertNotIn("image_to_video", url)
        self.assertEqual(headers["X-Runway-Version"], "2024-11-06")
        self.assertEqual(len(headers), 4)
        decoded_body = json.loads(body or b"{}")
        self.assertEqual(
            decoded_body,
            {
                "duration": 5,
                "model": MODEL,
                "promptText": "A calm cinematic sunrise over a modern city",
                "ratio": "1280:720",
            },
        )
        self.assertIs(type(decoded_body["duration"]), int)
        self.assertNotIn("promptImage", decoded_body)

    def test_live_runner_downloads_completed_video_to_local_storage(self) -> None:
        """A completed fake task is downloaded through the same HTTP executor."""
        executor = SuccessfulRecordingExecutor()
        stdout = StringIO()
        stderr = StringIO()
        clock = FakeClock()

        with TemporaryDirectory() as directory:
            output_directory = Path(directory) / "videos"
            code = run_guarded_live_test(
                parse_args(live_args()),
                env=live_env(),
                pricing_table=PRICING,
                executor_factory=lambda: executor,
                storage_factory=lambda configured_executor: MediaStorage(
                    output_directory,
                    executor=configured_executor,
                ),
                clock=clock,
                sleeper=FakeSleeper(clock),
                stdout=stdout,
                stderr=stderr,
            )

            stored_path = output_directory / "runway-live-task-1.mp4"
            self.assertEqual(code, 0)
            self.assertEqual(stderr.getvalue(), "")
            self.assertEqual(len(executor.calls), 2)
            self.assertEqual(executor.calls[1][0], "GET")
            self.assertEqual(stored_path.read_bytes(), b"fake-runway-mp4")
            self.assertIn(str(stored_path.resolve()), stdout.getvalue())
            self.assertIn("Output stored successfully.", stdout.getvalue())
            self.assertNotIn("https://example.invalid", stdout.getvalue())

    def test_storage_failure_returns_error_without_false_success(self) -> None:
        """A completed provider task is not reported successful if storage fails."""
        transport = FakeRunwayTransport(
            runway_task(
                "SUCCEEDED",
                ("https://example.invalid/private.mp4?token=signed",),
            ),
        )
        stdout = StringIO()
        stderr = StringIO()
        factory = RecordingExecutorFactory()

        code = run_guarded_live_test(
            parse_args(live_args()),
            env=live_env(),
            pricing_table=PRICING,
            executor_factory=factory,
            transport_factory=lambda executor: transport,
            storage_factory=lambda executor: FailingMediaStorage(),
            stdout=stdout,
            stderr=stderr,
        )

        self.assertEqual(code, 1)
        self.assertIn("Live Runway error", stderr.getvalue())
        self.assertNotIn("Output stored successfully.", stdout.getvalue())
        self.assertNotIn("example.invalid", stdout.getvalue())
        self.assertNotIn("example.invalid", stderr.getvalue())

    def test_live_runner_builds_text_to_video_request(self) -> None:
        """The guarded runner labels prompt-only requests explicitly."""
        transport = FakeRunwayTransport(
            runway_task(
                "SUCCEEDED",
                ("https://example.invalid/runway-live.mp4",),
            ),
        )

        code, _, _, _, _, _ = invoke(
            live_args(),
            live_env(),
            transport,
        )

        self.assertEqual(code, 0)
        generated_request = transport.create_calls[0]
        self.assertIs(
            generated_request.mode,
            RunwayGenerationMode.TEXT_TO_VIDEO,
        )
        self.assertIsNone(generated_request.prompt_image)
        self.assertIs(type(generated_request.duration_seconds), int)

    def test_cli_whole_number_durations_create_integer_requests(self) -> None:
        """Both 5 and 5.0 CLI spellings create an integer duration."""
        for duration in ("5", "5.0"):
            with self.subTest(duration=duration):
                transport = FakeRunwayTransport(
                    runway_task(
                        "SUCCEEDED",
                        ("https://example.invalid/runway-live.mp4",),
                    ),
                )
                argv = live_args()
                argv[argv.index("5")] = duration

                code, _, _, _, _, _ = invoke(
                    argv,
                    live_env(),
                    transport,
                )

                self.assertEqual(code, 0)
                self.assertIs(
                    type(transport.create_calls[0].duration_seconds),
                    int,
                )

    def test_invalid_duration_is_blocked_before_executor_construction(self) -> None:
        """Invalid durations never reach transport or executor construction."""
        for duration in ("0", "5.5", "nan", "inf"):
            with self.subTest(duration=duration):
                transport = FakeRunwayTransport(runway_task("SUCCEEDED"))
                argv = live_args()
                argv[argv.index("5")] = duration

                code, _, stderr, factory, _, _ = invoke(
                    argv,
                    live_env(),
                    transport,
                )

                self.assertEqual(code, 1)
                self.assertIn("duration_seconds", stderr)
                self.assertEqual(factory.calls, 0)
                self.assertEqual(transport.create_calls, [])

    def test_live_success_polls_existing_task(self) -> None:
        """One create call may be followed by controlled fake polling."""
        transport = FakeRunwayTransport(
            runway_task("PENDING"),
            [
                runway_task("RUNNING"),
                runway_task(
                    "SUCCEEDED",
                    ("https://example.invalid/runway-live.mp4",),
                ),
            ],
        )

        code, stdout, stderr, factory, _, sleeper = invoke(
            live_args(),
            live_env(),
            transport,
        )

        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        self.assertEqual(factory.calls, 1)
        self.assertEqual(len(transport.create_calls), 1)
        self.assertEqual(transport.get_calls, ["runway-live-task-1"] * 2)
        self.assertEqual(sleeper.calls, [2.0])
        self.assertIn("Poll count: 2", stdout)
        self.assertIn("Elapsed seconds: 2.000", stdout)
        self.assertIn("Output stored successfully.", stdout)
        self.assertIn("Stored:", stdout)
        self.assertIn("SHA256:", stdout)
        self.assertIn("File size: 24 bytes", stdout)
        self.assertNotIn("https://example.invalid", stdout)
        self.assertIn(f"Model: {MODEL}", stdout)
        self.assertIn("Duration: 5.0s", stdout)
        self.assertIn("Ratio: 1280:720", stdout)

    def test_api_key_is_absent_from_output_and_errors(self) -> None:
        """Credentials are redacted even from provider-generated failures."""
        transport = FakeRunwayTransport(runway_task("PENDING"))
        transport.error = MediaProviderError(f"Bearer {SECRET} was rejected")

        code, stdout, stderr, _, _, _ = invoke(
            live_args(),
            live_env(),
            transport,
        )

        self.assertEqual(code, 1)
        self.assertNotIn(SECRET, stdout)
        self.assertNotIn(SECRET, stderr)
        self.assertNotIn(SECRET, repr(parse_args(live_args())))
        self.assertIn("[REDACTED]", stderr)

    def test_api_key_is_redacted_from_all_terminal_values(self) -> None:
        """Prompt and provider output cannot echo the configured API key."""
        transport = FakeRunwayTransport(
            runway_task(
                "SUCCEEDED",
                (f"https://example.invalid/video.mp4?token={SECRET}",),
            ),
        )
        argv = live_args()
        argv[0] = f"A prompt accidentally containing {SECRET}"

        code, stdout, stderr, _, _, _ = invoke(
            argv,
            live_env(),
            transport,
        )

        self.assertEqual(code, 0)
        self.assertNotIn(SECRET, stdout)
        self.assertNotIn(SECRET, stderr)
        self.assertIn("[REDACTED]", stdout)
        self.assertNotIn("?token=", stdout)
        self.assertIn("Output stored successfully.", stdout)

    def test_live_failure_does_not_create_second_generation(self) -> None:
        """A failed create call is never retried or replaced by a mock."""
        transport = FakeRunwayTransport(runway_task("PENDING"))
        transport.error = RuntimeError("fake provider unavailable")

        code, _, stderr, factory, _, _ = invoke(
            live_args(),
            live_env(),
            transport,
        )

        self.assertEqual(code, 1)
        self.assertIn("Live Runway error", stderr)
        self.assertEqual(factory.calls, 1)
        self.assertEqual(len(transport.create_calls), 1)
        self.assertEqual(transport.get_calls, [])

    def test_fake_live_storage_uses_no_external_side_effects(self) -> None:
        """Injected test storage keeps fake live execution fully offline."""
        transport = FakeRunwayTransport(
            runway_task(
                "SUCCEEDED",
                ("https://example.invalid/runway-live.mp4",),
            ),
        )

        with (
            patch.object(socket, "socket", side_effect=AssertionError("network")),
            patch.object(Path, "open", side_effect=AssertionError("file")),
            patch.object(Path, "write_bytes", side_effect=AssertionError("download")),
        ):
            code, _, _, _, _, _ = invoke(
                live_args(),
                live_env(),
                transport,
            )

        self.assertEqual(code, 0)
        self.assertEqual(len(transport.create_calls), 1)

    def test_cost_estimation_requires_explicit_model_rate(self) -> None:
        """Cost calculation is deterministic and has no invented fallback."""
        self.assertEqual(
            estimate_runway_cost_usd(MODEL, 5.0, PRICING),
            0.5,
        )
        with self.assertRaises(ValueError):
            estimate_runway_cost_usd("unknown", 5.0, PRICING)
        with self.assertRaises(ValueError):
            estimate_runway_cost_usd(MODEL, 5.0)


class RunwayLiveReadinessTestCase(unittest.TestCase):
    """Tests for the non-executing live-readiness audit mode."""

    def test_complete_configuration_is_ready_without_execution(self) -> None:
        """All explicit prerequisites produce READY without creating a task."""
        transport = FakeRunwayTransport(runway_task("SUCCEEDED"))
        argv = live_args(confirm=True)
        argv.append("--check-live-readiness")

        code, stdout, stderr, factory, _, sleeper = invoke(
            argv,
            live_env(price="0.10"),
            transport,
            pricing=None,
        )

        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        self.assertIn("RUNWAY LIVE READINESS: READY", stdout)
        self.assertIn(f"Model: {MODEL}", stdout)
        self.assertIn("Duration: 5.0s", stdout)
        self.assertIn("Ratio: 1280:720", stdout)
        self.assertIn("Price per second: $0.100000", stdout)
        self.assertIn("Estimated cost: $0.500000", stdout)
        self.assertIn("Cost limit: $0.500000", stdout)
        self.assertIn("Poll interval: 2.0s", stdout)
        self.assertIn("Timeout: 300.0s", stdout)
        self.assertIn("Maximum polls: 150", stdout)
        self.assertIn("Live switch active: yes", stdout)
        self.assertIn("API key present: yes", stdout)
        self.assertIn("API version: 2024-11-06", stdout)
        self.assertEqual(factory.calls, 0)
        self.assertEqual(transport.create_calls, [])
        self.assertEqual(transport.get_calls, [])
        self.assertEqual(sleeper.calls, [])

    def test_invalid_api_version_is_blocked_without_execution(self) -> None:
        """Readiness rejects unknown versions before transport construction."""
        transport = FakeRunwayTransport(runway_task("SUCCEEDED"))
        argv = live_args(confirm=False)
        argv.append("--check-live-readiness")

        code, stdout, _, factory, _, _ = invoke(
            argv,
            live_env(price="0.10", api_version="2099-01-01"),
            transport,
            pricing=None,
        )

        self.assertEqual(code, 2)
        self.assertIn("RUNWAY LIVE READINESS: BLOCKED", stdout)
        self.assertIn("API version: 2099-01-01", stdout)
        self.assertIn("Runway API version must be one of", stdout)
        self.assertEqual(factory.calls, 0)
        self.assertEqual(transport.create_calls, [])

    def test_readiness_blocks_invalid_text_contract_values(self) -> None:
        """Model, ratio and duration are validated without HTTP execution."""
        cases = (
            ("unsupported", "1280:720", "5"),
            (MODEL, "768:1280", "5"),
            (MODEL, "1280:720", "11"),
        )
        for model, ratio, duration in cases:
            with self.subTest(model=model, ratio=ratio, duration=duration):
                transport = FakeRunwayTransport(runway_task("SUCCEEDED"))
                argv = live_args(confirm=False, model=model)
                argv[argv.index("1280:720")] = ratio
                argv[argv.index("5")] = duration
                argv.append("--check-live-readiness")

                code, stdout, _, factory, _, _ = invoke(
                    argv,
                    live_env(price="0.10"),
                    transport,
                    pricing=None,
                )

                self.assertEqual(code, 2)
                self.assertIn("RUNWAY LIVE READINESS: BLOCKED", stdout)
                self.assertEqual(factory.calls, 0)
                self.assertEqual(transport.create_calls, [])

    def test_readiness_uses_no_network_or_file_access(self) -> None:
        """Readiness remains a pure validation path."""
        transport = FakeRunwayTransport(runway_task("SUCCEEDED"))
        argv = live_args(confirm=False)
        argv.append("--check-live-readiness")

        with (
            patch.object(socket, "socket", side_effect=AssertionError("network")),
            patch.object(Path, "open", side_effect=AssertionError("file")),
            patch.object(Path, "write_bytes", side_effect=AssertionError("download")),
        ):
            code, _, _, factory, _, _ = invoke(
                argv,
                live_env(price="0.10"),
                transport,
                pricing=None,
            )

        self.assertEqual(code, 0)
        self.assertEqual(factory.calls, 0)
        self.assertEqual(transport.create_calls, [])

    def test_missing_api_key_is_blocked(self) -> None:
        """Readiness reports absent credentials without exposing values."""
        transport = FakeRunwayTransport(runway_task("SUCCEEDED"))
        argv = live_args(confirm=False)
        argv.append("--check-live-readiness")

        code, stdout, stderr, factory, _, _ = invoke(
            argv,
            live_env(api_key="", price="0.10"),
            transport,
            pricing=None,
        )

        self.assertEqual(code, 2)
        self.assertEqual(stderr, "")
        self.assertIn("RUNWAY LIVE READINESS: BLOCKED", stdout)
        self.assertIn("API key present: no", stdout)
        self.assertEqual(factory.calls, 0)

    def test_inactive_live_switch_is_blocked(self) -> None:
        """Readiness requires the independent environment switch."""
        transport = FakeRunwayTransport(runway_task("SUCCEEDED"))
        argv = live_args(confirm=False)
        argv.append("--check-live-readiness")

        code, stdout, _, factory, _, _ = invoke(
            argv,
            live_env(enabled="false", price="0.10"),
            transport,
            pricing=None,
        )

        self.assertEqual(code, 2)
        self.assertIn("Live switch active: no", stdout)
        self.assertIn("HELIOS_RUNWAY_LIVE_ENABLED must be true", stdout)
        self.assertEqual(factory.calls, 0)

    def test_missing_model_is_blocked(self) -> None:
        """Readiness never infers a provider model."""
        transport = FakeRunwayTransport(runway_task("SUCCEEDED"))
        argv = [
            "A calm cinematic sunrise over a modern city",
            "--duration",
            "5",
            "--max-estimated-cost-usd",
            "1.00",
            "--check-live-readiness",
        ]
        env = live_env(price="0.10")
        env.pop("HELIOS_MEDIA_RUNWAY_MODEL")

        code, stdout, _, factory, _, _ = invoke(
            argv,
            env,
            transport,
            pricing=None,
        )

        self.assertEqual(code, 2)
        self.assertIn("Model: not configured", stdout)
        self.assertIn("Runway model is not configured", stdout)
        self.assertEqual(factory.calls, 0)

    def test_missing_or_invalid_local_price_is_blocked(self) -> None:
        """Only finite positive environment pricing permits readiness."""
        for price in (None, "0", "-0.1", "NaN", "Infinity", "invalid"):
            with self.subTest(price=price):
                transport = FakeRunwayTransport(runway_task("SUCCEEDED"))
                argv = live_args(confirm=False)
                argv.append("--check-live-readiness")

                code, stdout, _, factory, _, _ = invoke(
                    argv,
                    live_env(price=price),
                    transport,
                    pricing=None,
                )

                self.assertEqual(code, 2)
                self.assertIn("Price per second: not configured", stdout)
                self.assertIn("no explicit pricing", stdout)
                self.assertEqual(factory.calls, 0)

    def test_missing_cost_limit_is_blocked(self) -> None:
        """Readiness requires the same explicit cost ceiling as live mode."""
        transport = FakeRunwayTransport(runway_task("SUCCEEDED"))
        argv = live_args(confirm=False, cost_limit=None)
        argv.append("--check-live-readiness")

        code, stdout, _, factory, _, _ = invoke(
            argv,
            live_env(price="0.10"),
            transport,
            pricing=None,
        )

        self.assertEqual(code, 2)
        self.assertIn("Cost limit: not configured", stdout)
        self.assertIn("--max-estimated-cost-usd is required", stdout)
        self.assertEqual(factory.calls, 0)

    def test_estimated_cost_over_limit_is_blocked(self) -> None:
        """Readiness applies the exact same decimal cost comparison."""
        transport = FakeRunwayTransport(runway_task("SUCCEEDED"))
        argv = live_args(confirm=False, cost_limit="0.49")
        argv.append("--check-live-readiness")

        code, stdout, _, factory, _, _ = invoke(
            argv,
            live_env(price="0.10"),
            transport,
            pricing=None,
        )

        self.assertEqual(code, 2)
        self.assertIn("Estimated cost: $0.500000", stdout)
        self.assertIn("exceeds limit", stdout)
        self.assertEqual(factory.calls, 0)

    def test_api_key_never_appears_in_readiness_output(self) -> None:
        """Readiness reports only whether a credential exists."""
        transport = FakeRunwayTransport(runway_task("SUCCEEDED"))
        argv = live_args(confirm=False)
        argv.append("--check-live-readiness")

        code, stdout, stderr, _, _, _ = invoke(
            argv,
            live_env(price="0.10"),
            transport,
            pricing=None,
        )

        self.assertEqual(code, 0)
        self.assertNotIn(SECRET, stdout)
        self.assertNotIn(SECRET, stderr)
        self.assertIn("API key present: yes", stdout)


if __name__ == "__main__":
    unittest.main()
