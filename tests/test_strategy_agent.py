"""Tests for the Nova strategy agent."""

import unittest
from typing import Any

from agents.strategy.agent import StrategyAgent
from agents.strategy.mock_llm_provider import MockStrategyLLMProvider
from agents.strategy.models import ContentStrategy
from agents.trend_research.models import TrendResult
from agents.trend_research.report import TrendReport
from engine.llm.base_provider import BaseLLMProvider
from engine.llm.models import LLMRequest, LLMResponse
from engine.runtime.capability import AgentCapability
from engine.tasks.priority import TaskPriority
from engine.tasks.status import TaskStatus
from engine.tasks.task import Task
from engine.tools.llm_tool import LLMTool


class RecordingStrategyLLMProvider(BaseLLMProvider):
    """LLM provider that records strategy requests."""

    def __init__(self) -> None:
        """Create a recording provider."""
        super().__init__(provider_id="recording", model="recording-strategy-model")
        self.received_request: LLMRequest | None = None
        self.response = MockStrategyLLMProvider(
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


class FailingStrategyLLMProvider(BaseLLMProvider):
    """LLM provider that always fails."""

    def __init__(self) -> None:
        """Create a failing provider."""
        super().__init__(provider_id="failing", model="failing-strategy-model")

    def generate(self, request: LLMRequest) -> LLMResponse:
        """Raise a runtime error."""
        msg = "strategy llm failed"
        raise RuntimeError(msg)


def create_trend_report() -> TrendReport:
    """Create a trend report for strategy tests."""
    return TrendReport(
        query="AI Agents",
        summary="Mock trend summary.",
        trends=[
            TrendResult("AI Agents automation", 0.92, "mock:search", "High interest."),
            TrendResult("AI Agents workflow", 0.84, "mock:social", "Workflow demand."),
            TrendResult("AI Agents strategy", 0.78, "mock:content", "Strategy need."),
        ],
        generated_by="mock:mock-trend-model",
    )


def create_strategy_task(payload: dict[str, Any] | None = None) -> Task:
    """Create a strategy task."""
    task_payload = {"trend_report": create_trend_report()} if payload is None else payload
    return Task(
        task_id="strategy-task-1",
        title="Strategy",
        description="Create content strategy from trend research.",
        priority=TaskPriority.MEDIUM,
        required_capability=AgentCapability.STRATEGY,
        payload=task_payload,
    )


class StrategyAgentTestCase(unittest.TestCase):
    """Tests for StrategyAgent behavior."""

    def test_agent_has_strategy_capability(self) -> None:
        """Nova declares the STRATEGY capability."""
        agent = StrategyAgent()

        self.assertTrue(agent.can_handle(AgentCapability.STRATEGY))

    def test_agent_name_is_nova(self) -> None:
        """Nova has the expected display name."""
        agent = StrategyAgent()

        self.assertEqual(agent.name, "Nova")

    def test_default_llm_tool_exists(self) -> None:
        """Nova has a default LLM tool."""
        agent = StrategyAgent()

        self.assertIsInstance(agent.get_tool("llm"), LLMTool)

    def test_trend_report_is_validated(self) -> None:
        """Nova accepts a valid TrendReport payload."""
        agent = StrategyAgent()
        task = create_strategy_task()

        result = agent.run(task)

        self.assertIsInstance(result, ContentStrategy)

    def test_wrong_payload_raises_value_error(self) -> None:
        """Nova rejects payloads without a TrendReport."""
        agent = StrategyAgent()
        task = create_strategy_task({"trend_report": "not a report"})

        with self.assertRaises(ValueError):
            agent.run(task)

    def test_task_completed_after_success(self) -> None:
        """Successful strategy generation completes the task."""
        agent = StrategyAgent()
        task = create_strategy_task()

        agent.run(task)

        self.assertIs(task.status, TaskStatus.COMPLETED)

    def test_last_strategy_is_stored(self) -> None:
        """Nova stores the generated strategy."""
        agent = StrategyAgent()
        task = create_strategy_task()

        result = agent.run(task)

        self.assertIs(agent.last_strategy, result)

    def test_llm_receives_llm_request(self) -> None:
        """Nova sends an LLMRequest to the LLM tool."""
        provider = RecordingStrategyLLMProvider()
        agent = StrategyAgent(tools=[LLMTool(provider=provider)])
        task = create_strategy_task()

        agent.run(task)

        self.assertIsInstance(provider.received_request, LLMRequest)

    def test_prompt_contains_query_trend_topics_and_scores(self) -> None:
        """Nova prompt contains query, trend topics and scores."""
        provider = RecordingStrategyLLMProvider()
        agent = StrategyAgent(tools=[LLMTool(provider=provider)])
        task = create_strategy_task()

        agent.run(task)

        request = provider.received_request
        assert request is not None
        self.assertIn("AI Agents", request.user_prompt)
        self.assertIn("AI Agents automation", request.user_prompt)
        self.assertIn("AI Agents workflow", request.user_prompt)
        self.assertIn("0.92", request.user_prompt)
        self.assertIn("0.84", request.user_prompt)
        self.assertEqual(
            request.system_prompt,
            "Nova erstellt skalierbare Content-Strategien "
            "für Social-Media-Unternehmen.",
        )

    def test_mock_provider_returns_deterministic_results(self) -> None:
        """MockStrategyLLMProvider returns deterministic content."""
        provider = MockStrategyLLMProvider()
        request = LLMRequest(system_prompt="Nova", user_prompt="Query: AI Agents")

        first_response = provider.generate(request)
        second_response = provider.generate(request)

        self.assertEqual(first_response, second_response)
        self.assertEqual(first_response.provider, "mock")
        self.assertEqual(first_response.model, "mock-strategy-model")
        self.assertEqual(first_response.content.count("Idea: "), 5)

    def test_strategy_contains_five_content_ideas(self) -> None:
        """Nova creates five structured content ideas."""
        agent = StrategyAgent()
        task = create_strategy_task()

        strategy = agent.run(task)

        self.assertEqual(len(strategy.ideas), 5)
        self.assertEqual(strategy.query, "AI Agents")
        self.assertEqual(strategy.generated_by, "mock:mock-strategy-model")

    def test_failure_sets_task_failed(self) -> None:
        """LLM errors move the task to FAILED."""
        agent = StrategyAgent(tools=[LLMTool(provider=FailingStrategyLLMProvider())])
        task = create_strategy_task()

        with self.assertRaises(RuntimeError):
            agent.run(task)

        self.assertIs(task.status, TaskStatus.FAILED)
        self.assertEqual(task.error_message, "strategy llm failed")

    def test_failure_is_propagated(self) -> None:
        """LLM errors are propagated to the caller."""
        agent = StrategyAgent(tools=[LLMTool(provider=FailingStrategyLLMProvider())])
        task = create_strategy_task()

        with self.assertRaisesRegex(RuntimeError, "strategy llm failed"):
            agent.run(task)


if __name__ == "__main__":
    unittest.main()

