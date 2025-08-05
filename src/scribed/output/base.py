"""Base classes for output handling."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Dict, Any
from enum import Enum


class OutputStatus(Enum):
    """Status of output operation."""

    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"


@dataclass
class OutputResult:
    """Result of an output operation."""

    status: OutputStatus
    message: str
    destination: str
    metadata: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class OutputError(Exception):
    """Base exception for output operations."""

    pass


class OutputDestination(ABC):
    """Abstract base class for output destinations."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize output destination with configuration.

        Args:
            config: Configuration dictionary for this output destination
        """
        self.config = config
        self._validate_config()

    @abstractmethod
    def _validate_config(self) -> None:
        """Validate the configuration for this output destination.

        Raises:
            OutputError: If configuration is invalid
        """
        pass

    @abstractmethod
    async def write(
        self, text: str, metadata: Optional[Dict[str, Any]] = None
    ) -> OutputResult:
        """Write text to this output destination.

        Args:
            text: The text to write
            metadata: Optional metadata about the transcription

        Returns:
            OutputResult indicating success or failure
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this output destination is available.

        Returns:
            True if the destination is available, False otherwise
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Get the name of this output destination."""
        pass
