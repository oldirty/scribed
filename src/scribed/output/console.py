"""Console output destination for displaying transcriptions to console."""

import logging
import os
import sys
from datetime import datetime
from typing import Dict, Any, Optional

from .base import OutputDestination, OutputResult, OutputStatus, OutputError

logger = logging.getLogger(__name__)


class ConsoleOutput(OutputDestination):
    """Output destination that displays transcriptions to console."""

    def _validate_config(self) -> None:
        """Validate console output configuration."""
        # Set defaults
        self.config.setdefault("include_metadata", True)
        self.config.setdefault("format", "formatted")  # plain or formatted
        self.config.setdefault("stream", "stdout")  # stdout or stderr
        self.config.setdefault("prefix", "[TRANSCRIPTION]")
        self.config.setdefault("timestamp", True)
        self.config.setdefault("colors", True)  # Enable colored output if supported

        # Validate stream
        if self.config["stream"] not in ["stdout", "stderr"]:
            raise OutputError(
                f"Invalid stream: {self.config['stream']}. Must be 'stdout' or 'stderr'"
            )

    async def write(
        self, text: str, metadata: Optional[Dict[str, Any]] = None
    ) -> OutputResult:
        """Write transcription to console.

        Args:
            text: The transcription text
            metadata: Optional metadata about the transcription

        Returns:
            OutputResult indicating success or failure
        """
        try:
            # Get output stream
            stream = sys.stdout if self.config["stream"] == "stdout" else sys.stderr

            # Format content for console
            content = self._format_content(text, metadata)

            # Write to console
            print(content, file=stream)
            stream.flush()

            return OutputResult(
                status=OutputStatus.SUCCESS,
                message=f"Displayed to {self.config['stream']}",
                destination=self.name,
                metadata={
                    "stream": self.config["stream"],
                    "content_length": len(content),
                },
            )

        except Exception as e:
            error_msg = f"Console write error: {e}"
            logger.error(error_msg)
            return OutputResult(
                status=OutputStatus.FAILED,
                message="Console write failed",
                destination=self.name,
                error=error_msg,
            )

    def _format_content(
        self, text: str, metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Format content for console display.

        Args:
            text: The transcription text
            metadata: Optional metadata

        Returns:
            Formatted content for console
        """
        if self.config["format"] == "plain":
            return text.strip()

        # Formatted output
        content = []

        # Add prefix and timestamp
        prefix_parts = []
        if self.config["prefix"]:
            prefix_parts.append(self.config["prefix"])

        if self.config["timestamp"]:
            timestamp = datetime.now().strftime("%H:%M:%S")
            prefix_parts.append(timestamp)

        if prefix_parts:
            prefix = " ".join(prefix_parts)
            if self.config["colors"] and self._supports_colors():
                # Add color codes for better visibility
                prefix = f"\\033[36m{prefix}\\033[0m"  # Cyan color
            content.append(f"{prefix}")

        # Add metadata if enabled
        if self.config["include_metadata"] and metadata:
            metadata_parts = []

            if "source" in metadata:
                metadata_parts.append(f"Source: {metadata['source']}")

            if "processing_time" in metadata:
                metadata_parts.append(f"Time: {metadata['processing_time']:.2f}s")

            if "confidence" in metadata:
                metadata_parts.append(f"Confidence: {metadata['confidence']:.2f}")

            if metadata_parts:
                metadata_line = " | ".join(metadata_parts)
                if self.config["colors"] and self._supports_colors():
                    metadata_line = f"\\033[90m{metadata_line}\\033[0m"  # Gray color
                content.append(metadata_line)

        # Add separator line if we have metadata
        if len(content) > 0:
            if self.config["colors"] and self._supports_colors():
                content.append("\\033[90m" + "-" * 50 + "\\033[0m")
            else:
                content.append("-" * 50)

        # Add main transcription text
        transcription_text = text.strip()
        if self.config["colors"] and self._supports_colors():
            transcription_text = (
                f"\\033[97m{transcription_text}\\033[0m"  # Bright white
            )
        content.append(transcription_text)

        # Add segments if available
        if metadata and "segments" in metadata and metadata["segments"]:
            content.append("")
            segments_header = "Segments:"
            if self.config["colors"] and self._supports_colors():
                segments_header = f"\\033[93m{segments_header}\\033[0m"  # Yellow
            content.append(segments_header)

            for i, segment in enumerate(metadata["segments"], 1):
                start = (
                    f"{segment.get('start_time', 'N/A'):.2f}s"
                    if isinstance(segment.get("start_time"), (int, float))
                    else "N/A"
                )
                end = (
                    f"{segment.get('end_time', 'N/A'):.2f}s"
                    if isinstance(segment.get("end_time"), (int, float))
                    else "N/A"
                )
                segment_text = segment.get("text", "")

                segment_line = f"  {i}. [{start} - {end}] {segment_text}"
                if self.config["colors"] and self._supports_colors():
                    segment_line = f"\\033[94m{segment_line}\\033[0m"  # Blue
                content.append(segment_line)

        return "\n".join(content)

    def _supports_colors(self) -> bool:
        """Check if the terminal supports color output.

        Returns:
            True if colors are supported
        """
        # Simple check for color support
        return (
            hasattr(sys.stdout, "isatty")
            and sys.stdout.isatty()
            and "TERM" in os.environ
            and os.environ["TERM"] != "dumb"
        )

    def is_available(self) -> bool:
        """Check if console output is available."""
        try:
            # Check if stdout/stderr are available
            stream = sys.stdout if self.config["stream"] == "stdout" else sys.stderr
            return stream is not None and hasattr(stream, "write")
        except Exception:
            return False

    @property
    def name(self) -> str:
        """Get the name of this output destination."""
        return "console"
