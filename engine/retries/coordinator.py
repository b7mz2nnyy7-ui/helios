"""Coordinates deterministic task retries through the Helios runtime."""

from typing import Any

from engine.retries.policy import RetryPolicy
from engine.runtime.runtime import HeliosRuntime
from engine.tasks.status import TaskStatus
from engine.tasks.task import Task


class RetryCoordinator:
    """Coordinates controlled retries for failed tasks."""

    def __init__(self, runtime: HeliosRuntime, policy: RetryPolicy) -> None:
        """Create a retry coordinator."""
        self.runtime = runtime
        self.policy = policy
        self.attempts: dict[str, int] = {}

    def retry(self, task: Task) -> Any:
        """Retry a failed task through the runtime if policy allows it."""
        if task.status is not TaskStatus.FAILED:
            msg = "Only FAILED tasks can be retried."
            raise ValueError(msg)

        current_attempt = self.get_attempts(task.task_id) + 1
        self.attempts[task.task_id] = current_attempt
        decision = self.policy.evaluate(task, current_attempt)
        if not decision.should_retry:
            msg = f"Retry refused for task '{task.task_id}': {decision.reason}"
            raise RuntimeError(msg)

        task.reset_for_retry()
        return self.runtime.submit_task(task)

    def get_attempts(self, task_id: str) -> int:
        """Return retry attempts recorded for a task ID."""
        return self.attempts.get(task_id, 0)

    def clear(self, task_id: str) -> None:
        """Clear retry attempts for a task ID."""
        if task_id not in self.attempts:
            raise KeyError(task_id)

        del self.attempts[task_id]
