"""Integration utilities for connecting output system with existing config."""

from typing import Dict, Any
from ..config import Config, OutputConfig as ConfigOutputConfig
from .handler import OutputHandler, OutputConfig


def create_output_handler_from_config(config: Config) -> OutputHandler:
    """Create OutputHandler from existing Scribed configuration.

    Args:
        config: Scribed configuration object

    Returns:
        Configured OutputHandler instance
    """
    # Convert existing config to output config
    output_config = OutputConfig(
        format=config.output.format,
        save_to_file=config.output.save_to_file,
        copy_to_clipboard=config.output.copy_to_clipboard,
        console_output=False,  # Not enabled by default in existing config
        file_config={
            "output_directory": config.audio.output_directory,
            "format": config.output.format,
            "filename_template": "transcription_{timestamp}",
            "include_metadata": True,
        },
        clipboard_config={
            "format": "plain",
            "include_metadata": False,
        },
        console_config={
            "format": "formatted",
            "include_metadata": True,
        },
    )

    return OutputHandler(output_config)


def create_metadata_from_transcription_result(
    result, source: str = "unknown"
) -> Dict[str, Any]:
    """Create metadata dictionary from transcription result.

    Args:
        result: Transcription result object
        source: Source of the transcription

    Returns:
        Metadata dictionary for output handling
    """
    metadata = {
        "source": source,
        "timestamp": result.timestamp if hasattr(result, "timestamp") else None,
        "processing_time": (
            result.processing_time if hasattr(result, "processing_time") else None
        ),
        "confidence": result.confidence if hasattr(result, "confidence") else None,
    }

    # Add segments if available
    if hasattr(result, "segments") and result.segments:
        metadata["segments"] = [
            {
                "text": segment.text,
                "start_time": segment.start_time,
                "end_time": segment.end_time,
                "confidence": (
                    segment.confidence if hasattr(segment, "confidence") else None
                ),
            }
            for segment in result.segments
        ]

    # Remove None values
    return {k: v for k, v in metadata.items() if v is not None}
