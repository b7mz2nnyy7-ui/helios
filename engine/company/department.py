"""Department definitions for the Helios company architecture."""

from enum import StrEnum


class Department(StrEnum):
    """Departments in the Helios AI company model."""

    EXECUTIVE = "EXECUTIVE"
    OPERATIONS = "OPERATIONS"
    RESEARCH = "RESEARCH"
    STRATEGY = "STRATEGY"
    KNOWLEDGE = "KNOWLEDGE"
    WRITING = "WRITING"
    CREATIVE = "CREATIVE"
    PRODUCTION = "PRODUCTION"
    DISTRIBUTION = "DISTRIBUTION"
    ANALYTICS = "ANALYTICS"
    MEMORY = "MEMORY"
    OPTIMIZATION = "OPTIMIZATION"
    COMPLIANCE = "COMPLIANCE"

