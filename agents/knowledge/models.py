"""Models for the Sage knowledge agent."""

from dataclasses import dataclass
from enum import StrEnum


class KnowledgeCategory(StrEnum):
    """Categories of reusable company knowledge."""

    MARKETING = "MARKETING"
    STORYTELLING = "STORYTELLING"
    PSYCHOLOGY = "PSYCHOLOGY"
    COPYWRITING = "COPYWRITING"
    SOCIAL_MEDIA = "SOCIAL_MEDIA"
    SEO = "SEO"
    FRAMEWORKS = "FRAMEWORKS"


@dataclass
class KnowledgeItem:
    """A structured knowledge item returned by Sage."""

    title: str
    category: KnowledgeCategory
    content: str
    source: str
    confidence: float

    def __post_init__(self) -> None:
        """Validate knowledge item values."""
        if not 0.0 <= self.confidence <= 1.0:
            msg = "confidence must be between 0.0 and 1.0."
            raise ValueError(msg)


@dataclass
class KnowledgeResponse:
    """Structured knowledge response generated from a query."""

    query: str
    summary: str
    items: list[KnowledgeItem]
    generated_by: str
