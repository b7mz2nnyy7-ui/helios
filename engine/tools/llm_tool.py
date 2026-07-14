"""Generic LLM tool."""

from typing import Any

from engine.llm.base_provider import BaseLLMProvider
from engine.llm.models import LLMRequest, LLMResponse
from engine.tools.base_tool import BaseTool


class LLMTool(BaseTool):
    """Tool that generates text through a configured LLM provider."""

    provider: BaseLLMProvider

    def __init__(self, provider: BaseLLMProvider) -> None:
        """Create an LLM tool for a provider."""
        super().__init__(
            tool_id="llm",
            name="LLM Tool",
            description="Generates text through a configured LLM provider.",
        )
        self.provider = provider

    def execute(self, **kwargs: Any) -> LLMResponse:
        """Execute the LLM provider with an LLM request.

        Raises:
            ValueError: If request is missing or not an LLMRequest.
        """
        request = kwargs.get("request")
        if not isinstance(request, LLMRequest):
            msg = "request must be an LLMRequest."
            raise ValueError(msg)

        return self.provider.generate(request)
