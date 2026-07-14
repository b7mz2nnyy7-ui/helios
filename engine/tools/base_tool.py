"""Base abstraction for Helios tools."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class BaseTool(ABC):
    """Abstract base class for all Helios tools."""

    tool_id: str
    name: str
    description: str

    @abstractmethod
    def execute(self, **kwargs: Any) -> Any:
        """Execute the tool with keyword arguments."""
