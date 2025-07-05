"""Base classes for transcription engines."""

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Union
from enum import Enum


class TranscriptionStatus(Enum):
    """Status of a transcription job."""
    
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class TranscriptionSegment:
    """A segment of transcribed text with timing information."""
    
    text: str
    start_time: float
    end_time: float
    confidence: Optional[float] = None


@dataclass
class TranscriptionResult:
    """Result of a transcription operation."""
    
    text: str
    segments: List[TranscriptionSegment]
    language: Optional[str] = None
    confidence: Optional[float] = None
    processing_time: Optional[float] = None
    status: TranscriptionStatus = TranscriptionStatus.COMPLETED
    error: Optional[str] = None


class TranscriptionEngine(ABC):
    """Abstract base class for transcription engines."""
    
    def __init__(self, config: dict) -> None:
        """Initialize the transcription engine.
        
        Args:
            config: Configuration dictionary for the engine
        """
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    @abstractmethod
    async def transcribe_file(self, audio_file_path: Union[str, Path]) -> TranscriptionResult:
        """Transcribe an audio file.
        
        Args:
            audio_file_path: Path to the audio file
            
        Returns:
            TranscriptionResult with the transcribed text and metadata
        """
        pass
    
    @abstractmethod
    async def transcribe_stream(self, audio_data: bytes) -> TranscriptionResult:
        """Transcribe streaming audio data.
        
        Args:
            audio_data: Raw audio data bytes
            
        Returns:
            TranscriptionResult with the transcribed text and metadata
        """
        pass
    
    @abstractmethod
    def get_supported_formats(self) -> List[str]:
        """Get list of supported audio formats.
        
        Returns:
            List of supported file extensions (e.g., ['.wav', '.mp3', '.flac'])
        """
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if the transcription engine is available and properly configured.
        
        Returns:
            True if the engine is ready to use, False otherwise
        """
        pass

    @abstractmethod
    def get_model_info(self) -> dict:
        """Get information about the current model and engine.
        
        Returns:
            Dictionary with model information including engine type, model name,
            language, device, availability status, etc.
        """
        pass
    
    def validate_audio_file(self, audio_file_path: Union[str, Path]) -> bool:
        """Validate that an audio file is supported.
        
        Args:
            audio_file_path: Path to the audio file
            
        Returns:
            True if the file is supported, False otherwise
        """
        path = Path(audio_file_path)
        if not path.exists():
            self.logger.error(f"Audio file does not exist: {path}")
            return False
        
        if path.suffix.lower() not in self.get_supported_formats():
            self.logger.error(f"Unsupported audio format: {path.suffix}")
            return False
        
        return True
    
    async def run_sync_in_thread(self, func, *args, **kwargs):
        """Run a synchronous function in a thread pool.
        
        This is useful for running blocking operations without blocking the event loop.
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, func, *args, **kwargs)
