"""Tests for the Oracle prediction agent."""

import unittest

from agents.learning.models import LearningInsight, LearningReport
from agents.prediction.agent import PredictionAgent
from agents.prediction.mock_llm_provider import MockPredictionLLMProvider
from agents.prediction.models import Prediction, PredictionReport
from engine.llm.base_provider import BaseLLMProvider
from engine.llm.models import LLMRequest, LLMResponse
from engine.runtime.capability import AgentCapability
from engine.tasks.priority import TaskPriority
from engine.tasks.status import TaskStatus
from engine.tasks.task import Task
from engine.tools.llm_tool import LLMTool


class RecordingPredictionLLMProvider(BaseLLMProvider):
    """LLM provider that records prediction requests."""

    def __init__(self) -> None:
        """Create a recording provider."""
        super().__init__(provider_id="recording", model="recording-prediction-model")
        self.received_request: LLMRequest | None = None
        self.response = MockPredictionLLMProvider(
            provider_id=self.provider_id,
            model=self.model,
        ).generate(
            LLMRequest(
                system_prompt="recording",
                user_prompt="recording",
            ),
        )

    def generate(self, request: LLMRequest) -> LLMResponse:
        """Record the request and return a deterministic response."""
        self.received_request = request
        return self.response


class FailingPredictionLLMProvider(BaseLLMProvider):
    """LLM provider that always fails."""

    def __init__(self) -> None:
        """Create a failing provider."""
        super().__init__(provider_id="failing", model="failing-prediction-model")

    def generate(self, request: LLMRequest) -> LLMResponse:
        """Raise a runtime error."""
        msg = "prediction llm failed"
        raise RuntimeError(msg)


def create_learning_report(video_id: str = "video-1") -> LearningReport:
    """Create a learning report for prediction tests."""
    return LearningReport(
        video_id=video_id,
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
        experiments=[
            "Test a checklist CTA against a question-led CTA.",
            "Recut the first three seconds with sharper contrast.",
        ],
        recommended_actions=[
            "Keep the current hook structure.",
            "Add a clear save/share prompt.",
        ],
        generated_by="mock:mock-learning-model",
    )


def create_prediction_task(payload: dict[str, object] | None = None) -> Task:
    """Create a prediction task."""
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


class PredictionAgentTestCase(unittest.TestCase):
    """Tests for PredictionAgent behavior."""

    def test_agent_has_prediction_capability(self) -> None:
        """Oracle declares the PREDICTION capability."""
        agent = PredictionAgent()

        self.assertTrue(agent.can_handle(AgentCapability.PREDICTION))

    def test_agent_name_is_oracle(self) -> None:
        """Oracle has the expected display name."""
        agent = PredictionAgent()

        self.assertEqual(agent.name, "Oracle")

    def test_default_provider_exists(self) -> None:
        """Oracle has a default LLM tool."""
        agent = PredictionAgent()

        self.assertIsInstance(agent.get_tool("llm"), LLMTool)

    def test_payload_validated_and_task_completed(self) -> None:
        """Valid prediction inputs complete the task."""
        agent = PredictionAgent()
        task = create_prediction_task()

        report = agent.run(task)

        self.assertIsInstance(report, PredictionReport)
        self.assertIs(task.status, TaskStatus.COMPLETED)

    def test_empty_learning_reports_raise_value_error(self) -> None:
        """Oracle rejects empty learning report lists."""
        agent = PredictionAgent()
        task = create_prediction_task({"learning_reports": []})

        with self.assertRaises(ValueError):
            agent.run(task)

    def test_task_result_and_last_prediction_report_are_identical(self) -> None:
        """Oracle stores the report and writes it to the task."""
        agent = PredictionAgent()
        task = create_prediction_task()

        report = agent.run(task)

        self.assertIs(task.result, report)
        self.assertIs(agent.last_prediction_report, report)

    def test_strongest_prediction_is_highest_probability(self) -> None:
        """PredictionReport selects the highest probability prediction."""
        agent = PredictionAgent()
        task = create_prediction_task()

        report = agent.run(task)

        self.assertEqual(report.strongest_prediction.title, "Checklist CTA Lift")
        self.assertEqual(
            report.strongest_prediction.probability,
            max(prediction.probability for prediction in report.predictions),
        )

    def test_prompt_contains_learning_report_details(self) -> None:
        """Oracle prompt contains learning report details."""
        provider = RecordingPredictionLLMProvider()
        agent = PredictionAgent(tools=[LLMTool(provider=provider)])
        task = create_prediction_task(
            {
                "learning_reports": [
                    create_learning_report("video-1"),
                    create_learning_report("video-2"),
                ],
            },
        )

        agent.run(task)

        request = provider.received_request
        assert request is not None
        self.assertIn("Video ID: video-1", request.user_prompt)
        self.assertIn("Video ID: video-2", request.user_prompt)
        self.assertIn("Performance Summary: Strong retention", request.user_prompt)
        self.assertIn("Experiments:", request.user_prompt)
        self.assertIn("Test a checklist CTA", request.user_prompt)
        self.assertIn("Recommended Actions:", request.user_prompt)
        self.assertIn("Keep the current hook structure.", request.user_prompt)
        self.assertEqual(
            request.system_prompt,
            "Oracle erkennt zukünftige Content-Chancen anhand vergangener "
            "Learnings.",
        )

    def test_mock_provider_is_deterministic(self) -> None:
        """MockPredictionLLMProvider returns deterministic responses."""
        provider = MockPredictionLLMProvider()
        request = LLMRequest(system_prompt="Oracle", user_prompt="Learning data")

        first_response = provider.generate(request)
        second_response = provider.generate(request)

        self.assertEqual(first_response, second_response)
        self.assertEqual(first_response.provider, "mock")
        self.assertEqual(first_response.model, "mock-prediction-model")

    def test_probability_is_validated(self) -> None:
        """Prediction validates probability."""
        with self.assertRaises(ValueError):
            Prediction(
                title="Invalid",
                probability=1.1,
                reasoning="Too high.",
                recommendation="Reject.",
            )

    def test_prediction_report_requires_predictions(self) -> None:
        """PredictionReport requires at least one prediction."""
        with self.assertRaises(ValueError):
            PredictionReport(
                predictions=[],
                summary="Invalid.",
                generated_by="mock",
            )

    def test_prediction_report_to_markdown(self) -> None:
        """PredictionReport can be rendered as Markdown."""
        agent = PredictionAgent()
        task = create_prediction_task()

        report = agent.run(task)

        markdown = report.to_markdown()
        self.assertIn("# Prediction Report", markdown)
        self.assertIn("Checklist CTA Lift", markdown)
        self.assertIn(report.summary, markdown)

    def test_llm_failure_sets_task_failed(self) -> None:
        """LLM errors move the task to FAILED."""
        agent = PredictionAgent(
            tools=[LLMTool(provider=FailingPredictionLLMProvider())],
        )
        task = create_prediction_task()

        with self.assertRaises(RuntimeError):
            agent.run(task)

        self.assertIs(task.status, TaskStatus.FAILED)
        self.assertEqual(task.error_message, "prediction llm failed")

    def test_errors_are_propagated(self) -> None:
        """LLM errors are propagated unchanged."""
        agent = PredictionAgent(
            tools=[LLMTool(provider=FailingPredictionLLMProvider())],
        )
        task = create_prediction_task()

        with self.assertRaisesRegex(RuntimeError, "prediction llm failed"):
            agent.run(task)


if __name__ == "__main__":
    unittest.main()
