"""File-based audio source implementations."""

import asyncio
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union

from .base import (
    AudioSource,
    AudioChunk,
    AudioFormat,
    AudioError,
    AudioValidationError,
    AudioFormatConverter,
)

try:
    import librosa
    import numpy as np

    LIBROSA_AVAILABLE = True
except ImportError:
    librosa = None
    np = None
    LIBROSA_AVAILABLE = False

try:
    import soundfile as sf

    SOUNDFILE_AVAILABLE = True
except ImportError:
    sf = None
    SOUNDFILE_AVAILABLE = False

# Fallback to wave for basic WAV support
try:
    import wave

    WAVE_AVAILABLE = True
except ImportError:
    wave = None
    WAVE_AVAILABLE = False


class FileSource(AudioSource):
    """Audio source that reads from a single audio file."""

    SUPPORTED_FORMATS = [".wav", ".mp3", ".flac", ".m4a", ".ogg", ".aac"]

    def __init__(self, config: Dict[str, Any]) -> None:
        """Initialize file source.

        Args:
            config: Configuration dictionary with keys:
                - file_path: Path to the audio file
                - chunk_size: Size of chunks to read (default: 1024)
                - target_sample_rate: Target sample rate (default: 16000)
                - target_channels: Target number of channels (default: 1)
                - target_format: Target audio format (default: "int16")
        """
        super().__init__(config)

        # File configuration
        file_path = config.get("file_path")
        if not file_path:
            raise AudioValidationError("file_path is required in config")

        self.file_path = Path(file_path)
        if not self.file_path.exists():
            raise AudioError(f"Audio file does not exist: {self.file_path}")

        if self.file_path.suffix.lower() not in self.SUPPORTED_FORMATS:
            raise AudioValidationError(
                f"Unsupported file format: {self.file_path.suffix}"
            )

        # Audio configuration
        self.chunk_size = config.get("chunk_size", 1024)
        self.target_sample_rate = config.get("target_sample_rate", 16000)
        self.target_channels = config.get("target_channels", 1)

        # Parse target format
        format_str = config.get("target_format", "int16").lower()
        if format_str == "int16":
            self.target_format = AudioFormat.INT16
        elif format_str == "int32":
            self.target_format = AudioFormat.INT32
        elif format_str == "float32":
            self.target_format = AudioFormat.FLOAT32
        else:
            raise AudioValidationError(f"Unsupported target format: {format_str}")

        # Validate target format
        AudioFormatConverter.validate_format(
            self.target_sample_rate, self.target_channels, self.target_format
        )

        # Audio data
        self.audio_data: Optional[np.ndarray] = None
        self.original_sample_rate: Optional[int] = None
        self.original_channels: Optional[int] = None
        self.current_position = 0
        self.total_samples = 0

        self.logger.info(f"File source configured for: {self.file_path}")

    async def start(self) -> None:
        """Start the file source by loading the audio file."""
        if self._is_active:
            self.logger.warning("File source already active")
            return

        try:
            await self._load_audio_file()
            self.current_position = 0
            self._mark_active()

        except Exception as e:
            raise AudioError(f"Failed to start file source: {e}")

    async def stop(self) -> None:
        """Stop the file source."""
        if not self._is_active:
            return

        self._mark_inactive()
        self.audio_data = None
        self.current_position = 0

    async def read_chunk(self) -> Optional[AudioChunk]:
        """Read the next audio chunk from the file.

        Returns:
            AudioChunk if available, None if end of file reached
        """
        if not self._is_active or self.audio_data is None:
            return None

        # Check if we've reached the end
        if self.current_position >= self.total_samples:
            return None

        # Calculate chunk end position
        chunk_end = min(self.current_position + self.chunk_size, self.total_samples)

        # Extract chunk data
        if self.target_channels == 1:
            chunk_data = self.audio_data[self.current_position : chunk_end]
        else:
            chunk_data = self.audio_data[self.current_position : chunk_end, :]

        # Convert to target format
        if self.target_format == AudioFormat.INT16:
            chunk_data = (np.clip(chunk_data, -1.0, 1.0) * 32767).astype(np.int16)
        elif self.target_format == AudioFormat.INT32:
            chunk_data = (np.clip(chunk_data, -1.0, 1.0) * 2147483647).astype(np.int32)
        elif self.target_format == AudioFormat.FLOAT32:
            chunk_data = np.clip(chunk_data, -1.0, 1.0).astype(np.float32)

        # Create audio chunk
        chunk = AudioChunk(
            data=chunk_data.tobytes(),
            sample_rate=self.target_sample_rate,
            channels=self.target_channels,
            format=self.target_format,
            timestamp=time.time(),
            chunk_size=len(chunk_data),
        )

        # Update position
        self.current_position = chunk_end

        return chunk

    def get_audio_info(self) -> Dict[str, Any]:
        """Get information about the file source."""
        info = self.get_base_info()
        info.update(
            {
                "file_path": str(self.file_path),
                "file_size_bytes": (
                    self.file_path.stat().st_size if self.file_path.exists() else 0
                ),
                "target_sample_rate": self.target_sample_rate,
                "target_channels": self.target_channels,
                "target_format": self.target_format.value,
                "chunk_size": self.chunk_size,
                "original_sample_rate": self.original_sample_rate,
                "original_channels": self.original_channels,
                "total_samples": self.total_samples,
                "current_position": self.current_position,
                "progress_percent": (
                    (self.current_position / self.total_samples * 100)
                    if self.total_samples > 0
                    else 0
                ),
                "duration_seconds": (
                    self.total_samples / self.target_sample_rate
                    if self.target_sample_rate > 0
                    else 0
                ),
                "librosa_available": LIBROSA_AVAILABLE,
                "soundfile_available": SOUNDFILE_AVAILABLE,
                "wave_available": WAVE_AVAILABLE,
            }
        )
        return info

    def is_available(self) -> bool:
        """Check if file source is available."""
        return LIBROSA_AVAILABLE or SOUNDFILE_AVAILABLE or WAVE_AVAILABLE

    async def _load_audio_file(self) -> None:
        """Load the audio file into memory."""
        if not self.is_available():
            raise AudioError(
                "No audio libraries available. Install with: "
                "pip install librosa soundfile"
            )

        try:
            # Try librosa first (best format support)
            if LIBROSA_AVAILABLE:
                self.audio_data, self.original_sample_rate = (
                    await self._load_with_librosa()
                )

            # Fallback to soundfile
            elif SOUNDFILE_AVAILABLE:
                self.audio_data, self.original_sample_rate = (
                    await self._load_with_soundfile()
                )

            # Fallback to wave (WAV only)
            elif WAVE_AVAILABLE and self.file_path.suffix.lower() == ".wav":
                self.audio_data, self.original_sample_rate = (
                    await self._load_with_wave()
                )

            else:
                raise AudioError(
                    f"Cannot load {self.file_path.suffix} files with available libraries"
                )

            # Determine original channels
            if self.audio_data.ndim == 1:
                self.original_channels = 1
            else:
                self.original_channels = self.audio_data.shape[1]

            # Convert to target format
            await self._convert_audio_format()

            # Update total samples
            if self.target_channels == 1:
                self.total_samples = len(self.audio_data)
            else:
                self.total_samples = self.audio_data.shape[0]

            self.logger.info(
                f"Loaded audio file: {self.original_sample_rate}Hz -> {self.target_sample_rate}Hz, "
                f"{self.original_channels}ch -> {self.target_channels}ch, "
                f"{self.total_samples} samples ({self.total_samples / self.target_sample_rate:.2f}s)"
            )

        except Exception as e:
            raise AudioError(f"Failed to load audio file {self.file_path}: {e}")

    async def _load_with_librosa(self) -> tuple:
        """Load audio file using librosa."""

        def load_sync():
            return librosa.load(
                str(self.file_path),
                sr=self.target_sample_rate,
                mono=(self.target_channels == 1),
            )

        # Run in thread to avoid blocking
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, load_sync)

    async def _load_with_soundfile(self) -> tuple:
        """Load audio file using soundfile."""

        def load_sync():
            data, sample_rate = sf.read(str(self.file_path))

            # Convert to mono if needed
            if self.target_channels == 1 and data.ndim > 1:
                data = np.mean(data, axis=1)

            # Resample if needed (basic implementation)
            if sample_rate != self.target_sample_rate:
                # Simple resampling - for production use librosa.resample
                ratio = self.target_sample_rate / sample_rate
                new_length = int(len(data) * ratio)
                indices = np.linspace(0, len(data) - 1, new_length)
                data = np.interp(indices, np.arange(len(data)), data)

            return data, self.target_sample_rate

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, load_sync)

    async def _load_with_wave(self) -> tuple:
        """Load WAV file using wave module."""

        def load_sync():
            with wave.open(str(self.file_path), "rb") as wav_file:
                frames = wav_file.readframes(-1)
                sample_rate = wav_file.getframerate()
                channels = wav_file.getnchannels()
                sample_width = wav_file.getsampwidth()

                # Convert to numpy array
                if sample_width == 1:
                    data = np.frombuffer(frames, dtype=np.uint8)
                    data = (data.astype(np.float32) - 128) / 128.0
                elif sample_width == 2:
                    data = np.frombuffer(frames, dtype=np.int16)
                    data = data.astype(np.float32) / 32767.0
                elif sample_width == 4:
                    data = np.frombuffer(frames, dtype=np.int32)
                    data = data.astype(np.float32) / 2147483647.0
                else:
                    raise AudioError(f"Unsupported sample width: {sample_width}")

                # Handle multi-channel
                if channels > 1:
                    data = data.reshape(-1, channels)
                    if self.target_channels == 1:
                        data = np.mean(data, axis=1)

                # Basic resampling if needed
                if sample_rate != self.target_sample_rate:
                    ratio = self.target_sample_rate / sample_rate
                    new_length = int(len(data) * ratio)
                    indices = np.linspace(0, len(data) - 1, new_length)
                    if data.ndim == 1:
                        data = np.interp(indices, np.arange(len(data)), data)
                    else:
                        data = np.array(
                            [
                                np.interp(indices, np.arange(len(data)), data[:, ch])
                                for ch in range(data.shape[1])
                            ]
                        ).T

                return data, self.target_sample_rate

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, load_sync)

    async def _convert_audio_format(self) -> None:
        """Convert audio to target format."""
        if self.audio_data is None:
            return

        # Ensure data is in float32 format for processing
        if self.audio_data.dtype != np.float32:
            self.audio_data = self.audio_data.astype(np.float32)

        # Handle channel conversion
        if self.original_channels != self.target_channels:
            if self.original_channels == 1 and self.target_channels > 1:
                # Mono to multi-channel (duplicate)
                self.audio_data = np.tile(
                    self.audio_data.reshape(-1, 1), (1, self.target_channels)
                )
            elif self.original_channels > 1 and self.target_channels == 1:
                # Multi-channel to mono (average)
                self.audio_data = np.mean(self.audio_data, axis=1)

        # Normalize to [-1, 1] range
        self.audio_data = np.clip(self.audio_data, -1.0, 1.0)

    def seek_to_position(self, position_seconds: float) -> None:
        """Seek to a specific position in the file.

        Args:
            position_seconds: Position in seconds
        """
        if not self._is_active:
            raise AudioError("File source not active")

        sample_position = int(position_seconds * self.target_sample_rate)
        self.current_position = max(0, min(sample_position, self.total_samples))

        self.logger.info(
            f"Seeked to position {position_seconds:.2f}s (sample {self.current_position})"
        )

    def get_remaining_duration(self) -> float:
        """Get remaining duration in seconds."""
        if not self._is_active or self.total_samples == 0:
            return 0.0

        remaining_samples = self.total_samples - self.current_position
        return remaining_samples / self.target_sample_rate

    @classmethod
    def get_supported_formats(cls) -> List[str]:
        """Get list of supported file formats."""
        return cls.SUPPORTED_FORMATS.copy()

    @classmethod
    def is_format_supported(cls, file_path: Union[str, Path]) -> bool:
        """Check if a file format is supported.

        Args:
            file_path: Path to the file

        Returns:
            True if format is supported
        """
        path = Path(file_path)
        return path.suffix.lower() in cls.SUPPORTED_FORMATS
