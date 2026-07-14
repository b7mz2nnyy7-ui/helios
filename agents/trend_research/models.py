"""Models for trend research agents."""

from dataclasses import dataclass


@dataclass
class TrendResult:
    """A deterministic trend research result."""

    topic: str
    score: float
    source: str
    reason: str
