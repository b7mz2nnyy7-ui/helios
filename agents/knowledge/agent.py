"""Sage knowledge agent."""

from typing import Protocol

from agents.knowledge.mock_provider import MockKnowledgeProvider
from agents.knowledge.models import KnowledgeCategory, KnowledgeItem, KnowledgeResponse
from engine.llm.models import LLMRequest
from engine.runtime.base_agent import BaseAgent
from engine.runtime.capability import AgentCapability
from engine.tasks.status import TaskStatus
from engine.tasks.task import Task


class KnowledgeProvider(Protocol):
    """Provider protocol for deterministic knowledge retrieval."""

    provider_id: str
    model: str

    def search(self, request: LLMRequest) -> list[KnowledgeItem]:
        """Return knowledge items for a request."""


class KnowledgeAgent(BaseAgent):
    """Sage agent for retrieving structured company knowledge."""

    provider: KnowledgeProvider
    last_response: KnowledgeResponse | None

    def __init__(self, provider: KnowledgeProvider | None = None) -> None:
        """Create the Sage knowledge agent."""
        super().__init__(
            agent_id="knowledge",
            name="Sage",
            capabilities={AgentCapability.KNOWLEDGE},
        )
        self.provider = provider or MockKnowledgeProvider()
        self.last_response = None

    def run(self, task: Task) -> KnowledgeResponse:
        """Create a knowledge response from a query task."""
        if task.required_capability is not AgentCapability.KNOWLEDGE:
            msg = "KnowledgeAgent can only handle KNOWLEDGE tasks."
            raise ValueError(msg)

        task.start()
        try:
            query = self._get_query(task.payload.get("query"))
            request = self._create_request(query)
            items = self.provider.search(request)
            response = KnowledgeResponse(
                query=query,
                summary=f"Knowledge response for: {query}",
                items=items,
                generated_by=f"{self.provider.provider_id}:{self.provider.model}",
            )
            self.last_response = response
            task.complete(response)
            return response
        except Exception as error:
            if task.status is TaskStatus.RUNNING:
                task.fail(str(error))
            raise

    def _get_query(self, value: object) -> str:
        if not isinstance(value, str) or not value.strip():
            msg = "query must be a non-empty string."
            raise ValueError(msg)

        return value.strip()

    def _create_request(self, query: str) -> LLMRequest:
        categories = ", ".join(category.value for category in KnowledgeCategory)
        return LLMRequest(
            system_prompt="Sage verwaltet das Unternehmenswissen der AI Content Company.",
            user_prompt=(
                f"Query: {query}\n"
                f"Gewünschte Kategorien: {categories}\n\n"
                "Ziel:\n"
                "- Marketing\n"
                "- Storytelling\n"
                "- Copywriting\n"
                "- Psychologie\n"
                "- Frameworks"
            ),
        )
