"""File output destination for saving transcriptions to files."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

from .base import OutputDestination, OutputResult, OutputStatus, OutputError

logger = logging.getLogger(__name__)


class FileOutput(OutputDestination):
    """Output destination that saves transcriptions to files."""

    def _validate_config(self) -> None:
        """Validate file output configuration."""
        # Set defaults
        self.config.setdefault("output_directory", "./transcripts")
        self.config.setdefault("format", "txt")
        self.config.setdefault("filename_template", "{timestamp}_{source}")
        self.config.setdefault("include_metadata", True)
        self.config.setdefault("create_directories", True)

        # Validate format
        supported_formats = ["txt", "json"]
        if self.config["format"] not in supported_formats:
            raise OutputError(
                f"Unsupported format: {self.config['format']}. Supported: {supported_formats}"
            )

        # Ensure output directory exists if create_directories is True
        if self.config["create_directories"]:
            try:
                output_dir = Path(self.config["output_directory"])
                output_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                raise OutputError(f"Failed to create output directory: {e}")

    async def write(
        self, text: str, metadata: Optional[Dict[str, Any]] = None
    ) -> OutputResult:
        """Write transcription to file.

        Args:
            text: The transcription text
            metadata: Optional metadata about the transcription

        Returns:
            OutputResult indicating success or failure
        """
        try:
            # Generate filename
            filename = self._generate_filename(metadata)
            output_path = Path(self.config["output_directory"]) / filename

            # Prepare content based on format
            if self.config["format"] == "json":
                content = self._format_as_json(text, metadata)
            else:
                content = self._format_as_text(text, metadata)

            # Write to file
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(content)

            return OutputResult(
                status=OutputStatus.SUCCESS,
                message=f"Saved to {output_path}",
                destination=self.name,
                metadata={"file_path": str(output_path), "file_size": len(content)},
            )

        except Exception as e:
            error_msg = f"Failed to write file: {e}"
            logger.error(error_msg)
            return OutputResult(
                status=OutputStatus.FAILED,
                message="File write failed",
                destination=self.name,
                error=error_msg,
            )

    def _generate_filename(self, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Generate filename based on template and metadata.

        Args:
            metadata: Optional metadata for filename generation

        Returns:
            Generated filename
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        source = "unknown"

        if metadata:
            source = metadata.get("source", "unknown")
            if "timestamp" in metadata:
                # Use provided timestamp if available
                if isinstance(metadata["timestamp"], datetime):
                    timestamp = metadata["timestamp"].strftime("%Y%m%d_%H%M%S")
                elif isinstance(metadata["timestamp"], str):
                    timestamp = metadata["timestamp"]

        # Apply template
        filename = self.config["filename_template"].format(
            timestamp=timestamp, source=source
        )

        # Add extension
        extension = ".json" if self.config["format"] == "json" else ".txt"
        if not filename.endswith(extension):
            filename += extension

        return filename

    def _format_as_text(
        self, text: str, metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Format transcription as plain text.

        Args:
            text: The transcription text
            metadata: Optional metadata

        Returns:
            Formatted text content
        """
        content = []

        # Add metadata header if enabled
        if self.config["include_metadata"] and metadata:
            content.append(f"# Transcription - {datetime.now().isoformat()}")
            content.append("")

            for key, value in metadata.items():
                if key not in ["segments"]:  # Skip complex objects
                    content.append(f"# {key.title()}: {value}")

            content.append("")
            content.append("---")
            content.append("")

        # Add main transcription text
        content.append(text)

        # Add segments if available
        if metadata and "segments" in metadata and metadata["segments"]:
            content.append("")
            content.append("## Segments")
            content.append("")

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
                content.append(f"{i}. [{start} - {end}] {segment_text}")

        return "\n".join(content)

    def _format_as_json(
        self, text: str, metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Format transcription as JSON.

        Args:
            text: The transcription text
            metadata: Optional metadata

        Returns:
            JSON formatted content
        """
        data = {"text": text, "timestamp": datetime.now().isoformat(), "format": "json"}

        if metadata:
            data["metadata"] = metadata

        return json.dumps(data, indent=2, ensure_ascii=False)

    def is_available(self) -> bool:
        """Check if file output is available."""
        try:
            output_dir = Path(self.config["output_directory"])

            # Check if directory exists or can be created
            if not output_dir.exists():
                if self.config["create_directories"]:
                    output_dir.mkdir(parents=True, exist_ok=True)
                else:
                    return False

            # Check if directory is writable
            test_file = output_dir / ".scribed_write_test"
            try:
                test_file.write_text("test")
                test_file.unlink()
                return True
            except Exception:
                return False

        except Exception as e:
            logger.error(f"File output availability check failed: {e}")
            return False

    @property
    def name(self) -> str:
        """Get the name of this output destination."""
        return "file"
