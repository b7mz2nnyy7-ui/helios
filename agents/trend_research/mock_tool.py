"""Mock trend research tool."""

from dataclasses import dataclass
from typing import Any

from agents.trend_research.models import TrendResult
from engine.tools.base_tool import BaseTool


@dataclass
class MockTrendTool(BaseTool):
    """Tool that returns deterministic trend research data."""

    tool_id: str = "mock_trend_tool"
    name: str = "Mock Trend Tool"
    description: str = "Returns deterministic trend research data for tests."

    def execute(self, **kwargs: Any) -> list[TrendResult]:
        """Return deterministic trend results for a query.

        Raises:
            ValueError: If query is missing or empty.
        """
        query = kwargs.get("query")
        if not isinstance(query, str) or not query.strip():
            msg = "query must be a non-empty string."
            raise ValueError(msg)

        return [
            TrendResult(
                topic=f"{query} automation",
                score=0.92,
                source="mock:search",
                reason="High deterministic search interest in automation angles.",
            ),
            TrendResult(
                topic=f"{query} workflow",
                score=0.84,
                source="mock:social",
                reason="Consistent deterministic discussion around workflow use cases.",
            ),
            TrendResult(
                topic=f"{query} strategy",
                score=0.78,
                source="mock:content",
                reason="Stable deterministic content demand for strategy breakdowns.",
            ),
        ]
