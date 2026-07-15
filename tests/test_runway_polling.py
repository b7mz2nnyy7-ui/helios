"""Tests for controlled synchronous Runway task polling."""

import socket
import time
import unittest
from dataclasses import FrozenInstanceError
from typing import cast
from unittest.mock import patch

from engine.media.providers.base import MediaProviderError
from integrations.runway.client import RunwayClient
from integrations.runway.models import RunwayTask
from integrations.runway.polling import (
    Clock,
    RunwayPollingConfig,
    RunwayPollingResult,
    RunwayTaskPoller,
    Sleeper,
    SystemClock,
    SystemSleeper,
)


class FakeRunwayClient(RunwayClient):
    """Runway client returning a deterministic task sequence."""

    def __init__(self, tasks: list[RunwayTask]) -> None:
        """Create a fake client without provider configuration."""
        self.tasks = list(tasks)
        self.calls: list[str] = []
        self.error: Exception | None = None

    def get_task(self, task_id: str) -> RunwayTask:
        """Return the next task or raise the configured error."""
        self.calls.append(task_id)
        if self.error is not None:
            raise self.error
        if not self.tasks:
            msg = "No fake Runway task remains."
            raise AssertionError(msg)
        return self.tasks.pop(0)


class FakeClock:
    """Manually advanced monotonic clock."""

    def __init__(self) -> None:
        """Start at zero without errors."""
        self.current = 0.0
        self.calls = 0
        self.error: Exception | None = None

    def monotonic(self) -> float:
        """Return current fake time or raise the configured error."""
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.current


class FakeSleeper:
    """Sleeper advancing fake time without blocking."""

    def __init__(self, clock: FakeClock) -> None:
        """Create a sleeper connected to one fake clock."""
        self.clock = clock
        self.calls: list[float] = []
        self.error: Exception | None = None

    def sleep(self, seconds: float) -> None:
        """Record and advance time or raise the configured error."""
        if self.error is not None:
            raise self.error
        self.calls.append(seconds)
        self.clock.current += seconds


def task(
    status: str,
    failure_message: str | None = None,
) -> RunwayTask:
    """Create a task with deterministic output for successful status."""
    output_urls = (
        ("https://example.invalid/video.mp4",)
        if status.upper() == "SUCCEEDED"
        else ()
    )
    return RunwayTask(
        task_id="runway-task-1",
        status=status,
        output_urls=output_urls,
        failure_message=failure_message,
    )


def create_poller(
    statuses: list[RunwayTask],
    config: RunwayPollingConfig | None = None,
) -> tuple[RunwayTaskPoller, FakeRunwayClient, FakeClock, FakeSleeper]:
    """Create a poller using only deterministic fakes."""
    client = FakeRunwayClient(statuses)
    clock = FakeClock()
    sleeper = FakeSleeper(clock)
    poller = RunwayTaskPoller(
        client=client,
        config=config or RunwayPollingConfig(),
        clock=clock,
        sleeper=sleeper,
    )
    return poller, client, clock, sleeper


class RunwayPollingModelTestCase(unittest.TestCase):
    """Tests for polling configuration and result models."""

    def test_default_config_is_valid(self) -> None:
        """Default limits match the controlled polling contract."""
        config = RunwayPollingConfig()

        self.assertEqual(config.poll_interval_seconds, 2.0)
        self.assertEqual(config.timeout_seconds, 300.0)
        self.assertEqual(config.max_polls, 150)

    def test_config_rejects_invalid_values(self) -> None:
        """Every configured polling limit must be positive."""
        invalid_configs = (
            {"poll_interval_seconds": 0},
            {"poll_interval_seconds": -1},
            {"poll_interval_seconds": float("nan")},
            {"timeout_seconds": 0},
            {"timeout_seconds": -1},
            {"timeout_seconds": float("nan")},
            {"max_polls": 0},
            {"max_polls": -1},
        )
        for values in invalid_configs:
            with self.subTest(values=values):
                with self.assertRaises(ValueError):
                    RunwayPollingConfig(**values)

    def test_polling_result_validates_diagnostics(self) -> None:
        """Polling results require a task and non-negative diagnostics."""
        successful_task = task("SUCCEEDED")
        result = RunwayPollingResult(successful_task, 1, 0.0)
        self.assertIs(result.task, successful_task)

        with self.assertRaises(ValueError):
            RunwayPollingResult(successful_task, -1, 0)
        with self.assertRaises(ValueError):
            RunwayPollingResult(successful_task, 1, -1)
        with self.assertRaises(ValueError):
            RunwayPollingResult(successful_task, 1, float("nan"))
        with self.assertRaises(ValueError):
            RunwayPollingResult(cast(RunwayTask, object()), 1, 0)

    def test_polling_models_are_immutable(self) -> None:
        """Polling configuration and results cannot be modified."""
        config = RunwayPollingConfig()
        result = RunwayPollingResult(task("SUCCEEDED"), 1, 0)

        with self.assertRaises(FrozenInstanceError):
            config.max_polls = 2  # type: ignore[misc]
        with self.assertRaises(FrozenInstanceError):
            result.poll_count = 2  # type: ignore[misc]

    def test_standard_time_dependencies_satisfy_protocols(self) -> None:
        """Standard time implementations satisfy injected contracts."""
        clock: Clock = SystemClock()
        sleeper: Sleeper = SystemSleeper()

        self.assertIsInstance(clock, SystemClock)
        self.assertIsInstance(sleeper, SystemSleeper)


