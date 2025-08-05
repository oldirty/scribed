"""Base classes and data structures for audio input sources."""

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import AsyncGenerator, Dict, List, Optional, Union, Any
import struct
import time

try:
    import numpy as np

    NUMPY_AVAILABLE = True
except ImportError:
    np = None
    NUMPY_AVAILABLE = False


class AudioFormat(Enum):
    """Supported audio formats."""

    INT16 = "int16"
    INT32 = "int32"
    FLOAT32 = "float32"


class AudioError(Exception):
    """Base exception for audio-related errors."""

    pass


class AudioValidationError(AudioError):
    """Exception raised when audio validation fails."""

    pass


class AudioDeviceError(AudioError):
    """Exception raised when audio device operations fail."""

    pass


@dataclass
class AudioChunk:
    """A chunk of audio data with metadata."""

    data: bytes
    sample_rate: int
    channels: int
    format: AudioFormat
    timestamp: float
    chunk_size: int

    def __post_init__(self):
        """Validate audio chunk data."""
        if not self.data:
            raise AudioValidationError("Audio chunk data cannot be empty")
        if self.sample_rate <= 0:
            raise AudioValidationError("Sample rate must be positive")
        if self.channels <= 0:
            raise AudioValidationError("Channel count must be positive")
        if self.chunk_size <= 0:
            raise AudioValidationError("Chunk size must be positive")

    @property
    def duration_seconds(self) -> float:
        """Calculate duration of this audio chunk in seconds."""
        bytes_per_sample = self._get_bytes_per_sample()
        total_samples = len(self.data) // (bytes_per_sample * self.channels)
        return total_samples / self.sample_rate

    def _get_bytes_per_sample(self) -> int:
        """Get bytes per sample for the current format."""
        if self.format == AudioFormat.INT16:
            return 2
        elif self.format == AudioFormat.INT32:
            return 4
        elif self.format == AudioFormat.FLOAT32:
            return 4
        else:
            raise AudioValidationError(f"Unsupported audio format: {self.format}")

    def to_numpy(self) -> Optional[Any]:
        """Convert audio data to numpy array if numpy is available."""
        if not NUMPY_AVAILABLE:
            return None

        if self.format == AudioFormat.INT16:
            return np.frombuffer(self.data, dtype=np.int16)
        elif self.format == AudioFormat.INT32:
            return np.frombuffer(self.data, dtype=np.int32)
        elif self.format == AudioFormat.FLOAT32:
            return np.frombuffer(self.data, dtype=np.float32)
        else:
            raise AudioValidationError(f"Cannot convert format {self.format} to numpy")


@dataclass
class AudioData:
    """Container for larger audio data with multiple chunks."""

    chunks: List[AudioChunk]
    total_duration: float
    metadata: Dict[str, Any]

    def __post_init__(self):
        """Validate audio data."""
        if not self.chunks:
            raise AudioValidationError("AudioData must contain at least one chunk")

        # Validate all chunks have consistent format
        first_chunk = self.chunks[0]
        for chunk in self.chunks[1:]:
            if (
                chunk.sample_rate != first_chunk.sample_rate
                or chunk.channels != first_chunk.channels
                or chunk.format != first_chunk.format
            ):
                raise AudioValidationError(
                    "All chunks must have consistent audio format"
                )

    @property
    def sample_rate(self) -> int:
        """Get sample rate from first chunk."""
        return self.chunks[0].sample_rate

    @property
    def channels(self) -> int:
        """Get channel count from first chunk."""
        return self.chunks[0].channels

    @property
    def format(self) -> AudioFormat:
        """Get audio format from first chunk."""
        return self.chunks[0].format

    def get_combined_data(self) -> bytes:
        """Combine all chunk data into a single bytes object."""
        return b"".join(chunk.data for chunk in self.chunks)

    def get_info(self) -> Dict[str, Any]:
        """Get information about this audio data."""
        return {
            "chunk_count": len(self.chunks),
            "total_duration": self.total_duration,
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "format": self.format.value,
            "total_bytes": len(self.get_combined_data()),
            "metadata": self.metadata,
        }


