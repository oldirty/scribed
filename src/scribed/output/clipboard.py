"""Clipboard output destination for copying transcriptions to clipboard."""

import logging
from typing import Dict, Any, Optional

from .base import OutputDestination, OutputResult, OutputStatus, OutputError

logger = logging.getLogger(__name__)


class ClipboardOutput(OutputDestination):
    """Output destination that copies transcriptions to clipboard."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize clipboard output with configuration."""
        super().__init__(config)
        self._clipboard_manager = None
        self._init_clipboard()

    def _validate_config(self) -> None:
        """Validate clipboard output configuration."""
        # Set defaults
        self.config.setdefault("include_metadata", False)
        self.config.setdefault("format", "plain")  # plain or formatted
        self.config.setdefault("max_length", None)  # Optional length limit

    def _init_clipboard(self) -> None:
        """Initialize clipboard manager."""
        try:
            from scribed.clipboard import get_clipboard_manager

            self._clipboard_manager = get_clipboard_manager()
        except ImportError as e:
            logger.error(f"Failed to import clipboard manager: {e}")
            self._clipboard_manager = None

    async def write(
        self, text: str, metadata: Optional[Dict[str, Any]] = None
    ) -> OutputResult:
        """Write transcription to clipboard.

        Args:
            text: The transcription text
            metadata: Optional metadata about the transcription

        Returns:
            OutputResult indicating success or failure
        """
        if not self._clipboard_manager:
            return OutputResult(
                status=OutputStatus.FAILED,
                message="Clipboard not available",
                destination=self.name,
                error="Clipboard manager not initialized",
            )

        try:
            # Format content for clipboard
            content = self._format_content(text, metadata)

            # Apply length limit if configured
            if self.config["max_length"] and len(content) > self.config["max_length"]:
                content = content[: self.config["max_length"]] + "..."
                logger.warning(
                    f"Clipboard content truncated to {self.config['max_length']} characters"
                )

            # Copy to clipboard
            success = self._clipboard_manager.set_text(content)

            if success:
                return OutputResult(
                    status=OutputStatus.SUCCESS,
                    message=f"Copied {len(content)} characters to clipboard",
                    destination=self.name,
                    metadata={"content_length": len(content)},
                )
            else:
                return OutputResult(
                    status=OutputStatus.FAILED,
                    message="Failed to copy to clipboard",
                    destination=self.name,
                    error="Clipboard operation failed",
                )

        except Exception as e:
            error_msg = f"Clipboard write error: {e}"
            logger.error(error_msg)
            return OutputResult(
                status=OutputStatus.FAILED,
                message="Clipboard write failed",
                destination=self.name,
                error=error_msg,
            )

    def _format_content(
        self, text: str, metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Format content for clipboard based on configuration.

        Args:
            text: The transcription text
            metadata: Optional metadata

        Returns:
            Formatted content for clipboard
        """
        if self.config["format"] == "plain":
            # Just the transcription text
            return text.strip()

        elif (
            self.config["format"] == "formatted"
            and self.config["include_metadata"]
            and metadata
        ):
            # Include basic metadata
            content = []

            # Add timestamp if available
            if "timestamp" in metadata:
                content.append(f"Transcribed: {metadata['timestamp']}")

            # Add source if available
            if "source" in metadata:
                content.append(f"Source: {metadata['source']}")

            # Add processing time if available
            if "processing_time" in metadata:
                content.append(f"Processing time: {metadata['processing_time']:.2f}s")

            if content:
                content.append("")  # Empty line separator

            content.append(text.strip())
            return "\n".join(content)

        else:
            # Default to plain text
            return text.strip()

    def is_available(self) -> bool:
        """Check if clipboard is available."""
        if not self._clipboard_manager:
            return False

        return self._clipboard_manager.is_available()

    @property
    def name(self) -> str:
        """Get the name of this output destination."""
        return "clipboard"
