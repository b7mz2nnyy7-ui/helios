"""Tests for deterministic task retry policy."""

import unittest
from dataclasses import FrozenInstanceError

from engine.retries.models import RetryDecision
from engine.retries.policy import RetryPolicy
from engine.runtime.capability import AgentCapability
from engine.tasks.priority import TaskPriority
from engine.tasks.status import TaskStatus
from engine.tasks.task import Task


def create_task() -> Task:
    """Create a task for retry policy tests."""
    return Task(
        task_id="task-1",
        title="Retry Task",
        description="A task used for retry policy tests.",
        priority=TaskPriority.MEDIUM,
        required_capability=AgentCapability.STRATEGY,
        payload={},
    )


def create_failed_task(error_message: str = "RuntimeError: failed") -> Task:
    """Create a failed task for retry policy tests."""
    task = create_task()
    task.start()
    task.fail(error_message)
    return task


class RetryPolicyTestCase(unittest.TestCase):
    """Tests for RetryPolicy behavior."""

    def test_default_max_attempts_is_three(self) -> None:
        """RetryPolicy defaults to three max attempts."""
        policy = RetryPolicy()

        self.assertEqual(policy.max_attempts, 3)

    def test_invalid_max_attempts_raises_value_error(self) -> None:
        """max_attempts must be greater than 0."""
        with self.assertRaises(ValueError):
            RetryPolicy(max_attempts=0)

    def test_invalid_current_attempt_raises_value_error(self) -> None:
        """current_attempt must be at least 1."""
        policy = RetryPolicy()

        with self.assertRaises(ValueError):
            policy.evaluate(create_failed_task(), current_attempt=0)

    def test_non_failed_task_is_rejected(self) -> None:
        """Only FAILED tasks can be evaluated."""
        policy = RetryPolicy()

        with self.assertRaises(ValueError):
            policy.evaluate(create_task(), current_attempt=1)

    def test_retry_on_attempt_one_of_three(self) -> None:
        """Attempt 1 of 3 can be retried."""
        decision = RetryPolicy().evaluate(create_failed_task(), current_attempt=1)

        self.assertTrue(decision.should_retry)
        self.assertEqual(decision.attempt, 1)
        self.assertEqual(decision.max_attempts, 3)
        self.assertIn("Retry allowed", decision.reason)

    def test_retry_on_attempt_two_of_three(self) -> None:
        """Attempt 2 of 3 can be retried."""
        decision = RetryPolicy().evaluate(create_failed_task(), current_attempt=2)

        self.assertTrue(decision.should_retry)

    def test_no_retry_on_attempt_three_of_three(self) -> None:
        """Attempt 3 of 3 reaches the retry limit."""
        decision = RetryPolicy().evaluate(create_failed_task(), current_attempt=3)

        self.assertFalse(decision.should_retry)
        self.assertIn("Retry limit reached", decision.reason)

    def test_no_retry_above_limit(self) -> None:
        """Attempts above the limit are not retried."""
        decision = RetryPolicy().evaluate(create_failed_task(), current_attempt=4)

        self.assertFalse(decision.should_retry)

    def test_non_retryable_error_prevents_retry(self) -> None:
        """Configured non-retryable error prefixes prevent retry."""
        policy = RetryPolicy(non_retryable_error_types={"ValueError:"})
        task = create_failed_task("ValueError: invalid input")

        decision = policy.evaluate(task, current_attempt=1)

        self.assertFalse(decision.should_retry)
        self.assertIn("non-retryable", decision.reason)

    def test_other_errors_remain_retryable(self) -> None:
        """Errors that do not match prefixes remain retryable."""
        policy = RetryPolicy(non_retryable_error_types={"ValueError:"})
        task = create_failed_task("RuntimeError: transient failure")

        decision = policy.evaluate(task, current_attempt=1)

        self.assertTrue(decision.should_retry)

    def test_retry_decision_is_immutable(self) -> None:
        """RetryDecision is immutable."""
        decision = RetryDecision(
            should_retry=True,
            attempt=1,
            max_attempts=3,
            reason="Retry allowed.",
        )

        with self.assertRaises(FrozenInstanceError):
            setattr(decision, "should_retry", False)

    def test_policy_does_not_mutate_task(self) -> None:
        """Evaluating a retry decision does not mutate the task."""
        policy = RetryPolicy()
        task = create_failed_task("RuntimeError: failed")
        original_status = task.status
        original_error_message = task.error_message
        original_result = task.result

        policy.evaluate(task, current_attempt=1)

        self.assertIs(task.status, original_status)
        self.assertIs(task.status, TaskStatus.FAILED)
        self.assertEqual(task.error_message, original_error_message)
        self.assertEqual(task.result, original_result)

    def test_multiple_evaluations_are_independent(self) -> None:
        """Each evaluation returns an independent decision object."""
        policy = RetryPolicy()
        task = create_failed_task()

        first_decision = policy.evaluate(task, current_attempt=1)
        second_decision = policy.evaluate(task, current_attempt=1)

        self.assertIsNot(first_decision, second_decision)
        self.assertEqual(first_decision, second_decision)


if __name__ == "__main__":
    unittest.main()
