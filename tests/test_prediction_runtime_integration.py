"""Runtime integration tests for Oracle prediction agent."""

import unittest

from agents.learning.models import LearningInsight, LearningReport
from agents.prediction.agent import PredictionAgent
from agents.prediction.models import PredictionReport
from engine.runtime.capability import AgentCapability
from engine.runtime.runtime import HeliosRuntime
from engine.tasks.priority import TaskPriority
from engine.tasks.status import TaskStatus
from engine.tasks.task import Task


def create_learning_report() -> LearningReport:
    """Create a learning report for runtime integration tests."""
    return LearningReport(
        video_id="video-1",
        performance_summary="Strong retention with platform variance.",
        strengths=[
            LearningInsight(
                category="Retention",
                observation="Opening structure held attention.",
                evidence="Watch percentage remained high.",
                recommendation="Reuse the hook structure.",
                confidence=0.86,
            ),
        ],
        weaknesses=[
            LearningInsight(
                category="Engagement Depth",
                observation="Saves and shares lagged.",
                evidence="Weakest platform engagement was lower.",
                recommendation="Add a save-worthy checklist.",
                confidence=0.79,
            ),
        ],
        experiments=["Test a checklist CTA against a question-led CTA."],
        recommended_actions=["Keep the current hook structure."],
        generated_by="mock:mock-learning-model",
    )


def create_prediction_task(payload: dict[str, object] | None = None) -> Task:
    """Create a prediction task for runtime integration tests."""
    return Task(
        task_id="prediction-task-1",
        title="Prediction",
        description="Create strategic predictions from learnings.",
        priority=TaskPriority.MEDIUM,
        required_capability=AgentCapability.PREDICTION,
        payload=(
            {"learning_reports": [create_learning_report()]}
            if payload is None
            else payload
        ),
    )


class PredictionRuntimeIntegrationTestCase(unittest.TestCase):
    """Integration tests for Oracle through HeliosRuntime."""

    def test_runtime_dispatches_prediction_task_to_oracle(self) -> None:
        """Runtime can dispatch PREDICTION tasks to Oracle."""
        runtime = HeliosRuntime()
        oracle = PredictionAgent()
        task = create_prediction_task()
        runtime.register(oracle)

        result = runtime.submit_task(task)

        self.assertIsInstance(result, PredictionReport)
        self.assertIs(result, task.result)
        self.assertIs(task.status, TaskStatus.COMPLETED)
        self.assertIs(oracle.last_prediction_report, result)

    def test_runtime_returns_prediction_report(self) -> None:
        """Runtime returns the PredictionReport from Oracle."""
        runtime = HeliosRuntime()
        runtime.register(PredictionAgent())
        task = create_prediction_task()

        result = runtime.submit_task(task)

        self.assertIsInstance(result, PredictionReport)

    def test_runtime_propagates_oracle_errors(self) -> None:
        """Runtime propagates Oracle validation errors."""
        runtime = HeliosRuntime()
        runtime.register(PredictionAgent())
        task = create_prediction_task({"learning_reports": []})

        with self.assertRaises(ValueError):
            runtime.submit_task(task)

        self.assertIs(task.status, TaskStatus.FAILED)


if __name__ == "__main__":
    unittest.main()
