"""Tests for the guarded local Runway live-test runner."""

import socket
import unittest
from collections.abc import Mapping
from decimal import Decimal
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from engine.media.providers.base import MediaProviderError
from integrations.runway.http_transport import HTTPExecutor, HTTPResponse
from integrations.runway.models import RunwayGenerationRequest, RunwayTask
from scripts.run_runway_live_test import (
    RUNWAY_API_KEY_ENV,
    estimate_runway_cost_usd,
    parse_args,
    run_guarded_live_test,
)

MODEL = "configured-test-model"
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


def live_env(*, enabled: str = "true", api_key: str = SECRET) -> dict[str, str]:
    """Return explicit fake live configuration."""
    return {
        "HELIOS_RUNWAY_LIVE_ENABLED": enabled,
        RUNWAY_API_KEY_ENV: api_key,
        "HELIOS_MEDIA_RUNWAY_MODEL": MODEL,
    }


def invoke(
    argv: list[str],
    env: Mapping[str, str],
    transport: FakeRunwayTransport,
    pricing: Mapping[str, Decimal] = PRICING,
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
        self.assertIn("Output URL: https://example.invalid/runway-live.mp4", stdout)
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

    def test_no_network_download_or_file_write_occurs(self) -> None:
        """Successful fake live execution has no external side effects."""
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


if __name__ == "__main__":
    unittest.main()
