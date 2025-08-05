"""Output handling system for Scribed transcriptions."""

from .handler import OutputHandler, OutputConfig
from .base import OutputDestination, OutputResult, OutputError, OutputStatus
from .file import FileOutput
from .clipboard import ClipboardOutput
from .console import ConsoleOutput
from .integration import (
    create_output_handler_from_config,
    create_metadata_from_transcription_result,
)

__all__ = [
    "OutputHandler",
    "OutputConfig",
    "OutputDestination",
    "OutputResult",
    "OutputError",
    "OutputStatus",
    "FileOutput",
    "ClipboardOutput",
    "ConsoleOutput",
    "create_output_handler_from_config",
    "create_metadata_from_transcription_result",
]
