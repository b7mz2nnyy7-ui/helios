"""Tests for deterministic task retry coordination."""

import unittest
from typing import Any

from engine.retries.coordinator import RetryCoordinator
from engine.retries.policy import RetryPolicy
from engine.runtime.base_agent import BaseAgent
from engine.runtime.capability import AgentCapability
from engine.runtime.runtime import HeliosRuntime
from engine.tasks.priority import TaskPriority
from engine.tasks.status import TaskStatus
from engine.tasks.task import Task


class RetryAgent(BaseAgent):
    """Agent implementation used for retry coordinator tests."""

    def __init__(
        self,
        should_fail: bool = False,
        result: str = "retry-result",
    ) -> None:
        """Create a retry test agent."""
        super().__init__(
            agent_id="retry-agent",
            name="Retry Agent",
            capabilities={AgentCapability.STRATEGY},
        )
        self.should_fail = should_fail
        self.result = result
        self.run_calls = 0

    def run(self, task: Task) -> Any:
        """Complete or fail a task based on configuration."""
        self.run_calls += 1
        task.start()
        if self.should_fail:
            task.fail("RuntimeError: retry failed")
            msg = "retry failed"
            raise RuntimeError(msg)

        task.complete(self.result)
        return self.result


def create_task(task_id: str = "task-1") -> Task:
    """Create a retryable task."""
    return Task(
        task_id=task_id,
        title="Retry Task",
        description="A task used for retry coordinator tests.",
        priority=TaskPriority.MEDIUM,
        required_capability=AgentCapability.STRATEGY,
        payload={},
    )


def create_failed_task(
    task_id: str = "task-1",
    error_message: str = "RuntimeError: failed",
    result: Any = None,
) -> Task:
    """Create a failed task for retry coordinator tests."""
    task = create_task(task_id)
    task.start()
    task.result = result
    task.fail(error_message)
    return task


def create_runtime(agent: RetryAgent) -> HeliosRuntime:
    """Create a runtime with a retry test agent."""
    runtime = HeliosRuntime()
    runtime.register(agent)
    return runtime


