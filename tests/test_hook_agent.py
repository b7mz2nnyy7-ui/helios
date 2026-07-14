"""Tests for the Apollo hook agent."""

import unittest
from typing import Any

from agents.hook.agent import HookAgent
from agents.hook.mock_llm_provider import MockHookLLMProvider
from agents.hook.models import HookCandidate, OptimizedHook
from agents.script.models import ScriptSection, VideoScript
from engine.llm.base_provider import BaseLLMProvider
from engine.llm.models import LLMRequest, LLMResponse
from engine.runtime.capability import AgentCapability
from engine.tasks.priority import TaskPriority
from engine.tasks.status import TaskStatus
from engine.tasks.task import Task
from engine.tools.llm_tool import LLMTool


class RecordingHookLLMProvider(BaseLLMProvider):
    """LLM provider that records hook requests."""

    def __init__(self) -> None:
        """Create a recording provider."""
        super().__init__(provider_id="recording", model="recording-hook-model")
        self.received_request: LLMRequest | None = None
        self.response = MockHookLLMProvider(
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


class FailingHookLLMProvider(BaseLLMProvider):
    """LLM provider that always fails."""

    def __init__(self) -> None:
        """Create a failing provider."""
        super().__init__(provider_id="failing", model="failing-hook-model")

    def generate(self, request: LLMRequest) -> LLMResponse:
        """Raise a runtime error."""
        msg = "hook llm failed"
        raise RuntimeError(msg)


def create_video_script() -> VideoScript:
    """Create a video script for hook tests."""
    return VideoScript(
        title="AI Agents That Actually Save Time",
        hook="Most AI agent content sounds futuristic.",
        sections=[
            ScriptSection("Problem", "Teams are overwhelmed by tools."),
            ScriptSection("Insight", "Practical automation removes repeated work."),
            ScriptSection("Action", "Start with one audience pain point."),
        ],
        call_to_action="Pick one recurring content task.",
        summary="A practical script about AI workflows.",
        generated_by="mock:mock-script-model",
    )


def create_hook_task(payload: dict[str, Any] | None = None) -> Task:
    """Create a hook optimization task."""
    return Task(
        task_id="hook-task-1",
        title="Hook",
        description="Optimize video hook.",
        priority=TaskPriority.MEDIUM,
        required_capability=AgentCapability.HOOK,
        payload={"video_script": create_video_script()} if payload is None else payload,
    )


class HookAgentTestCase(unittest.TestCase):
    """Tests for HookAgent behavior."""

    def test_agent_has_hook_capability(self) -> None:
        """Apollo declares the HOOK capability."""
        agent = HookAgent()

        self.assertTrue(agent.can_handle(AgentCapability.HOOK))

    def test_agent_name_is_apollo(self) -> None:
        """Apollo has the expected display name."""
        agent = HookAgent()

        self.assertEqual(agent.name, "Apollo")

    def test_default_llm_tool_exists(self) -> None:
        """Apollo has a default LLM tool."""
        agent = HookAgent()

        self.assertIsInstance(agent.get_tool("llm"), LLMTool)

    def test_valid_video_script_is_processed(self) -> None:
        """Apollo accepts a valid VideoScript payload."""
        agent = HookAgent()
        task = create_hook_task()

        result = agent.run(task)

        self.assertIsInstance(result, OptimizedHook)

    def test_wrong_payload_raises_value_error(self) -> None:
        """Apollo rejects payloads without a VideoScript."""
        agent = HookAgent()
        task = create_hook_task({"video_script": "invalid"})

        with self.assertRaises(ValueError):
            agent.run(task)

    def test_task_completed_after_success(self) -> None:
        """Successful hook optimization completes the task."""
        agent = HookAgent()
        task = create_hook_task()

        agent.run(task)

        self.assertIs(task.status, TaskStatus.COMPLETED)

    def test_task_result_and_last_hook_are_identical(self) -> None:
        """Apollo stores the optimized hook and writes it to the task."""
        agent = HookAgent()
        task = create_hook_task()

        optimized_hook = agent.run(task)

        self.assertIs(task.result, optimized_hook)
        self.assertIs(agent.last_hook, optimized_hook)

    def test_prompt_contains_script_data(self) -> None:
        """Apollo prompt contains title, original hook, summary and sections."""
        provider = RecordingHookLLMProvider()
        agent = HookAgent(tools=[LLMTool(provider=provider)])
        task = create_hook_task()

        agent.run(task)

        request = provider.received_request
        assert request is not None
        self.assertIn("Script Title: AI Agents That Actually Save Time", request.user_prompt)
        self.assertIn(
            "Original Hook: Most AI agent content sounds futuristic.",
            request.user_prompt,
        )
        self.assertIn("Summary: A practical script about AI workflows.", request.user_prompt)
        self.assertIn("Problem", request.user_prompt)
        self.assertIn("Insight", request.user_prompt)
        self.assertIn("Action", request.user_prompt)
        self.assertEqual(
            request.system_prompt,
            "Apollo optimiert ausschließlich Hooks für maximale Aufmerksamkeit.",
        )

    def test_mock_provider_is_deterministic(self) -> None:
        """MockHookLLMProvider returns deterministic content."""
        provider = MockHookLLMProvider()
        request = LLMRequest(system_prompt="Apollo", user_prompt="Script data")

        first_response = provider.generate(request)
        second_response = provider.generate(request)

        self.assertEqual(first_response, second_response)
        self.assertEqual(first_response.provider, "mock")
        self.assertEqual(first_response.model, "mock-hook-model")
        self.assertEqual(first_response.content.count("Hook: "), 10)

    def test_highest_score_is_selected(self) -> None:
        """Apollo selects the hook candidate with the highest score."""
        agent = HookAgent()
        task = create_hook_task()

        optimized_hook = agent.run(task)

        highest_score = max(candidate.score for candidate in optimized_hook.candidates)
        self.assertEqual(optimized_hook.selected_hook.score, highest_score)
        self.assertEqual(
            optimized_hook.selected_hook.text,
            "The fastest AI win is not a chatbot. It is a workflow you stop repeating.",
        )

    def test_score_is_validated(self) -> None:
        """HookCandidate validates score values."""
        with self.assertRaises(ValueError):
            HookCandidate(text="Invalid", score=1.1, reason="Too high.")

    def test_markdown_contains_selected_hook(self) -> None:
        """OptimizedHook can be rendered as Markdown."""
        agent = HookAgent()
        task = create_hook_task()

        optimized_hook = agent.run(task)

        self.assertIn(optimized_hook.selected_hook.text, optimized_hook.to_markdown())

    def test_llm_failure_sets_task_failed(self) -> None:
        """LLM errors move the task to FAILED."""
        agent = HookAgent(tools=[LLMTool(provider=FailingHookLLMProvider())])
        task = create_hook_task()

        with self.assertRaises(RuntimeError):
            agent.run(task)

        self.assertIs(task.status, TaskStatus.FAILED)
        self.assertEqual(task.error_message, "hook llm failed")

    def test_errors_are_propagated(self) -> None:
        """LLM errors are propagated unchanged."""
        agent = HookAgent(tools=[LLMTool(provider=FailingHookLLMProvider())])
        task = create_hook_task()

        with self.assertRaisesRegex(RuntimeError, "hook llm failed"):
            agent.run(task)


if __name__ == "__main__":
    unittest.main()
