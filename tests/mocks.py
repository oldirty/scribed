"""Test mocks and stubs for Scribed components."""

import asyncio
import logging
import threading
import time
import wave
from pathlib import Path
from typing import Callable, Optional, AsyncGenerator, Any
from unittest.mock import Mock


class MockMicrophoneInput:
    """Mock microphone input for testing without hardware."""

    def __init__(self, config: dict) -> None:
        """Initialize mock microphone input.

        Args:
            config: Configuration (same as real MicrophoneInput)
        """
        self.logger = logging.getLogger(__name__)

        self.device_index = config.get("device_index")
        self.sample_rate = config.get("sample_rate", 16000)
        self.channels = config.get("channels", 1)
        self.chunk_size = config.get("chunk_size", 1024)
        self.format = config.get("format", "paInt16")

        self._is_recording = False
        self._record_thread: Optional[threading.Thread] = None
        self._callback: Optional[Callable[[bytes], None]] = None

        # Use test audio file if available, otherwise generate silence
        self.test_audio_file = (
            Path(__file__).parent.parent / "audio_input" / "test_audio.wav"
        )
        self._audio_data: bytes = b""
        self._load_test_audio()

        self.logger.info(
            f"Mock microphone input configured - Rate: {self.sample_rate}Hz, Channels: {self.channels}"
        )

    def _load_test_audio(self) -> None:
        """Load test audio data or generate silence."""
        if self.test_audio_file.exists():
            try:
                with wave.open(str(self.test_audio_file), "rb") as wav_file:
                    self._audio_data = wav_file.readframes(wav_file.getnframes())
                    self.logger.info(f"Loaded test audio from {self.test_audio_file}")
                    return
            except Exception as e:
                self.logger.warning(f"Could not load test audio: {e}")

        # Generate silence if no test file
        duration_seconds = 5.0  # 5 seconds of silence
        samples = int(self.sample_rate * duration_seconds * self.channels)
        if self.format == "paInt16":
            # 16-bit signed integer silence
            self._audio_data = b"\x00\x00" * samples
        else:
            # Default to bytes
            self._audio_data = b"\x00" * (samples * 2)  # Assume 16-bit

        self.logger.info("Generated silence for mock audio")

    def start_recording(self, callback: Callable[[bytes], None]) -> None:
        """Start mock recording.

        Args:
            callback: Function to call with audio data chunks
        """
        if self._is_recording:
            self.logger.warning("Already recording")
            return

        self._callback = callback
        self._is_recording = True

        # Start mock recording thread
        self._record_thread = threading.Thread(
            target=self._mock_record_loop, daemon=True
        )
        self._record_thread.start()

        self.logger.info("Started mock recording")

    def stop_recording(self) -> None:
        """Stop mock recording."""
        self._is_recording = False

        if self._record_thread and self._record_thread.is_alive():
            self._record_thread.join(timeout=2.0)

        self.logger.info("Stopped mock recording")

    def _mock_record_loop(self) -> None:
        """Mock recording loop that sends test audio data."""
        chunk_duration = self.chunk_size / self.sample_rate  # seconds per chunk
        bytes_per_sample = 2 if self.format == "paInt16" else 1
        bytes_per_chunk = self.chunk_size * self.channels * bytes_per_sample

        data_pos = 0

        while self._is_recording:
            # Get next chunk of audio data
            if data_pos + bytes_per_chunk <= len(self._audio_data):
                chunk = self._audio_data[data_pos : data_pos + bytes_per_chunk]
                data_pos += bytes_per_chunk
            else:
                # Loop back to beginning or pad with silence
                remaining = len(self._audio_data) - data_pos
                if remaining > 0:
                    chunk = self._audio_data[data_pos:] + b"\x00" * (
                        bytes_per_chunk - remaining
                    )
                else:
                    chunk = b"\x00" * bytes_per_chunk
                data_pos = 0

            # Call callback
            if self._callback:
                try:
                    self._callback(chunk)
                except Exception as e:
                    self.logger.error(f"Error in mock audio callback: {e}")

            # Sleep to simulate real-time audio
            time.sleep(chunk_duration)

    def is_recording(self) -> bool:
        """Check if mock recording."""
        return self._is_recording

    def get_buffer_data(self, duration_seconds: float) -> bytes:
        """Get mock buffer data."""
        bytes_per_sample = 2 if self.format == "paInt16" else 1
        total_bytes = int(
            duration_seconds * self.sample_rate * self.channels * bytes_per_sample
        )

        if total_bytes <= len(self._audio_data):
            return self._audio_data[:total_bytes]
        else:
            # Repeat data if needed
            repetitions = (total_bytes // len(self._audio_data)) + 1
            repeated_data = self._audio_data * repetitions
            return repeated_data[:total_bytes]

    def get_info(self) -> dict:
        """Get mock microphone info."""
        return {
            "device_index": self.device_index,
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "chunk_size": self.chunk_size,
            "format": self.format,
            "is_recording": self._is_recording,
            "available": True,  # Always available in mock
            "buffer_size": 0,
            "mock": True,
        }

    @staticmethod
    def is_available() -> bool:
        """Mock is always available."""
        return True

    @staticmethod
    def list_devices() -> list:
        """Return mock device list."""
        return [
            {
                "index": 0,
                "name": "Mock Microphone Device",
                "channels": 1,
                "sample_rate": 16000.0,
                "host_api": 0,
            }
        ]

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop_recording()


class MockAsyncMicrophoneInput:
    """Mock async microphone input for testing."""

    def __init__(self, config: dict):
        """Initialize mock async microphone input."""
        self.microphone = MockMicrophoneInput(config)
        self.logger = logging.getLogger(__name__)
        self._audio_queue: asyncio.Queue[bytes] = asyncio.Queue()
        self._running = False

    async def start_recording(
        self, callback: Optional[Callable[[bytes], None]] = None
    ) -> None:
        """Start mock async recording."""
        self._running = True

        # Start the mock microphone with our queue-based callback
        def queue_callback(audio_data: bytes):
            try:
                # Use thread-safe method to put in queue
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(self._audio_queue.put(audio_data))
                loop.close()
            except Exception as e:
                self.logger.error(f"Error queuing mock audio data: {e}")

        # Start recording in thread
        await asyncio.get_event_loop().run_in_executor(
            None, self.microphone.start_recording, queue_callback
        )

        # Start processing audio if callback provided
        if callback:
            asyncio.create_task(self._process_audio(callback))

    async def _process_audio(self, callback: Callable[[bytes], None]) -> None:
        """Process mock audio data from queue."""
        while self._running:
            try:
                # Wait for audio data with timeout
                audio_data = await asyncio.wait_for(
                    self._audio_queue.get(), timeout=1.0
                )

                # Call the user callback
                if asyncio.iscoroutinefunction(callback):
                    await callback(audio_data)
                else:
                    callback(audio_data)

            except asyncio.TimeoutError:
                # Normal timeout, continue listening
                continue
            except Exception as e:
                self.logger.error(f"Error processing mock audio data: {e}")

    async def get_audio_stream(self) -> AsyncGenerator[bytes, None]:
        """Get mock async generator for audio stream."""
        self._running = True

        # Start recording
        def queue_callback(audio_data: bytes):
            try:
                # Use thread-safe method to put in queue
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(self._audio_queue.put(audio_data))
                loop.close()
            except Exception:
                pass

        await asyncio.get_event_loop().run_in_executor(
            None, self.microphone.start_recording, queue_callback
        )

        try:
            while self._running:
                audio_data = await asyncio.wait_for(
                    self._audio_queue.get(), timeout=1.0
                )
                yield audio_data
        except asyncio.TimeoutError:
            pass
        finally:
            await self.stop_recording()

    async def stop_recording(self) -> None:
        """Stop mock async recording."""
        self._running = False
        await asyncio.get_event_loop().run_in_executor(
            None, self.microphone.stop_recording
        )

    def is_recording(self) -> bool:
        """Check if mock recording."""
        return self.microphone.is_recording()

    def get_info(self) -> dict:
        """Get mock microphone info."""
        return self.microphone.get_info()


class MockWakeWordEngine:
    """Mock wake word engine for testing."""

    def __init__(self, config: dict):
        """Initialize mock wake word engine."""
        self.config = config
        self.logger = logging.getLogger(__name__)
        self._running = False
        self._callback: Optional[Callable] = None

    def set_wake_word_callback(self, callback: Callable) -> None:
        """Set wake word detection callback."""
        self._callback = callback

    async def start_detection(self) -> None:
        """Start mock wake word detection."""
        self._running = True
        self.logger.info("Mock wake word detection started")

        # Simulate detecting a wake word after a short delay
        await asyncio.sleep(0.5)
        if self._running and self._callback:
            self._callback("test_wake_word", 0.95)

    async def stop_detection(self) -> None:
        """Stop mock wake word detection."""
        self._running = False
        self.logger.info("Mock wake word detection stopped")

    def process_audio(self, audio_data: bytes) -> None:
        """Process audio for wake word detection (mock)."""
        # Mock processing - occasionally trigger wake word
        import random

        if random.random() < 0.01:  # 1% chance to trigger
            if self._callback:
                self._callback("test_wake_word", 0.85)

    def is_running(self) -> bool:
        """Check if mock detection is running."""
        return self._running


class MockAsyncWakeWordEngine:
    """Mock async wake word engine for testing."""

    def __init__(self, config: dict):
        """Initialize mock async wake word engine."""
        self.config = config
        self.logger = logging.getLogger(__name__)
        self._running = False
        self._callback: Optional[Callable] = None
        self.engine = MockWakeWordEngine(config)  # Use sync mock internally

    async def start_listening(self, callback: Callable) -> None:
        """Start mock async wake word detection."""
        self._running = True
        self._callback = callback
        self.logger.info("Mock async wake word detection started")

        # Simulate detecting a wake word after a short delay
        await asyncio.sleep(0.5)
        if self._running and self._callback:
            if asyncio.iscoroutinefunction(self._callback):
                await self._callback(0, "test_wake_word")
            else:
                self._callback(0, "test_wake_word")

    async def stop_listening(self) -> None:
        """Stop mock async wake word detection."""
        self._running = False
        self.logger.info("Mock async wake word detection stopped")

    def process_audio(self, audio_data: bytes) -> None:
        """Process audio for wake word detection (mock)."""
        # Delegate to sync engine
        self.engine.process_audio(audio_data)

    def is_running(self) -> bool:
        """Check if mock detection is running."""
        return self._running

    def set_wake_word_callback(self, callback: Callable) -> None:
        """Set wake word detection callback."""
        self._callback = callback
