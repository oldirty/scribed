"""Audio input handling for microphone and streaming audio."""

import asyncio
import logging
import struct
import threading
import time
from typing import Callable, Optional, AsyncGenerator, Any
from collections import deque

try:
    import pyaudio  # type: ignore
    import numpy as np  # type: ignore

    AUDIO_AVAILABLE = True
except ImportError:
    pyaudio = None  # type: ignore
    np = None  # type: ignore
    AUDIO_AVAILABLE = False


class AudioInputError(Exception):
    """Exception raised when audio input fails."""

    pass


class MicrophoneInput:
    """Microphone input handler for real-time audio processing."""

    def __init__(self, config: dict) -> None:
        """Initialize microphone input.

        Args:
            config: Configuration with keys:
                - device_index: Audio input device index (None for default)
                - sample_rate: Sample rate in Hz (default: 16000)
                - channels: Number of channels (default: 1)
                - chunk_size: Buffer size in frames (default: 1024)
                - format: Audio format (default: paInt16)
        """
        self.logger = logging.getLogger(__name__)

        if not AUDIO_AVAILABLE:
            raise AudioInputError(
                "Audio dependencies not available. Install with: pip install pyaudio numpy"
            )

        self.device_index = config.get("device_index")
        self.sample_rate = config.get("sample_rate", 16000)
        self.channels = config.get("channels", 1)
        self.chunk_size = config.get("chunk_size", 1024)
        self.format = getattr(pyaudio, config.get("format", "paInt16"))

        # Audio components
        self.audio: Optional[Any] = None  # pyaudio.PyAudio when available
        self.stream: Optional[Any] = None  # pyaudio stream when available
        self._is_recording = False
        self._record_thread: Optional[threading.Thread] = None
        self._callback: Optional[Callable[[bytes], None]] = None
        self._audio_buffer: deque[bytes] = deque(maxlen=100)  # Buffer for audio chunks

        self.logger.info(
            f"Microphone input configured - Rate: {self.sample_rate}Hz, Channels: {self.channels}"
        )

    def _initialize_audio(self) -> None:
        """Initialize PyAudio."""
        try:
            self.audio = pyaudio.PyAudio()  # type: ignore

            # Log available devices for debugging
            self._log_audio_devices()

            # Open input stream
            self.stream = self.audio.open(  # type: ignore
                format=self.format,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                input_device_index=self.device_index,
                frames_per_buffer=self.chunk_size,
            )

            self.logger.info("Audio stream opened successfully")

        except Exception as e:
            raise AudioInputError(f"Failed to initialize audio: {e}")

    def _log_audio_devices(self) -> None:
        """Log available audio input devices."""
        try:
            assert self.audio is not None, "Audio must be initialized first"

            device_count = self.audio.get_device_count()  # type: ignore
            self.logger.info(f"Found {device_count} audio devices:")

            for i in range(device_count):
                info = self.audio.get_device_info_by_index(i)  # type: ignore
                max_input_channels = int(info["maxInputChannels"])  # type: ignore
                if max_input_channels > 0:  # Input device
                    self.logger.info(
                        f"  Device {i}: {info['name']} "
                        f"(Channels: {max_input_channels}, "
                        f"Rate: {info['defaultSampleRate']}Hz)"
                    )

        except Exception as e:
            self.logger.warning(f"Could not enumerate audio devices: {e}")

    def start_recording(self, callback: Callable[[bytes], None]) -> None:
        """Start recording audio.

        Args:
            callback: Function to call with audio data chunks.
                     Receives raw audio bytes.
        """
        if self._is_recording:
            self.logger.warning("Already recording")
            return

        self._callback = callback

        try:
            self._initialize_audio()

            # Start recording thread
            self._is_recording = True
            self._record_thread = threading.Thread(
                target=self._record_loop, daemon=True
            )
            self._record_thread.start()

            self.logger.info("Started recording audio")

        except Exception as e:
            self.stop_recording()
            raise AudioInputError(f"Failed to start recording: {e}")

    def stop_recording(self) -> None:
        """Stop recording audio."""
        self._is_recording = False

        if self._record_thread and self._record_thread.is_alive():
            self._record_thread.join(timeout=2.0)

        # Cleanup audio
        if self.stream:
            try:
                self.stream.stop_stream()
                self.stream.close()
            except Exception as e:
                self.logger.warning(f"Error closing audio stream: {e}")
            finally:
                self.stream = None

        if self.audio:
            try:
                self.audio.terminate()
            except Exception as e:
                self.logger.warning(f"Error terminating audio: {e}")
            finally:
                self.audio = None

        self.logger.info("Stopped recording audio")

    def _record_loop(self) -> None:
        """Main recording loop running in separate thread."""
        try:
            assert self.stream is not None, "Audio stream must be initialized"

            while self._is_recording:
                # Read audio chunk
                data = self.stream.read(self.chunk_size, exception_on_overflow=False)  # type: ignore

                # Add to buffer
                self._audio_buffer.append(data)

                # Call callback with audio data
                if self._callback:
                    try:
                        self._callback(data)
                    except Exception as e:
                        self.logger.error(f"Error in audio callback: {e}")

        except Exception as e:
            self.logger.error(f"Error in recording loop: {e}")
            self._is_recording = False

    def is_recording(self) -> bool:
        """Check if currently recording."""
        return self._is_recording

    def get_buffer_data(self, duration_seconds: float) -> bytes:
        """Get recent audio data from buffer.

        Args:
            duration_seconds: Duration of audio to retrieve

        Returns:
            Raw audio bytes
        """
        chunks_needed = int((duration_seconds * self.sample_rate) / self.chunk_size)
        chunks_needed = min(chunks_needed, len(self._audio_buffer))

        if chunks_needed == 0:
            return b""

        # Get the most recent chunks
        recent_chunks = list(self._audio_buffer)[-chunks_needed:]
        return b"".join(recent_chunks)

    def get_info(self) -> dict:
        """Get information about the microphone input."""
        return {
            "device_index": self.device_index,
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "chunk_size": self.chunk_size,
            "format": self.format,
            "is_recording": self._is_recording,
            "available": AUDIO_AVAILABLE,
            "buffer_size": len(self._audio_buffer),
        }

    @staticmethod
    def is_available() -> bool:
        """Check if audio input is available."""
        return AUDIO_AVAILABLE

    @staticmethod
    def list_devices() -> list:
        """List available audio input devices."""
        if not AUDIO_AVAILABLE:
            return []

        devices = []
        try:
            audio = pyaudio.PyAudio()  # type: ignore
            device_count = audio.get_device_count()  # type: ignore

            for i in range(device_count):
                info = audio.get_device_info_by_index(i)  # type: ignore
                max_input_channels = int(info["maxInputChannels"])  # type: ignore
                if max_input_channels > 0:  # Input device
                    devices.append(
                        {
                            "index": i,
                            "name": info["name"],
                            "channels": max_input_channels,
                            "sample_rate": info["defaultSampleRate"],
                            "host_api": info["hostApi"],
                        }
                    )

            audio.terminate()

        except Exception:
            pass

        return devices

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - cleanup resources."""
        self.stop_recording()


class AsyncMicrophoneInput:
    """Async wrapper for MicrophoneInput."""

    def __init__(self, config: dict):
        """Initialize async microphone input."""
        self.microphone = MicrophoneInput(config)
        self.logger = logging.getLogger(__name__)
        self._audio_queue: asyncio.Queue[bytes] = asyncio.Queue()
        self._running = False

    async def start_recording(
        self, callback: Optional[Callable[[bytes], None]] = None
    ) -> None:
        """Start async recording.

        Args:
            callback: Optional callback for audio data
        """
        self._running = True

        # Start the sync microphone with our queue-based callback
        def queue_callback(audio_data: bytes):
            try:
                asyncio.create_task(self._audio_queue.put(audio_data))
            except Exception as e:
                self.logger.error(f"Error queuing audio data: {e}")

        # Start recording in thread
        await asyncio.get_event_loop().run_in_executor(
            None, self.microphone.start_recording, queue_callback
        )

        # Start processing audio if callback provided
        if callback:
            asyncio.create_task(self._process_audio(callback))

    async def _process_audio(self, callback: Callable[[bytes], None]) -> None:
        """Process audio data from queue."""
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
                self.logger.error(f"Error processing audio data: {e}")

    async def get_audio_stream(self) -> AsyncGenerator[bytes, None]:
        """Get async generator for audio stream."""
        self._running = True

        # Start recording
        def queue_callback(audio_data: bytes):
            try:
                asyncio.create_task(self._audio_queue.put(audio_data))
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
        """Stop async recording."""
        self._running = False
        await asyncio.get_event_loop().run_in_executor(
            None, self.microphone.stop_recording
        )

    def is_recording(self) -> bool:
        """Check if recording."""
        return self.microphone.is_recording()

    def get_info(self) -> dict:
        """Get microphone info."""
        return self.microphone.get_info()
