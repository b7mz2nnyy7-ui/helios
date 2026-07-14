"""Models for the Mira audience research agent."""

from dataclasses import dataclass


@dataclass
class AudiencePainPoint:
    """A problem or concern within a target audience."""

    problem: str
    severity: float
    emotional_driver: str


@dataclass
class AudienceProfile:
    """Structured audience profile generated from a topic."""

    topic: str
    target_age_range: str
    language: str
    interests: list[str]
    pain_points: list[AudiencePainPoint]
    preferred_tone: str
    preferred_platforms: list[str]
    summary: str
    generated_by: str
