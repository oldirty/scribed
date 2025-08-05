"""Unified output handler for managing multiple output destinations."""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from .base import OutputDestination, OutputResult, OutputStatus, OutputError
from .file import FileOutput
from .clipboard import ClipboardOutput
from .console import ConsoleOutput

logger = logging.getLogger(__name__)


@dataclass
class OutputConfig:
    """Configuration for output handling."""

    format: str = "txt"
    save_to_file: bool = True
    copy_to_clipboard: bool = False
    console_output: bool = False
    file_config: Optional[Dict[str, Any]] = None
    clipboard_config: Optional[Dict[str, Any]] = None
    console_config: Optional[Dict[str, Any]] = None


class OutputHandler:
    """Unified output handler that manages multiple output destinations."""

    def __init__(self, config: OutputConfig):
        """Initialize output handler with configuration.

        Args:
            config: Output configuration
        """
        self.config = config
        self.destinations: List[OutputDestination] = []
        self._setup_destinations()

    def _setup_destinations(self) -> None:
        """Set up output destinations based on configuration."""
        try:
            # File output
            if self.config.save_to_file:
                file_config = self.config.file_config or {}
                file_config.setdefault("format", self.config.format)
                file_output = FileOutput(file_config)
                if file_output.is_available():
                    self.destinations.append(file_output)
                    logger.info("File output destination enabled")
                else:
                    logger.warning("File output destination not available")

            # Clipboard output
            if self.config.copy_to_clipboard:
                clipboard_config = self.config.clipboard_config or {}
                clipboard_output = ClipboardOutput(clipboard_config)
                if clipboard_output.is_available():
                    self.destinations.append(clipboard_output)
                    logger.info("Clipboard output destination enabled")
                else:
                    logger.warning("Clipboard output destination not available")

            # Console output
            if self.config.console_output:
                console_config = self.config.console_config or {}
                console_output = ConsoleOutput(console_config)
                if console_output.is_available():
                    self.destinations.append(console_output)
                    logger.info("Console output destination enabled")
                else:
                    logger.warning("Console output destination not available")

            if not self.destinations:
                logger.warning("No output destinations available")

        except Exception as e:
            logger.error(f"Error setting up output destinations: {e}")
            raise OutputError(f"Failed to initialize output handler: {e}")

    async def write_transcription(
        self, text: str, metadata: Optional[Dict[str, Any]] = None
    ) -> List[OutputResult]:
        """Write transcription to all configured destinations.

        Args:
            text: The transcription text to write
            metadata: Optional metadata about the transcription

        Returns:
            List of OutputResult objects, one for each destination
        """
        if not text.strip():
            logger.warning("Empty transcription text provided")
            return []

        results = []

        for destination in self.destinations:
            try:
                logger.debug(f"Writing to {destination.name}")
                result = await destination.write(text, metadata)
                results.append(result)

                if result.status == OutputStatus.SUCCESS:
                    logger.info(
                        f"Successfully wrote to {destination.name}: {result.message}"
                    )
                else:
                    logger.warning(
                        f"Failed to write to {destination.name}: {result.error}"
                    )

            except Exception as e:
                error_msg = f"Unexpected error writing to {destination.name}: {e}"
                logger.error(error_msg)
                results.append(
                    OutputResult(
                        status=OutputStatus.FAILED,
                        message="Unexpected error",
                        destination=destination.name,
                        error=error_msg,
                    )
                )

        return results

    def get_available_destinations(self) -> List[str]:
        """Get list of available destination names.

        Returns:
            List of destination names that are available
        """
        return [dest.name for dest in self.destinations if dest.is_available()]

    def is_any_destination_available(self) -> bool:
        """Check if any output destination is available.

        Returns:
            True if at least one destination is available
        """
        return any(dest.is_available() for dest in self.destinations)

    def add_destination(self, destination: OutputDestination) -> None:
        """Add a custom output destination.

        Args:
            destination: The output destination to add
        """
        if destination.is_available():
            self.destinations.append(destination)
            logger.info(f"Added custom output destination: {destination.name}")
        else:
            logger.warning(f"Custom destination {destination.name} is not available")

    def remove_destination(self, destination_name: str) -> bool:
        """Remove an output destination by name.

        Args:
            destination_name: Name of the destination to remove

        Returns:
            True if destination was found and removed
        """
        for i, dest in enumerate(self.destinations):
            if dest.name == destination_name:
                removed = self.destinations.pop(i)
                logger.info(f"Removed output destination: {removed.name}")
                return True

        logger.warning(f"Destination {destination_name} not found")
        return False