class AudioFormatConverter:
    """Utility class for audio format conversion and validation."""

    @staticmethod
    def validate_format(sample_rate: int, channels: int, format: AudioFormat) -> bool:
        """Validate audio format parameters.

        Args:
            sample_rate: Sample rate in Hz
            channels: Number of audio channels
            format: Audio format

        Returns:
            True if format is valid

        Raises:
            AudioValidationError: If format is invalid
        """
        if sample_rate <= 0:
            raise AudioValidationError(f"Invalid sample rate: {sample_rate}")

        if channels <= 0:
            raise AudioValidationError(f"Invalid channel count: {channels}")

        if sample_rate > 192000:
            raise AudioValidationError(f"Sample rate too high: {sample_rate}")

        if channels > 8:
            raise AudioValidationError(f"Too many channels: {channels}")

        # Common sample rates
        common_rates = [8000, 16000, 22050, 44100, 48000, 96000, 192000]
        if sample_rate not in common_rates:
            logging.getLogger(__name__).warning(
                f"Uncommon sample rate: {sample_rate}. Common rates: {common_rates}"
            )

        return True

    @staticmethod
    def convert_chunk_format(
        chunk: AudioChunk, target_format: AudioFormat
    ) -> AudioChunk:
        """Convert audio chunk to different format.

        Args:
            chunk: Source audio chunk
            target_format: Target audio format

        Returns:
            New AudioChunk with converted format

        Raises:
            AudioValidationError: If conversion is not supported
        """
        if not NUMPY_AVAILABLE:
            raise AudioValidationError("Numpy required for format conversion")

        if chunk.format == target_format:
            return chunk

        # Convert to numpy array
        source_array = chunk.to_numpy()
        if source_array is None:
            raise AudioValidationError("Failed to convert chunk to numpy array")

        # Normalize to float32 first
        if chunk.format == AudioFormat.INT16:
            normalized = source_array.astype(np.float32) / 32767.0
        elif chunk.format == AudioFormat.INT32:
            normalized = source_array.astype(np.float32) / 2147483647.0
        elif chunk.format == AudioFormat.FLOAT32:
            normalized = source_array.astype(np.float32)
        else:
            raise AudioValidationError(f"Unsupported source format: {chunk.format}")

        # Convert to target format
        if target_format == AudioFormat.INT16:
            target_array = (np.clip(normalized, -1.0, 1.0) * 32767).astype(np.int16)
        elif target_format == AudioFormat.INT32:
            target_array = (np.clip(normalized, -1.0, 1.0) * 2147483647).astype(
                np.int32
            )
        elif target_format == AudioFormat.FLOAT32:
            target_array = np.clip(normalized, -1.0, 1.0).astype(np.float32)
        else:
            raise AudioValidationError(f"Unsupported target format: {target_format}")

        return AudioChunk(
            data=target_array.tobytes(),
            sample_rate=chunk.sample_rate,
            channels=chunk.channels,
            format=target_format,
            timestamp=chunk.timestamp,
            chunk_size=chunk.chunk_size,
        )

    @staticmethod
    def resample_chunk(chunk: AudioChunk, target_sample_rate: int) -> AudioChunk:
        """Resample audio chunk to different sample rate.

        Args:
            chunk: Source audio chunk
            target_sample_rate: Target sample rate in Hz

        Returns:
            New AudioChunk with resampled data

        Note:
            This is a basic implementation. For production use, consider
            using scipy.signal.resample or librosa for better quality.
        """
        if not NUMPY_AVAILABLE:
            raise AudioValidationError("Numpy required for resampling")

        if chunk.sample_rate == target_sample_rate:
            return chunk

        # Simple linear interpolation resampling
        source_array = chunk.to_numpy()
        if source_array is None:
            raise AudioValidationError("Failed to convert chunk to numpy array")

        # Calculate resampling ratio
        ratio = target_sample_rate / chunk.sample_rate
        target_length = int(len(source_array) * ratio)

        # Create new time indices
        source_indices = np.linspace(0, len(source_array) - 1, target_length)

        # Interpolate
        resampled = np.interp(
            source_indices, np.arange(len(source_array)), source_array
        )

        # Convert back to original format
        if chunk.format == AudioFormat.INT16:
            resampled = resampled.astype(np.int16)
        elif chunk.format == AudioFormat.INT32:
            resampled = resampled.astype(np.int32)
        elif chunk.format == AudioFormat.FLOAT32:
            resampled = resampled.astype(np.float32)

        return AudioChunk(
            data=resampled.tobytes(),
            sample_rate=target_sample_rate,
            channels=chunk.channels,
            format=chunk.format,
            timestamp=chunk.timestamp,
            chunk_size=int(chunk.chunk_size * ratio),
        )


