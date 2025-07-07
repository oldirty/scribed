"""Whisper-based wake word detection engine."""

import asyncio
import logging
import tempfile
import time
import wave
from pathlib import Path
from typing import Callable, Optional, Any, List, Tuple
from collections import deque
import difflib

from ..transcription.service import TranscriptionService


class WhisperWakeWordError(Exception):
    """Exception raised when Whisper wake word detection fails."""

    pass


class WhisperWakeWordEngine:
    """Wake word detection engine using Whisper transcription."""

    def __init__(self, config: dict) -> None:
        """Initialize the Whisper wake word engine.

        Args:
            config: Configuration with keys:
                - keywords: List of wake words to detect
                - chunk_duration: Duration of audio chunks in seconds (default: 1.5)
                - overlap_duration: Overlap between chunks in seconds (default: 0.5)
                - confidence_threshold: Minimum similarity score (0.0-1.0, default: 0.7)
                - sample_rate: Audio sample rate (default: 16000)
                - channels: Audio channels (default: 1)
                - transcription_config: Config for Whisper transcription service
        """
        self.logger = logging.getLogger(__name__)

        # Wake word configuration
        self.keywords = config.get("keywords", ["hey scribed", "scribed"])
        self.chunk_duration = config.get("chunk_duration", 1.5)  # seconds
        self.overlap_duration = config.get("overlap_duration", 0.5)  # seconds
        self.confidence_threshold = config.get("confidence_threshold", 0.7)

        # Audio configuration
        self.sample_rate = config.get("sample_rate", 16000)
        self.channels = config.get("channels", 1)
        self.chunk_size = int(self.sample_rate * self.chunk_duration)
        self.overlap_size = int(self.sample_rate * self.overlap_duration)

        # Initialize transcription service
        transcription_config = config.get(
            "transcription_config",
            {
                "provider": "whisper",
                "model": "tiny",  # Use smallest/fastest model for wake words
                "language": "en",
            },
        )

        try:
            self.transcription_service = TranscriptionService(transcription_config)
            if not self.transcription_service.is_available():
                raise WhisperWakeWordError("Transcription service not available")
            self.logger.info("Whisper wake word engine initialized")
        except Exception as e:
            raise WhisperWakeWordError(
                f"Failed to initialize transcription service: {e}"
            )

        # Audio buffer for rolling window - stores audio chunks
        self._audio_buffer: deque[bytes] = deque(
            maxlen=self.chunk_size + self.overlap_size
        )
        self._current_audio: bytes = b""  # Current accumulated audio data
        self._is_listening = False
        self._listen_task: Optional[asyncio.Task] = None

        # Normalize keywords for better matching
        self._normalized_keywords = [self._normalize_text(kw) for kw in self.keywords]

        self.logger.info(f"Wake words: {self.keywords}")
        self.logger.info(
            f"Chunk duration: {self.chunk_duration}s, overlap: {self.overlap_duration}s"
        )
        self.logger.info(f"Confidence threshold: {self.confidence_threshold}")

    def _normalize_text(self, text: str) -> str:
        """Normalize text for better matching."""
        return text.lower().strip().replace("-", " ").replace("_", " ")

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two text strings."""
        # Use sequence matcher for fuzzy matching
        matcher = difflib.SequenceMatcher(None, text1, text2)
        return matcher.ratio()

    def _check_for_wake_words(
        self, transcribed_text: str
    ) -> Tuple[Optional[int], Optional[str]]:
        """Check if transcribed text contains any wake words.

        Returns:
            Tuple of (keyword_index, keyword_name) if found, (None, None) otherwise
        """
        normalized_text = self._normalize_text(transcribed_text)

        for idx, keyword in enumerate(self._normalized_keywords):
            # Check for exact substring match first
            if keyword in normalized_text:
                return idx, self.keywords[idx]

            # Check for fuzzy match
            similarity = self._calculate_similarity(keyword, normalized_text)
            if similarity >= self.confidence_threshold:
                self.logger.debug(
                    f"Fuzzy match: '{keyword}' in '{normalized_text}' (similarity: {similarity:.3f})"
                )
                return idx, self.keywords[idx]

            # Check if wake word appears as part of the transcribed text
            words = normalized_text.split()
            keyword_words = keyword.split()

            # Sliding window approach for multi-word wake words
            if len(keyword_words) <= len(words):
                for i in range(len(words) - len(keyword_words) + 1):
                    window = " ".join(words[i : i + len(keyword_words)])
                    similarity = self._calculate_similarity(keyword, window)
                    if similarity >= self.confidence_threshold:
                        self.logger.debug(
                            f"Window match: '{keyword}' in '{window}' (similarity: {similarity:.3f})"
                        )
                        return idx, self.keywords[idx]

        return None, None

    def _write_wav_file(self, file_handle, audio_data: bytes) -> None:
        """Write audio data as WAV file."""
        with wave.open(file_handle, "wb") as wav_file:
            wav_file.setnchannels(self.channels)
            wav_file.setsampwidth(2)  # 16-bit audio
            wav_file.setframerate(self.sample_rate)
            wav_file.writeframes(audio_data)

    async def _process_audio_chunk(
        self, audio_data: bytes, callback: Callable[[int, str], Any]
    ) -> None:
        """Process an audio chunk and check for wake words."""
        try:
            # Create temporary WAV file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                self._write_wav_file(temp_file, audio_data)
                temp_path = temp_file.name

            try:
                # Transcribe the audio chunk
                result = await self.transcription_service.transcribe_file(temp_path)

                if result.text and result.text.strip():
                    transcribed_text = result.text.strip()
                    self.logger.debug(f"Transcribed: '{transcribed_text}'")

                    # Check for wake words
                    keyword_index, keyword_name = self._check_for_wake_words(
                        transcribed_text
                    )

                    if keyword_index is not None and keyword_name is not None:
                        self.logger.info(
                            f"Wake word detected: '{keyword_name}' in '{transcribed_text}'"
                        )

                        # Call the callback
                        if asyncio.iscoroutinefunction(callback):
                            await callback(keyword_index, keyword_name)
                        else:
                            callback(keyword_index, keyword_name)

            finally:
                # Clean up temp file
                try:
                    Path(temp_path).unlink()
                except Exception as e:
                    self.logger.warning(f"Failed to delete temp file: {e}")

        except Exception as e:
            self.logger.error(f"Error processing audio chunk: {e}")

    async def _listen_loop(self, callback: Callable[[int, str], Any]) -> None:
        """Main listening loop that processes audio chunks."""
        self.logger.info("Whisper wake word listening started")

        while self._is_listening:
            try:
                # Check if we have enough accumulated audio data
                if (
                    len(self._current_audio)
                    >= self.chunk_duration * self.sample_rate * 2
                ):  # 2 bytes per sample
                    # Extract chunk for processing
                    chunk_size_bytes = int(self.chunk_duration * self.sample_rate * 2)
                    chunk_data = self._current_audio[:chunk_size_bytes]

                    # Keep overlap for next chunk
                    overlap_size_bytes = int(
                        self.overlap_duration * self.sample_rate * 2
                    )
                    self._current_audio = self._current_audio[
                        chunk_size_bytes - overlap_size_bytes :
                    ]

                    # Process the chunk
                    await self._process_audio_chunk(chunk_data, callback)

                else:
                    # Not enough data yet, wait a bit
                    await asyncio.sleep(0.1)

            except Exception as e:
                self.logger.error(f"Error in listen loop: {e}")
                await asyncio.sleep(0.1)

    def queue_audio_data(self, audio_data: bytes) -> None:
        """Queue audio data for processing.

        This should be called from the microphone callback.
        """
        if not self._is_listening:
            return

        # Accumulate audio data for processing
        self._current_audio += audio_data

    async def start_listening(self, callback: Callable[[int, str], Any]) -> None:
        """Start listening for wake words.

        Args:
            callback: Function to call when wake word is detected.
                     Should accept (keyword_index: int, keyword_name: str)
        """
        if self._is_listening:
            self.logger.warning("Already listening for wake words")
            return

        self._is_listening = True
        self._audio_buffer.clear()

        # Start the listening task
        self._listen_task = asyncio.create_task(self._listen_loop(callback))

        self.logger.info("Whisper wake word detection started")

    def stop_listening(self) -> None:
        """Stop listening for wake words."""
        if not self._is_listening:
            return

        self._is_listening = False

        # Cancel the listening task
        if self._listen_task and not self._listen_task.done():
            self._listen_task.cancel()

        self._audio_buffer.clear()
        self.logger.info("Whisper wake word detection stopped")

    def is_available(self) -> bool:
        """Check if the engine is available."""
        return self.transcription_service.is_available()

    def get_info(self) -> dict:
        """Get engine information."""
        return {
            "engine": "whisper",
            "keywords": self.keywords,
            "chunk_duration": self.chunk_duration,
            "overlap_duration": self.overlap_duration,
            "confidence_threshold": self.confidence_threshold,
            "transcription_backend": self.transcription_service.get_engine_info(),
            "available": self.is_available(),
        }


class AsyncWhisperWakeWordEngine:
    """Async wrapper for WhisperWakeWordEngine."""

    def __init__(self, config: dict) -> None:
        """Initialize async Whisper wake word engine."""
        self.engine = WhisperWakeWordEngine(config)
        self.logger = logging.getLogger(__name__)

    async def start_listening(self, callback: Callable[[int, str], Any]) -> None:
        """Start async listening for wake words."""
        await self.engine.start_listening(callback)

    def stop_listening(self) -> None:
        """Stop listening for wake words."""
        self.engine.stop_listening()

    def queue_audio_data(self, audio_data: bytes) -> None:
        """Queue audio data for processing."""
        self.engine.queue_audio_data(audio_data)

    def is_available(self) -> bool:
        """Check if the engine is available."""
        return self.engine.is_available()

    def get_info(self) -> dict:
        """Get engine information."""
        return self.engine.get_info()

    def __getattr__(self, name):
        """Delegate attribute access to the underlying engine."""
        return getattr(self.engine, name)
