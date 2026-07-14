"""Deterministic retry policy for failed tasks."""

from engine.retries.models import RetryDecision
from engine.tasks.status import TaskStatus
from engine.tasks.task import Task


class RetryPolicy:
    """Evaluates whether a failed task should be retried."""

    def __init__(
        self,
        max_attempts: int = 3,
        non_retryable_error_types: set[str] | None = None,
    ) -> None:
        """Create a retry policy."""
        if max_attempts <= 0:
            msg = "max_attempts must be greater than 0."
            raise ValueError(msg)

        self.max_attempts = max_attempts
        self.non_retryable_error_types = set(non_retryable_error_types or set())

    def evaluate(self, task: Task, current_attempt: int) -> RetryDecision:
        """Evaluate whether a failed task should be retried."""
        if current_attempt < 1:
            msg = "current_attempt must be at least 1."
            raise ValueError(msg)

        if task.status is not TaskStatus.FAILED:
            msg = "Only FAILED tasks can be evaluated for retry."
            raise ValueError(msg)

        non_retryable_error = self._matching_non_retryable_error(task)
        if non_retryable_error is not None:
            return RetryDecision(
                should_retry=False,
                attempt=current_attempt,
                max_attempts=self.max_attempts,
                reason=f"Retry disabled for non-retryable error {non_retryable_error}.",
            )

        if current_attempt < self.max_attempts:
            return RetryDecision(
                should_retry=True,
                attempt=current_attempt,
                max_attempts=self.max_attempts,
                reason=(
                    f"Retry allowed: attempt {current_attempt} of "
                    f"{self.max_attempts}."
                ),
            )

        return RetryDecision(
            should_retry=False,
            attempt=current_attempt,
            max_attempts=self.max_attempts,
            reason=(
                f"Retry limit reached: attempt {current_attempt} of "
                f"{self.max_attempts}."
            ),
        )

    def _matching_non_retryable_error(self, task: Task) -> str | None:
        error_message = task.error_message or ""
        for error_type in self.non_retryable_error_types:
            if error_message.startswith(error_type):
                return error_type

        return None

