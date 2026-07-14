"""Provider-neutral LLM request and response models."""

from dataclasses import dataclass


@dataclass
class LLMProviderConfig:
    """Provider-neutral configuration for an LLM provider."""

    provider_id: str
    model: str
    default_temperature: float = 0.2
    default_max_tokens: int | None = None

    def __post_init__(self) -> None:
        """Validate provider configuration values."""
        if not self.provider_id.strip():
            msg = "provider_id must not be empty."
            raise ValueError(msg)

        if not self.model.strip():
            msg = "model must not be empty."
            raise ValueError(msg)

        if not 0.0 <= self.default_temperature <= 2.0:
            msg = "default_temperature must be between 0.0 and 2.0."
            raise ValueError(msg)

        if self.default_max_tokens is not None and self.default_max_tokens <= 0:
            msg = "default_max_tokens must be None or greater than 0."
            raise ValueError(msg)


@dataclass
class LLMRequest:
    """Request sent to an LLM provider."""

    system_prompt: str
    user_prompt: str
    temperature: float = 0.2
    max_tokens: int | None = None

    def __post_init__(self) -> None:
        """Validate request values."""
        if not self.system_prompt.strip():
            msg = "system_prompt must not be empty."
            raise ValueError(msg)

        if not self.user_prompt.strip():
            msg = "user_prompt must not be empty."
            raise ValueError(msg)

        if not 0.0 <= self.temperature <= 2.0:
            msg = "temperature must be between 0.0 and 2.0."
            raise ValueError(msg)

        if self.max_tokens is not None and self.max_tokens <= 0:
            msg = "max_tokens must be None or greater than 0."
            raise ValueError(msg)


@dataclass
class LLMResponse:
    """Response returned by an LLM provider."""

    content: str
    model: str
    provider: str
    input_tokens: int | None = None
    output_tokens: int | None = None
