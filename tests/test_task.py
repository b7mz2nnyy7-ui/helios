"""Tests for the task model."""

import unittest

from engine.runtime.capability import AgentCapability
from engine.tasks.priority import TaskPriority
from engine.tasks.status import TaskStatus
from engine.tasks.task import Task


def create_task() -> Task:
    """Create a test task."""
    return Task(
        task_id="task-1",
        title="Test Task",
        description="A task used for tests.",
        priority=TaskPriority.MEDIUM,
        required_capability=AgentCapability.STRATEGY,
        payload={"key": "value"},
    )


class TaskTestCase(unittest.TestCase):
    """Tests for Task behavior."""

    def test_new_task_has_pending_status(self) -> None:
        """A new task starts with PENDING status."""
        task = create_task()

        self.assertIs(task.status, TaskStatus.PENDING)

    def test_start_sets_status_to_running(self) -> None:
        """Starting a task sets its status to RUNNING."""
        task = create_task()

        task.start()

        self.assertIs(task.status, TaskStatus.RUNNING)

    def test_complete_sets_status_to_completed(self) -> None:
        """Completing a task sets its status to COMPLETED."""
        task = create_task()
        task.start()

        task.complete()

        self.assertIs(task.status, TaskStatus.COMPLETED)

    def test_complete_stores_result(self) -> None:
        """Completing a task stores its result."""
        task = create_task()
        result = {"value": 1}
        task.start()

        task.complete(result)

        self.assertEqual(task.result, result)

    def test_error_message_is_none_after_success(self) -> None:
        """Completing a task leaves error_message unset."""
        task = create_task()
        task.start()

        task.complete("result")

        self.assertIsNone(task.error_message)

    def test_fail_sets_status_to_failed(self) -> None:
        """Failing a task sets its status to FAILED."""
        task = create_task()
        task.start()

        task.fail()

        self.assertIs(task.status, TaskStatus.FAILED)

    def test_fail_stores_error_message(self) -> None:
        """Failing a task stores its error message."""
        task = create_task()
        task.start()

        task.fail("failed because of test")

        self.assertEqual(task.error_message, "failed because of test")

    def test_pending_to_completed_raises_value_error(self) -> None:
        """A pending task cannot be completed directly."""
        task = create_task()

        with self.assertRaisesRegex(ValueError, "PENDING.*COMPLETED"):
            task.complete()

    def test_pending_to_failed_raises_value_error(self) -> None:
        """A pending task cannot fail directly."""
        task = create_task()

        with self.assertRaisesRegex(ValueError, "PENDING.*FAILED"):
            task.fail()

    def test_running_to_running_raises_value_error(self) -> None:
        """A running task cannot be started again."""
        task = create_task()
        task.start()

        with self.assertRaisesRegex(ValueError, "RUNNING.*RUNNING"):
            task.start()

    def test_completed_to_running_raises_value_error(self) -> None:
        """A completed task cannot be started."""
        task = create_task()
        task.start()
        task.complete()

        with self.assertRaisesRegex(ValueError, "COMPLETED.*RUNNING"):
            task.start()

    def test_completed_to_completed_raises_value_error(self) -> None:
        """A completed task cannot be completed again."""
        task = create_task()
        task.start()
        task.complete()

        with self.assertRaisesRegex(ValueError, "COMPLETED.*COMPLETED"):
            task.complete()

    def test_completed_to_failed_raises_value_error(self) -> None:
        """A completed task cannot fail."""
        task = create_task()
        task.start()
        task.complete()

        with self.assertRaisesRegex(ValueError, "COMPLETED.*FAILED"):
            task.fail()

    def test_failed_to_running_raises_value_error(self) -> None:
        """A failed task cannot be started."""
        task = create_task()
        task.start()
        task.fail()

        with self.assertRaisesRegex(ValueError, "FAILED.*RUNNING"):
            task.start()

    def test_failed_to_completed_raises_value_error(self) -> None:
        """A failed task cannot be completed."""
        task = create_task()
        task.start()
        task.fail()

        with self.assertRaisesRegex(ValueError, "FAILED.*COMPLETED"):
            task.complete()

    def test_failed_to_failed_raises_value_error(self) -> None:
        """A failed task cannot fail again."""
        task = create_task()
        task.start()
        task.fail()

        with self.assertRaisesRegex(ValueError, "FAILED.*FAILED"):
            task.fail()

    def test_is_finished_returns_false_for_pending_task(self) -> None:
        """A pending task is not finished."""
        task = create_task()

        self.assertFalse(task.is_finished())

    def test_is_finished_returns_false_for_running_task(self) -> None:
        """A running task is not finished."""
        task = create_task()
        task.start()

        self.assertFalse(task.is_finished())

    def test_is_finished_returns_true_for_completed_task(self) -> None:
        """A completed task is finished."""
        task = create_task()
        task.start()
        task.complete()

        self.assertTrue(task.is_finished())

    def test_is_finished_returns_true_for_failed_task(self) -> None:
        """A failed task is finished."""
        task = create_task()
        task.start()
        task.fail()

        self.assertTrue(task.is_finished())


if __name__ == "__main__":
    unittest.main()
