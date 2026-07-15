"""Controlled synchronous polling for existing Runway tasks."""

import re
import time
from dataclasses import dataclass
from typing import Protocol

from engine.media.providers.base import MediaProviderError
from integrations.runway.client import RunwayClient
from integrations.runway.models import RunwayTask

_SUCCESS_STATUSES = {"SUCCEEDED"}
_FAILURE_STATUSES = {"FAILED", "CANCELED", "CANCELLED"}
_POLLING_STATUSES = {"PENDING", "THROTTLED", "RUNNING"}


@dataclass(frozen=True)
class RunwayPollingConfig:
    """Limits controlling synchronous Runway task polling."""

    poll_interval_seconds: float = 2.0
    timeout_seconds: float = 300.0
    max_polls: int = 150

    def __post_init__(self) -> None:
        """Validate positive polling limits."""
        if not self.poll_interval_seconds > 0:
            msg = "poll_interval_seconds must be greater than 0."
            raise ValueError(msg)
        if not self.timeout_seconds > 0:
            msg = "timeout_seconds must be greater than 0."
            raise ValueError(msg)
        if not self.max_polls > 0:
            msg = "max_polls must be greater than 0."
            raise ValueError(msg)


@dataclass(frozen=True)
class RunwayPollingResult:
    """Completed Runway task with polling diagnostics."""

    task: RunwayTask
    poll_count: int
    elapsed_seconds: float

    def __post_init__(self) -> None:
        """Validate task and non-negative polling diagnostics."""
        if not isinstance(self.task, RunwayTask):
            msg = "task must be a RunwayTask."
            raise ValueError(msg)
        if not self.poll_count >= 0:
            msg = "poll_count must be greater than or equal to 0."
            raise ValueError(msg)
        if not self.elapsed_seconds >= 0:
            msg = "elapsed_seconds must be greater than or equal to 0."
            raise ValueError(msg)


class Clock(Protocol):
    """Monotonic time source used by the task poller."""

    def monotonic(self) -> float:
        """Return the current monotonic time in seconds."""


class Sleeper(Protocol):
    """Delay boundary used between task status requests."""

    def sleep(self, seconds: float) -> None:
        """Pause execution for the requested duration."""


class SystemClock:
    """Clock backed by the standard-library monotonic timer."""

    def monotonic(self) -> float:
        """Return standard-library monotonic time."""
        return time.monotonic()


class SystemSleeper:
    """Sleeper backed by the standard-library blocking sleep."""

    def sleep(self, seconds: float) -> None:
        """Block the current thread for the requested duration."""
        time.sleep(seconds)


class RunwayTaskPoller:
    """Wait synchronously for one existing Runway task to finish."""

    def __init__(
        self,
        client: RunwayClient,
        config: RunwayPollingConfig,
        clock: Clock,
        sleeper: Sleeper,
    ) -> None:
        """Create an isolated poller with injected time dependencies."""
        self.client = client
        self.config = config
        self.clock = clock
        self.sleeper = sleeper

    def wait_for_completion(self, task_id: str) -> RunwayPollingResult:
        """Poll until success or raise for failure and configured limits."""
        if not isinstance(task_id, str) or not task_id.strip():
            msg = "task_id must not be empty."
            raise ValueError(msg)

        started_at = self._read_clock(task_id)
        poll_count = 0

        while True:
            if poll_count > 0:
                elapsed_seconds = self._elapsed_seconds(task_id, started_at)
                self._enforce_limits(task_id, poll_count, elapsed_seconds)

            task = self._get_task(task_id)
            poll_count += 1
            elapsed_seconds = self._elapsed_seconds(task_id, started_at)
            status = task.status.strip().upper()

            if status in _SUCCESS_STATUSES:
                return RunwayPollingResult(
                    task=task,
                    poll_count=poll_count,
                    elapsed_seconds=elapsed_seconds,
                )

            if status in _FAILURE_STATUSES:
                raise MediaProviderError(
                    self._failure_message(task, poll_count, elapsed_seconds),
                )

            if status not in _POLLING_STATUSES:
                msg = (
                    f"Runway task '{task_id}' returned unknown status '{status}' "
                    f"after {poll_count} polls and {elapsed_seconds:.3f} seconds."
                )
                raise MediaProviderError(msg)

            self._enforce_limits(task_id, poll_count, elapsed_seconds)
            self._sleep(task_id, elapsed_seconds)

    def _get_task(self, task_id: str) -> RunwayTask:
        try:
            return self.client.get_task(task_id)
        except MediaProviderError:
            raise
        except Exception as error:
            msg = f"Runway client failed while polling task '{task_id}'."
            raise MediaProviderError(msg) from error

    def _read_clock(self, task_id: str) -> float:
        try:
            return self.clock.monotonic()
        except Exception as error:
            msg = f"Runway polling clock failed for task '{task_id}'."
            raise MediaProviderError(msg) from error

    def _elapsed_seconds(self, task_id: str, started_at: float) -> float:
        elapsed_seconds = self._read_clock(task_id) - started_at
        if elapsed_seconds < 0:
            msg = f"Runway polling clock moved backwards for task '{task_id}'."
            raise MediaProviderError(msg)
        return elapsed_seconds

    def _sleep(self, task_id: str, elapsed_seconds: float) -> None:
        remaining_seconds = self.config.timeout_seconds - elapsed_seconds
        sleep_seconds = min(
            self.config.poll_interval_seconds,
            remaining_seconds,
        )
        try:
            self.sleeper.sleep(sleep_seconds)
        except Exception as error:
            msg = f"Runway polling sleep failed for task '{task_id}'."
            raise MediaProviderError(msg) from error

    def _enforce_limits(
        self,
        task_id: str,
        poll_count: int,
        elapsed_seconds: float,
    ) -> None:
        if elapsed_seconds >= self.config.timeout_seconds:
            msg = (
                f"Runway task '{task_id}' timed out after {poll_count} polls "
                f"and {elapsed_seconds:.3f} seconds."
            )
            raise MediaProviderError(msg)

        if poll_count >= self.config.max_polls:
            msg = (
                f"Runway task '{task_id}' reached the limit of {poll_count} polls "
                f"after {elapsed_seconds:.3f} seconds."
            )
            raise MediaProviderError(msg)

    def _failure_message(
        self,
        task: RunwayTask,
        poll_count: int,
        elapsed_seconds: float,
    ) -> str:
        message = (
            f"Runway task '{task.task_id}' ended with status {task.status.upper()} "
            f"after {poll_count} polls and {elapsed_seconds:.3f} seconds."
        )
        if task.failure_message is None:
            return message

        safe_failure = _sanitize_failure_message(task.failure_message)
        return f"{message} Failure: {safe_failure}"


def _sanitize_failure_message(message: str) -> str:
    sanitized = re.sub(
        r"(?i)Bearer\s+\S+",
        "Bearer [REDACTED]",
        message,
    )
    sanitized = re.sub(
        r"(?i)(api[_ -]?key\s*[:=]\s*)\S+",
        r"\1[REDACTED]",
        sanitized,
    )
    return " ".join(sanitized.split())[:160]