class AudioSource(ABC):
    """Abstract base class for audio input sources."""

    def __init__(self, config: Dict[str, Any]) -> None:
        """Initialize audio source.

        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self._is_active = False
        self._start_time: Optional[float] = None

    @abstractmethod
    async def start(self) -> None:
        """Start the audio source.

        Raises:
            AudioError: If starting fails
        """
        pass

    @abstractmethod
    async def stop(self) -> None:
        """Stop the audio source.

        Raises:
            AudioError: If stopping fails
        """
        pass

    @abstractmethod
    async def read_chunk(self) -> Optional[AudioChunk]:
        """Read the next audio chunk.

        Returns:
            AudioChunk if available, None if no more data

        Raises:
            AudioError: If reading fails
        """
        pass

    @abstractmethod
    def get_audio_info(self) -> Dict[str, Any]:
        """Get information about the audio source.

        Returns:
            Dictionary with audio source information
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the audio source is available.

        Returns:
            True if source is available and ready to use
        """
        pass

    async def read_stream(self) -> AsyncGenerator[AudioChunk, None]:
        """Get async generator for audio stream.

        Yields:
            AudioChunk objects as they become available

        Raises:
            AudioError: If streaming fails
        """
        if not self._is_active:
            await self.start()

        try:
            while self._is_active:
                chunk = await self.read_chunk()
                if chunk is None:
                    break
                yield chunk
        finally:
            if self._is_active:
                await self.stop()

    async def read_duration(self, duration_seconds: float) -> AudioData:
        """Read audio for a specific duration.

        Args:
            duration_seconds: Duration to read in seconds

        Returns:
            AudioData containing all chunks for the duration

        Raises:
            AudioError: If reading fails
        """
        chunks = []
        start_time = time.time()

        if not self._is_active:
            await self.start()

        try:
            while time.time() - start_time < duration_seconds:
                chunk = await self.read_chunk()
                if chunk is None:
                    break
                chunks.append(chunk)

            if not chunks:
                raise AudioError("No audio data read")

            actual_duration = time.time() - start_time
            metadata = {
                "requested_duration": duration_seconds,
                "actual_duration": actual_duration,
                "source_type": self.__class__.__name__,
            }

            return AudioData(
                chunks=chunks, total_duration=actual_duration, metadata=metadata
            )

        finally:
            if self._is_active:
                await self.stop()

    def _mark_active(self) -> None:
        """Mark source as active."""
        self._is_active = True
        self._start_time = time.time()
        self.logger.info(f"Audio source {self.__class__.__name__} started")

    def _mark_inactive(self) -> None:
        """Mark source as inactive."""
        self._is_active = False
        if self._start_time:
            duration = time.time() - self._start_time
            self.logger.info(
                f"Audio source {self.__class__.__name__} stopped after {duration:.2f}s"
            )
        self._start_time = None

    @property
    def is_active(self) -> bool:
        """Check if source is currently active."""
        return self._is_active

    @property
    def uptime_seconds(self) -> Optional[float]:
        """Get uptime in seconds if active."""
        if self._is_active and self._start_time:
            return time.time() - self._start_time
        return None

    def get_base_info(self) -> Dict[str, Any]:
        """Get base information common to all audio sources."""
        return {
            "source_type": self.__class__.__name__,
            "is_active": self._is_active,
            "is_available": self.is_available(),
            "uptime_seconds": self.uptime_seconds,
            "config": self.config,
        }

    async def __aenter__(self):
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.stop()