class RetryCoordinatorTestCase(unittest.TestCase):
    """Tests for RetryCoordinator behavior."""

    def test_first_retry_is_attempt_one(self) -> None:
        """The first retry call records attempt 1."""
        agent = RetryAgent()
        coordinator = RetryCoordinator(create_runtime(agent), RetryPolicy())
        task = create_failed_task()

        coordinator.retry(task)

        self.assertEqual(coordinator.get_attempts("task-1"), 1)

    def test_second_retry_is_attempt_two(self) -> None:
        """The second retry call records attempt 2."""
        agent = RetryAgent(should_fail=True)
        coordinator = RetryCoordinator(create_runtime(agent), RetryPolicy())
        task = create_failed_task()

        with self.assertRaises(RuntimeError):
            coordinator.retry(task)
        with self.assertRaises(RuntimeError):
            coordinator.retry(task)

        self.assertEqual(coordinator.get_attempts("task-1"), 2)

    def test_policy_limit_is_respected(self) -> None:
        """RetryCoordinator refuses retries once the policy limit is reached."""
        agent = RetryAgent()
        coordinator = RetryCoordinator(create_runtime(agent), RetryPolicy(max_attempts=1))
        task = create_failed_task()

        with self.assertRaises(RuntimeError):
            coordinator.retry(task)

        self.assertEqual(agent.run_calls, 0)
        self.assertEqual(coordinator.get_attempts("task-1"), 1)

    def test_non_retryable_error_prevents_runtime_call(self) -> None:
        """Non-retryable errors prevent runtime execution."""
        agent = RetryAgent()
        policy = RetryPolicy(non_retryable_error_types={"ValueError:"})
        coordinator = RetryCoordinator(create_runtime(agent), policy)
        task = create_failed_task(error_message="ValueError: invalid")

        with self.assertRaises(RuntimeError):
            coordinator.retry(task)

        self.assertEqual(agent.run_calls, 0)
        self.assertIs(task.status, TaskStatus.FAILED)

    def test_successful_retry_returns_runtime_result(self) -> None:
        """A successful retry returns the runtime result."""
        agent = RetryAgent(result="ok")
        coordinator = RetryCoordinator(create_runtime(agent), RetryPolicy())
        task = create_failed_task()

        result = coordinator.retry(task)

        self.assertEqual(result, "ok")

    def test_successful_retry_sets_task_completed(self) -> None:
        """A successful retry completes the task."""
        agent = RetryAgent()
        coordinator = RetryCoordinator(create_runtime(agent), RetryPolicy())
        task = create_failed_task()

        coordinator.retry(task)

        self.assertIs(task.status, TaskStatus.COMPLETED)

    def test_retry_failure_leaves_task_failed(self) -> None:
        """A failed retry leaves the task in FAILED state."""
        agent = RetryAgent(should_fail=True)
        coordinator = RetryCoordinator(create_runtime(agent), RetryPolicy())
        task = create_failed_task()

        with self.assertRaises(RuntimeError):
            coordinator.retry(task)

        self.assertIs(task.status, TaskStatus.FAILED)
        self.assertEqual(task.error_message, "RuntimeError: retry failed")

    def test_original_exception_is_propagated(self) -> None:
        """A retry execution error is propagated unchanged."""
        agent = RetryAgent(should_fail=True)
        coordinator = RetryCoordinator(create_runtime(agent), RetryPolicy())
        task = create_failed_task()

        with self.assertRaisesRegex(RuntimeError, "retry failed"):
            coordinator.retry(task)

    def test_attempts_are_counted_per_task(self) -> None:
        """Attempts are tracked separately per task ID."""
        agent = RetryAgent(should_fail=True)
        coordinator = RetryCoordinator(create_runtime(agent), RetryPolicy())
        first_task = create_failed_task("task-1")
        second_task = create_failed_task("task-2")

        with self.assertRaises(RuntimeError):
            coordinator.retry(first_task)
        with self.assertRaises(RuntimeError):
            coordinator.retry(first_task)
        with self.assertRaises(RuntimeError):
            coordinator.retry(second_task)

        self.assertEqual(coordinator.get_attempts("task-1"), 2)
        self.assertEqual(coordinator.get_attempts("task-2"), 1)

    def test_get_attempts_returns_zero_for_unknown_task(self) -> None:
        """Unknown task IDs have zero attempts."""
        coordinator = RetryCoordinator(create_runtime(RetryAgent()), RetryPolicy())

        self.assertEqual(coordinator.get_attempts("unknown"), 0)

    def test_clear_removes_attempt_counter(self) -> None:
        """clear removes a task attempt counter."""
        coordinator = RetryCoordinator(create_runtime(RetryAgent()), RetryPolicy())
        task = create_failed_task()
        coordinator.retry(task)

        coordinator.clear("task-1")

        self.assertEqual(coordinator.get_attempts("task-1"), 0)

    def test_clear_unknown_task_raises_key_error(self) -> None:
        """clear raises KeyError for unknown task IDs."""
        coordinator = RetryCoordinator(create_runtime(RetryAgent()), RetryPolicy())

        with self.assertRaises(KeyError):
            coordinator.clear("unknown")

    def test_reset_for_retry_only_allows_failed_tasks(self) -> None:
        """reset_for_retry only works from FAILED state."""
        task = create_task()

        with self.assertRaises(ValueError):
            task.reset_for_retry()

    def test_reset_for_retry_clears_result_and_error_message(self) -> None:
        """reset_for_retry clears result and error_message."""
        task = create_failed_task(result={"previous": "result"})

        task.reset_for_retry()

        self.assertIs(task.status, TaskStatus.PENDING)
        self.assertIsNone(task.result)
        self.assertIsNone(task.error_message)

    def test_coordinator_does_not_mutate_other_tasks(self) -> None:
        """Retrying one task does not mutate another task."""
        coordinator = RetryCoordinator(create_runtime(RetryAgent()), RetryPolicy())
        retried_task = create_failed_task("retried")
        other_task = create_failed_task("other", error_message="RuntimeError: other")

        coordinator.retry(retried_task)

        self.assertIs(other_task.status, TaskStatus.FAILED)
        self.assertEqual(other_task.error_message, "RuntimeError: other")
        self.assertEqual(coordinator.get_attempts("other"), 0)

    def test_no_runtime_execution_when_should_retry_false(self) -> None:
        """Runtime is not called when policy refuses retry."""
        agent = RetryAgent()
        coordinator = RetryCoordinator(create_runtime(agent), RetryPolicy(max_attempts=1))
        task = create_failed_task()

        with self.assertRaises(RuntimeError):
            coordinator.retry(task)

        self.assertEqual(agent.run_calls, 0)


if __name__ == "__main__":
    unittest.main()
