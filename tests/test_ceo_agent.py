"""Tests for the Helios CEO agent."""

import unittest

from agents.business_intelligence.models import (
    BusinessIntelligenceReport,
    BusinessKPI,
    BusinessOpportunity,
    BusinessRisk,
    BusinessRiskSeverity,
)
from agents.ceo.agent import CEOAgent
from agents.ceo.mock_llm_provider import MockCEOLLMProvider
from agents.ceo.models import CompanyPriority, ExecutiveDecision, ExecutiveDecisionReport
from engine.llm.base_provider import BaseLLMProvider
from engine.llm.models import LLMRequest, LLMResponse
from engine.runtime.capability import AgentCapability
from engine.tasks.priority import TaskPriority
from engine.tasks.status import TaskStatus
from engine.tasks.task import Task
from engine.tools.llm_tool import LLMTool


class RecordingCEOLLMProvider(BaseLLMProvider):
    """LLM provider that records CEO requests."""

    def __init__(self) -> None:
        """Create a recording provider."""
        super().__init__(provider_id="recording", model="recording-ceo-model")
        self.received_request: LLMRequest | None = None
        self.response = MockCEOLLMProvider(
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


class FailingCEOLLMProvider(BaseLLMProvider):
    """LLM provider that always fails."""

    def __init__(self) -> None:
        """Create a failing provider."""
        super().__init__(provider_id="failing", model="failing-ceo-model")

    def generate(self, request: LLMRequest) -> LLMResponse:
        """Raise a runtime error."""
        msg = "ceo llm failed"
        raise RuntimeError(msg)


def create_business_report() -> BusinessIntelligenceReport:
    """Create a business intelligence report for CEO tests."""
    return BusinessIntelligenceReport(
        kpis=[
            BusinessKPI(
                name="Total Views",
                value="1750",
                description="Current portfolio-level demand signal.",
            ),
        ],
        opportunities=[
            BusinessOpportunity(
                title="Checklist CTA Lift",
                probability=0.82,
                impact="High near-term growth upside",
                recommendation="Prioritize checklist-led variants.",
            ),
        ],
        risks=[
            BusinessRisk(
                title="Platform Engagement Gap",
                severity=BusinessRiskSeverity.MEDIUM,
                mitigation="Recut weak-platform pacing.",
            ),
        ],
        priorities=["Launch the checklist CTA experiment first."],
        executive_summary=(
            "Athena recommends prioritizing Checklist CTA Lift because it is "
            "the strongest prediction."
        ),
        generated_by="mock:mock-business-model",
    )


def create_ceo_task(payload: dict[str, object] | None = None) -> Task:
    """Create a CEO task."""
    return Task(
        task_id="ceo-task-1",
        title="CEO Decision",
        description="Create executive decision report.",
        priority=TaskPriority.MEDIUM,
        required_capability=AgentCapability.CEO,
        payload=(
            {"business_report": create_business_report()}
            if payload is None
            else payload
        ),
    )


class CEOAgentTestCase(unittest.TestCase):
    """Tests for CEOAgent behavior."""

    def test_agent_has_ceo_capability(self) -> None:
        """Helios declares the CEO capability."""
        agent = CEOAgent()

        self.assertTrue(agent.can_handle(AgentCapability.CEO))

    def test_agent_name_is_helios(self) -> None:
        """CEO agent has the expected display name."""
        agent = CEOAgent()

        self.assertEqual(agent.name, "Helios")

    def test_default_provider_exists(self) -> None:
        """Helios has a default LLM tool."""
        agent = CEOAgent()

        self.assertIsInstance(agent.get_tool("llm"), LLMTool)

    def test_payload_validated_and_task_completed(self) -> None:
        """A valid business report completes the task."""
        agent = CEOAgent()
        task = create_ceo_task()

        report = agent.run(task)

        self.assertIsInstance(report, ExecutiveDecisionReport)
        self.assertIs(task.status, TaskStatus.COMPLETED)

    def test_missing_business_report_raises_value_error(self) -> None:
        """Helios rejects missing BusinessIntelligenceReport payloads."""
        agent = CEOAgent()
        task = create_ceo_task({"business_report": "invalid"})

        with self.assertRaises(ValueError):
            agent.run(task)

    def test_task_result_and_last_decision_report_are_identical(self) -> None:
        """Helios stores the report and writes it to the task."""
        agent = CEOAgent()
        task = create_ceo_task()

        report = agent.run(task)

        self.assertIs(task.result, report)
        self.assertIs(agent.last_decision_report, report)

    def test_report_contains_required_sections(self) -> None:
        """Helios creates at least one priority and decision."""
        agent = CEOAgent()
        task = create_ceo_task()

        report = agent.run(task)

        self.assertGreaterEqual(len(report.priorities), 1)
        self.assertGreaterEqual(len(report.decisions), 1)

    def test_prompt_contains_business_report_sections(self) -> None:
        """Helios prompt contains executive summary, KPIs, risks and opportunities."""
        provider = RecordingCEOLLMProvider()
        agent = CEOAgent(tools=[LLMTool(provider=provider)])
        task = create_ceo_task()

        agent.run(task)

        request = provider.received_request
        assert request is not None
        self.assertIn("Executive Summary", request.user_prompt)
        self.assertIn("Checklist CTA Lift", request.user_prompt)
        self.assertIn("KPIs", request.user_prompt)
        self.assertIn("Total Views", request.user_prompt)
        self.assertIn("Risiken", request.user_prompt)
        self.assertIn("Platform Engagement Gap", request.user_prompt)
        self.assertIn("Opportunities", request.user_prompt)
        self.assertIn("Priorities", request.user_prompt)
        self.assertEqual(
            request.system_prompt,
            "Helios trifft strategische Unternehmensentscheidungen.",
        )

    def test_mock_provider_is_deterministic(self) -> None:
        """MockCEOLLMProvider returns deterministic responses."""
        provider = MockCEOLLMProvider()
        request = LLMRequest(system_prompt="Helios", user_prompt="Business report")

        first_response = provider.generate(request)
        second_response = provider.generate(request)

        self.assertEqual(first_response, second_response)
        self.assertEqual(first_response.provider, "mock")
        self.assertEqual(first_response.model, "mock-ceo-model")

    def test_confidence_is_validated(self) -> None:
        """ExecutiveDecision validates confidence."""
        with self.assertRaises(ValueError):
            ExecutiveDecision(
                title="Invalid",
                rationale="Invalid.",
                expected_impact="None.",
                confidence=1.1,
            )

    def test_priority_score_is_validated(self) -> None:
        """CompanyPriority validates priority score."""
        with self.assertRaises(ValueError):
            CompanyPriority(
                title="Invalid",
                reason="Invalid.",
                priority_score=1.1,
            )

    def test_report_to_markdown(self) -> None:
        """ExecutiveDecisionReport can be rendered as Markdown."""
        agent = CEOAgent()
        task = create_ceo_task()

        report = agent.run(task)

        markdown = report.to_markdown()
        self.assertIn("# Executive Decision Report", markdown)
        self.assertIn("Scale Checklist CTA Experiment", markdown)
        self.assertIn("Approve next content batch", markdown)

    def test_llm_failure_sets_task_failed(self) -> None:
        """LLM errors move the task to FAILED."""
        agent = CEOAgent(tools=[LLMTool(provider=FailingCEOLLMProvider())])
        task = create_ceo_task()

        with self.assertRaises(RuntimeError):
            agent.run(task)

        self.assertIs(task.status, TaskStatus.FAILED)
        self.assertEqual(task.error_message, "ceo llm failed")

    def test_errors_are_propagated(self) -> None:
        """LLM errors are propagated unchanged."""
        agent = CEOAgent(tools=[LLMTool(provider=FailingCEOLLMProvider())])
        task = create_ceo_task()

        with self.assertRaisesRegex(RuntimeError, "ceo llm failed"):
            agent.run(task)


if __name__ == "__main__":
    unittest.main()
