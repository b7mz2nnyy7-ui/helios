"""Tests for the generic LLM tool."""

import unittest

from engine.llm.base_provider import BaseLLMProvider
from engine.llm.models import LLMRequest, LLMResponse
from engine.tools.llm_tool import LLMTool


class RecordingLLMProvider(BaseLLMProvider):
    """Provider that records requests and returns a fixed response."""

    def __init__(self) -> None:
        """Create a recording provider."""
        super().__init__(provider_id="test_provider", model="test-model")
        self.received_request: LLMRequest | None = None
        self.response = LLMResponse(
            content="Generated text.",
            model=self.model,
            provider=self.provider_id,
            input_tokens=10,
            output_tokens=5,
        )

    def generate(self, request: LLMRequest) -> LLMResponse:
        """Record the request and return the fixed response."""
        self.received_request = request
        return self.response


class FailingLLMProvider(BaseLLMProvider):
    """Provider that always fails."""

    def __init__(self) -> None:
        """Create a failing provider."""
        super().__init__(provider_id="failing_provider", model="test-model")

    def generate(self, request: LLMRequest) -> LLMResponse:
        """Raise a runtime error."""
        msg = "provider failed"
        raise RuntimeError(msg)


class LLMToolTestCase(unittest.TestCase):
    """Tests for LLMTool behavior."""

    def test_execute_calls_provider_with_same_request(self) -> None:
        """LLMTool passes the same request object to the provider."""
        provider = RecordingLLMProvider()
        tool = LLMTool(provider=provider)
        request = LLMRequest(
            system_prompt="You are helpful.",
            user_prompt="Write a summary.",
        )

        tool.execute(request=request)

        self.assertIs(provider.received_request, request)

    def test_execute_returns_provider_response(self) -> None:
        """LLMTool returns the exact provider response."""
        provider = RecordingLLMProvider()
        tool = LLMTool(provider=provider)
        request = LLMRequest(
            system_prompt="You are helpful.",
            user_prompt="Write a summary.",
        )

        response = tool.execute(request=request)

        self.assertIs(response, provider.response)

    def test_execute_without_request_raises_value_error(self) -> None:
        """LLMTool requires a request argument."""
        tool = LLMTool(provider=RecordingLLMProvider())

        with self.assertRaises(ValueError):
            tool.execute()

    def test_execute_with_wrong_request_type_raises_value_error(self) -> None:
        """LLMTool rejects non-LLMRequest request values."""
        tool = LLMTool(provider=RecordingLLMProvider())

        with self.assertRaises(ValueError):
            tool.execute(request="not a request")

    def test_provider_error_is_propagated(self) -> None:
        """Provider errors are propagated unchanged."""
        tool = LLMTool(provider=FailingLLMProvider())
        request = LLMRequest(
            system_prompt="You are helpful.",
            user_prompt="Write a summary.",
        )

        with self.assertRaisesRegex(RuntimeError, "provider failed"):
            tool.execute(request=request)


if __name__ == "__main__":
    unittest.main()
