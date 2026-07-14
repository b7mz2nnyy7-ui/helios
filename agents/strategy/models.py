"""Models for the Nova strategy agent."""

from dataclasses import dataclass


@dataclass
class ContentIdea:
    """A single content idea in a strategy."""

    title: str
    angle: str
    target_platform: str
    reason: str


@dataclass
class ContentStrategy:
    """Structured content strategy generated from trend research."""

    query: str
    summary: str
    ideas: list[ContentIdea]
    generated_by: str

