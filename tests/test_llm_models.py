"""Tests for LLM request and response models."""

import unittest

from engine.llm.base_provider import BaseLLMProvider
from engine.llm.models import LLMProviderConfig, LLMRequest


class LLMModelsTestCase(unittest.TestCase):
    """Tests for LLM model behavior."""

    def test_valid_llm_provider_config_can_be_created(self) -> None:
        """A valid LLMProviderConfig stores the provided values."""
        config = LLMProviderConfig(
            provider_id="mock",
            model="mock-model",
            default_temperature=0.4,
            default_max_tokens=500,
        )

        self.assertEqual(config.provider_id, "mock")
        self.assertEqual(config.model, "mock-model")
        self.assertEqual(config.default_temperature, 0.4)
        self.assertEqual(config.default_max_tokens, 500)

    def test_empty_provider_id_raises_value_error(self) -> None:
        """An empty provider_id is invalid."""
        with self.assertRaises(ValueError):
            LLMProviderConfig(provider_id="", model="mock-model")

    def test_empty_model_raises_value_error(self) -> None:
        """An empty model is invalid."""
        with self.assertRaises(ValueError):
            LLMProviderConfig(provider_id="mock", model=" ")

    def test_provider_config_temperature_below_zero_raises_value_error(self) -> None:
        """Provider default temperature must not be below 0.0."""
        with self.assertRaises(ValueError):
            LLMProviderConfig(
                provider_id="mock",
                model="mock-model",
                default_temperature=-0.1,
            )

    def test_provider_config_temperature_above_two_raises_value_error(self) -> None:
        """Provider default temperature must not be above 2.0."""
        with self.assertRaises(ValueError):
            LLMProviderConfig(
                provider_id="mock",
                model="mock-model",
                default_temperature=2.1,
            )

    def test_provider_config_max_tokens_zero_raises_value_error(self) -> None:
        """Provider default_max_tokens must be greater than 0 when provided."""
        with self.assertRaises(ValueError):
            LLMProviderConfig(
                provider_id="mock",
                model="mock-model",
                default_max_tokens=0,
            )

    def test_valid_llm_request_can_be_created(self) -> None:
        """A valid LLMRequest stores the provided values."""
        request = LLMRequest(
            system_prompt="You are helpful.",
            user_prompt="Write a summary.",
            temperature=0.5,
            max_tokens=100,
        )

        self.assertEqual(request.system_prompt, "You are helpful.")
        self.assertEqual(request.user_prompt, "Write a summary.")
        self.assertEqual(request.temperature, 0.5)
        self.assertEqual(request.max_tokens, 100)

    def test_empty_system_prompt_raises_value_error(self) -> None:
        """An empty system prompt is invalid."""
        with self.assertRaises(ValueError):
            LLMRequest(system_prompt="", user_prompt="Write a summary.")

    def test_empty_user_prompt_raises_value_error(self) -> None:
        """An empty user prompt is invalid."""
        with self.assertRaises(ValueError):
            LLMRequest(system_prompt="You are helpful.", user_prompt=" ")

    def test_temperature_below_zero_raises_value_error(self) -> None:
        """Temperature must not be below 0.0."""
        with self.assertRaises(ValueError):
            LLMRequest(
                system_prompt="You are helpful.",
                user_prompt="Write a summary.",
                temperature=-0.1,
            )

    def test_temperature_above_two_raises_value_error(self) -> None:
        """Temperature must not be above 2.0."""
        with self.assertRaises(ValueError):
            LLMRequest(
                system_prompt="You are helpful.",
                user_prompt="Write a summary.",
                temperature=2.1,
            )

    def test_max_tokens_zero_raises_value_error(self) -> None:
        """max_tokens must be greater than 0 when provided."""
        with self.assertRaises(ValueError):
            LLMRequest(
                system_prompt="You are helpful.",
                user_prompt="Write a summary.",
                max_tokens=0,
            )

    def test_max_tokens_below_zero_raises_value_error(self) -> None:
        """max_tokens must not be negative."""
        with self.assertRaises(ValueError):
            LLMRequest(
                system_prompt="You are helpful.",
                user_prompt="Write a summary.",
                max_tokens=-1,
            )

    def test_base_llm_provider_is_abstract(self) -> None:
        """BaseLLMProvider cannot be instantiated directly."""
        with self.assertRaises(TypeError):
            BaseLLMProvider(provider_id="base", model="model")  # type: ignore[abstract]


if __name__ == "__main__":
    unittest.main()
