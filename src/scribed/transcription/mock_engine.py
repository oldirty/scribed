"""Mock transcription engine for testing purposes."""

import asyncio
import time
from pathlib import Path
from typing import List, Union

from .base import (
    TranscriptionEngine,
    TranscriptionResult,
    TranscriptionSegment,
    TranscriptionStatus,
)


class MockTranscriptionEngine(TranscriptionEngine):
    """Mock transcription engine that returns predictable results for testing."""

    def __init__(self, config: dict) -> None:
        """Initialize the mock engine."""
        super().__init__(config)
        self.mock_text = config.get(
            "mock_text", "Hello world, this is a test transcription."
        )
        self.mock_delay = config.get("mock_delay", 0.1)  # seconds

    async def transcribe_file(
        self, audio_file_path: Union[str, Path]
    ) -> TranscriptionResult:
        """Mock transcription of an audio file."""
        if not self.validate_audio_file(audio_file_path):
            return TranscriptionResult(
                text="",
                segments=[],
                status=TranscriptionStatus.FAILED,
                error="Invalid audio file",
            )

        # Simulate processing time
        await asyncio.sleep(self.mock_delay)

        # Create mock segments
        segments = [
            TranscriptionSegment(
                text=self.mock_text,
                start_time=0.0,
                end_time=2.0,
                confidence=0.95,
            )
        ]

        return TranscriptionResult(
            text=self.mock_text,
            segments=segments,
            status=TranscriptionStatus.COMPLETED,
            processing_time=self.mock_delay,
        )

    async def transcribe_stream(self, audio_data: bytes) -> TranscriptionResult:
        """Mock streaming transcription."""
        await asyncio.sleep(self.mock_delay)

        return TranscriptionResult(
            text=self.mock_text,
            segments=[],
            status=TranscriptionStatus.COMPLETED,
            processing_time=self.mock_delay,
        )

    def get_supported_formats(self) -> List[str]:
        """Get supported audio formats."""
        return [
            ".wav",
            ".mp3",
            ".mp4",
            ".mpeg",
            ".mpga",
            ".m4a",
            ".webm",
            ".flac",
            ".ogg",
        ]

    def is_available(self) -> bool:
        """Mock engine is always available."""
        return True

    def get_model_info(self) -> dict:
        """Get mock model information."""
        return {
            "engine": "mock",
            "model": "test",
            "language": "en",
            "available": True,
        }
