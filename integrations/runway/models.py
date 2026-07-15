"""Provider-specific request and task models for Runway."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class RunwayGenerationRequest:
    """Structured request passed to a Runway transport."""

    model: str
    prompt_text: str
    ratio: str
    duration_seconds: float
    seed: int | None = None

    def __post_init__(self) -> None:
        """Validate required generation request values."""
        required_text = {
            "model": self.model,
            "prompt_text": self.prompt_text,
            "ratio": self.ratio,
        }
        for field_name, value in required_text.items():
            if not value.strip():
                msg = f"{field_name} must not be empty."
                raise ValueError(msg)

        if self.duration_seconds <= 0:
            msg = "duration_seconds must be greater than 0."
            raise ValueError(msg)


@dataclass(frozen=True)
class RunwayTask:
    """Provider-neutral view of a Runway generation task."""

    task_id: str
    status: str
    output_urls: tuple[str, ...] = field(default_factory=tuple)
    failure_message: str | None = None

    def __post_init__(self) -> None:
        """Validate required task response values."""
        if not self.task_id.strip():
            msg = "task_id must not be empty."
            raise ValueError(msg)

        if not self.status.strip():
            msg = "status must not be empty."
            raise ValueError(msg)

        if not isinstance(self.output_urls, tuple):
            msg = "output_urls must be a tuple."
            raise ValueError(msg)

        if any(not isinstance(url, str) or not url.strip() for url in self.output_urls):
            msg = "output_urls must contain non-empty strings."
            raise ValueError(msg)

        if self.failure_message is not None and not self.failure_message.strip():
            msg = "failure_message must not be empty when configured."
            raise ValueError(msg)
