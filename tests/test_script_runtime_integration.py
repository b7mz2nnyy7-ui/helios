"""Runtime integration tests for Orion script agent."""

import unittest

from agents.audience_research.models import AudiencePainPoint, AudienceProfile
from agents.knowledge.models import (
    KnowledgeCategory,
    KnowledgeItem,
    KnowledgeResponse,
)
from agents.script.agent import ScriptAgent
from agents.script.models import VideoScript
from agents.strategy.models import ContentIdea, ContentStrategy
from agents.trend_research.models import TrendResult
from agents.trend_research.report import TrendReport
from engine.runtime.capability import AgentCapability
from engine.runtime.runtime import HeliosRuntime
from engine.tasks.priority import TaskPriority
from engine.tasks.status import TaskStatus
from engine.tasks.task import Task


def create_script_task(payload: dict[str, object] | None = None) -> Task:
    """Create a script task for runtime integration tests."""
    task_payload = {
        "trend_report": TrendReport(
            query="AI Agents",
            summary="AI agents are becoming workflow tools.",
            trends=[
                TrendResult("AI workflow automation", 0.92, "mock", "High demand."),
            ],
            generated_by="mock:mock-trend-model",
        ),
        "audience_profile": AudienceProfile(
            topic="AI Agents",
            target_age_range="18-34",
            language="de",
            interests=["Automation"],
            pain_points=[AudiencePainPoint("Tool overload", 0.82, "Frustration")],
            preferred_tone="Clear",
            preferred_platforms=["YouTube"],
            summary="Creators want practical workflows.",
            generated_by="mock:mock-audience-model",
        ),
        "knowledge_response": KnowledgeResponse(
            query="AI content strategy",
            summary="Use specificity.",
            items=[
                KnowledgeItem(
                    "Audience Promise",
                    KnowledgeCategory.MARKETING,
                    "Clarify the promise.",
                    "internal",
                    0.91,
                ),
            ],
            generated_by="mock:mock-knowledge-model",
        ),
        "content_strategy": ContentStrategy(
            query="AI Agents",
            summary="Make practical AI workflows easy to understand.",
            ideas=[
                ContentIdea(
                    "Workflow Demo",
                    "Practical implementation",
                    "YouTube",
                    "Shows repeatable workflows.",
                ),
            ],
            generated_by="mock:mock-strategy-model",
        ),
    }
    return Task(
        task_id="script-task-1",
        title="Script",
        description="Create video script from company intelligence.",
        priority=TaskPriority.MEDIUM,
        required_capability=AgentCapability.SCRIPT,
        payload=task_payload if payload is None else payload,
    )


class ScriptRuntimeIntegrationTestCase(unittest.TestCase):
    """Integration tests for Orion through HeliosRuntime."""

    def test_runtime_dispatches_script_task_to_orion(self) -> None:
        """Runtime can dispatch SCRIPT tasks to Orion."""
        runtime = HeliosRuntime()
        orion = ScriptAgent()
        task = create_script_task()
        runtime.register(orion)

        result = runtime.submit_task(task)

        self.assertIsInstance(result, VideoScript)
        self.assertIs(result, task.result)
        self.assertIs(task.status, TaskStatus.COMPLETED)
        self.assertIs(orion.last_script, result)

    def test_runtime_returns_video_script(self) -> None:
        """Runtime returns the VideoScript from Orion."""
        runtime = HeliosRuntime()
        runtime.register(ScriptAgent())
        task = create_script_task()

        result = runtime.submit_task(task)

        self.assertIsInstance(result, VideoScript)

    def test_runtime_propagates_orion_errors(self) -> None:
        """Runtime propagates Orion validation errors."""
        runtime = HeliosRuntime()
        runtime.register(ScriptAgent())
        task = create_script_task({"trend_report": "invalid"})

        with self.assertRaises(ValueError):
            runtime.submit_task(task)

        self.assertIs(task.status, TaskStatus.FAILED)


if __name__ == "__main__":
    unittest.main()