class RunwayTaskPollerTestCase(unittest.TestCase):
    """Tests for bounded task status polling."""

    def test_empty_task_id_is_rejected(self) -> None:
        """Polling requires a non-empty task identifier."""
        poller, client, _, _ = create_poller([task("SUCCEEDED")])

        for task_id in ("", " "):
            with self.subTest(task_id=task_id):
                with self.assertRaises(ValueError):
                    poller.wait_for_completion(task_id)
        self.assertEqual(client.calls, [])

    def test_immediate_success_requires_no_sleep(self) -> None:
        """An immediately successful task returns after one request."""
        successful_task = task("SUCCEEDED")
        poller, client, _, sleeper = create_poller([successful_task])

        result = poller.wait_for_completion("runway-task-1")

        self.assertIs(result.task, successful_task)
        self.assertEqual(result.poll_count, 1)
        self.assertEqual(result.elapsed_seconds, 0.0)
        self.assertEqual(client.calls, ["runway-task-1"])
        self.assertEqual(sleeper.calls, [])

    def test_pending_running_succeeded_sequence(self) -> None:
        """Pollable states continue until success."""
        poller, client, _, sleeper = create_poller(
            [task("PENDING"), task("RUNNING"), task("SUCCEEDED")],
        )

        result = poller.wait_for_completion("runway-task-1")

        self.assertEqual(result.poll_count, 3)
        self.assertEqual(result.elapsed_seconds, 4.0)
        self.assertEqual(len(client.calls), 3)
        self.assertEqual(sleeper.calls, [2.0, 2.0])

    def test_throttled_status_continues_polling(self) -> None:
        """Throttled tasks wait before another status request."""
        poller, _, _, sleeper = create_poller(
            [task("THROTTLED"), task("SUCCEEDED")],
        )

        result = poller.wait_for_completion("runway-task-1")

        self.assertEqual(result.poll_count, 2)
        self.assertEqual(sleeper.calls, [2.0])

    def test_terminal_failures_raise_with_safe_details(self) -> None:
        """Failed and cancelled tasks raise contextual provider errors."""
        for status in ("FAILED", "CANCELLED", "CANCELED"):
            with self.subTest(status=status):
                poller, client, _, sleeper = create_poller(
                    [task(status, "Provider rejected the prompt")],
                )
                with self.assertRaises(MediaProviderError) as context:
                    poller.wait_for_completion("runway-task-1")

                message = str(context.exception)
                self.assertIn(status, message)
                self.assertIn("Provider rejected the prompt", message)
                self.assertIn("1 polls", message)
                self.assertEqual(len(client.calls), 1)
                self.assertEqual(sleeper.calls, [])

    def test_failure_message_redacts_credentials(self) -> None:
        """Credential-shaped failure details are redacted and shortened."""
        secret = "secret-token"
        failure = f"Authorization Bearer {secret} api_key={secret} " + "x" * 300
        poller, _, _, _ = create_poller([task("FAILED", failure)])

        with self.assertRaises(MediaProviderError) as context:
            poller.wait_for_completion("runway-task-1")

        message = str(context.exception)
        self.assertNotIn(secret, message)
        self.assertIn("[REDACTED]", message)
        self.assertLess(len(message), 300)

    def test_unknown_status_is_rejected(self) -> None:
        """Unrecognized provider states stop polling immediately."""
        poller, client, _, sleeper = create_poller([task("MYSTERY")])

        with self.assertRaises(MediaProviderError) as context:
            poller.wait_for_completion("runway-task-1")

        self.assertIn("MYSTERY", str(context.exception))
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(sleeper.calls, [])

    def test_timeout_stops_before_another_request(self) -> None:
        """Elapsed timeout prevents any request beyond the limit."""
        config = RunwayPollingConfig(
            poll_interval_seconds=2,
            timeout_seconds=3,
            max_polls=10,
        )
        poller, client, _, sleeper = create_poller(
            [task("PENDING") for _ in range(4)],
            config,
        )

        with self.assertRaises(MediaProviderError) as context:
            poller.wait_for_completion("runway-task-1")

        message = str(context.exception)
        self.assertIn("runway-task-1", message)
        self.assertIn("2 polls", message)
        self.assertIn("3.000 seconds", message)
        self.assertEqual(len(client.calls), 2)
        self.assertEqual(sleeper.calls, [2, 1])

    def test_max_polls_stops_without_extra_request_or_sleep(self) -> None:
        """Poll-count limit applies directly after the final allowed request."""
        config = RunwayPollingConfig(
            poll_interval_seconds=1,
            timeout_seconds=100,
            max_polls=2,
        )
        poller, client, _, sleeper = create_poller(
            [task("PENDING") for _ in range(3)],
            config,
        )

        with self.assertRaises(MediaProviderError) as context:
            poller.wait_for_completion("runway-task-1")

        self.assertIn("2 polls", str(context.exception))
        self.assertEqual(len(client.calls), 2)
        self.assertEqual(sleeper.calls, [1])

    def test_media_provider_client_error_is_unchanged(self) -> None:
        """Existing MediaProviderError instances pass through unchanged."""
        poller, client, _, _ = create_poller([task("SUCCEEDED")])
        original = MediaProviderError("safe client failure")
        client.error = original

        with self.assertRaises(MediaProviderError) as context:
            poller.wait_for_completion("runway-task-1")

        self.assertIs(context.exception, original)

    def test_other_client_error_is_wrapped_with_cause(self) -> None:
        """Unexpected client errors become safe provider errors."""
        poller, client, _, _ = create_poller([task("SUCCEEDED")])
        original = RuntimeError("client failed")
        client.error = original

        with self.assertRaises(MediaProviderError) as context:
            poller.wait_for_completion("runway-task-1")

        self.assertIs(context.exception.__cause__, original)

    def test_clock_error_is_wrapped_with_cause(self) -> None:
        """Clock failures become contextual provider errors."""
        poller, client, clock, _ = create_poller([task("SUCCEEDED")])
        original = RuntimeError("clock failed")
        clock.error = original

        with self.assertRaises(MediaProviderError) as context:
            poller.wait_for_completion("runway-task-1")

        self.assertIs(context.exception.__cause__, original)
        self.assertEqual(client.calls, [])

    def test_sleeper_error_is_wrapped_with_cause(self) -> None:
        """Sleeper failures become contextual provider errors."""
        poller, client, _, sleeper = create_poller([task("PENDING")])
        original = RuntimeError("sleep failed")
        sleeper.error = original

        with self.assertRaises(MediaProviderError) as context:
            poller.wait_for_completion("runway-task-1")

        self.assertIs(context.exception.__cause__, original)
        self.assertEqual(len(client.calls), 1)

    def test_pollers_share_no_state(self) -> None:
        """Independent pollers retain separate dependencies and counts."""
        first, first_client, _, _ = create_poller([task("SUCCEEDED")])
        second, second_client, _, _ = create_poller(
            [task("RUNNING"), task("SUCCEEDED")],
        )

        first_result = first.wait_for_completion("first")
        second_result = second.wait_for_completion("second")

        self.assertEqual(first_result.poll_count, 1)
        self.assertEqual(second_result.poll_count, 2)
        self.assertEqual(first_client.calls, ["first"])
        self.assertEqual(second_client.calls, ["second", "second"])

    def test_polling_uses_no_real_sleep_network_or_costly_call(self) -> None:
        """Fakes complete polling without time or network side effects."""
        poller, client, _, sleeper = create_poller(
            [task("PENDING"), task("SUCCEEDED")],
        )

        with (
            patch.object(time, "sleep", side_effect=AssertionError("real sleep")),
            patch.object(socket, "socket", side_effect=AssertionError("network")),
        ):
            result = poller.wait_for_completion("runway-task-1")

        self.assertEqual(result.poll_count, 2)
        self.assertEqual(len(client.calls), 2)
        self.assertEqual(sleeper.calls, [2.0])


if __name__ == "__main__":
    unittest.main()
