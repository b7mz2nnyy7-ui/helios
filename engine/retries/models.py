"""Models for deterministic task retry decisions."""

from dataclasses import dataclass


@dataclass(frozen=True)
class RetryDecision:
    """Decision returned by a retry policy evaluation."""

    should_retry: bool
    attempt: int
    max_attempts: int
    reason: str

