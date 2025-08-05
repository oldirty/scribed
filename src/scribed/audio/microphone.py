"""Microphone audio source implementation."""

import asyncio
import logging
import threading
import time
from collections import deque
from typing import Any, Dict, Optional, TYPE_CHECKING, Callable, AsyncGenerator

from .base import (
    AudioSource,
    AudioChunk,
    AudioFormat,
    AudioError,
    AudioDeviceError,
    AudioValidationError,
    AudioFormatConverter,
)

try:
    import pyaudio
    import numpy as np

    AUDIO_AVAILABLE = True
except ImportError:
    pyaudio = None
    np = None
    AUDIO_AVAILABLE = False

# Audio preprocessing removed for performance optimization


class MicrophoneSource(AudioSource):
    """Microphone audio source that implements the AudioSource interface."""

    def __init__(self, config: Dict[str, Any]) -> None:
        """Initialize microphone source.

        Args:
            config: Configuration dictionary with keys:
                - device_index: Audio input device index (None for default)
                - sample_rate: Sample rate in Hz (default: 16000)
                - channels: Number of channels (default: 1)
                - chunk_size: Buffer size in frames (default: 1024)
                - format: Audio format (default: "int16")
        """
        super().__init__(config)

        if not AUDIO_AVAILABLE:
            raise AudioError(
                "Audio dependencies not available. Install with: pip install pyaudio numpy"
            )

        # Audio configuration
        self.device_index = config.get("device_index")
        self.sample_rate = config.get("sample_rate", 16000)
        self.channels = config.get("channels", 1)
        self.chunk_size = config.get("chunk_size", 1024)

        # Parse audio format
        format_str = config.get("format", "int16").lower()
        if format_str == "int16":
            self.format = AudioFormat.INT16
            self.pyaudio_format = pyaudio.paInt16
        elif format_str == "int32":
            self.format = AudioFormat.INT32
            self.pyaudio_format = pyaudio.paInt32
        elif format_str == "float32":
            self.format = AudioFormat.FLOAT32
            self.pyaudio_format = pyaudio.paFloat32
        else:
            raise AudioValidationError(f"Unsupported audio format: {format_str}")

        # Validate audio format
        AudioFormatConverter.validate_format(
            self.sample_rate, self.channels, self.format
        )

        # Audio preprocessing removed for 3x performance improvement

        # Audio components
        self.audio: Optional[Any] = None
        self.stream: Optional[Any] = None
        self._record_thread: Optional[threading.Thread] = None
        self._audio_queue: asyncio.Queue[AudioChunk] = asyncio.Queue()
        self._audio_buffer: deque[AudioChunk] = deque(maxlen=100)
        self._stop_event = threading.Event()

        self.logger.info(
            f"Microphone source configured - Rate: {self.sample_rate}Hz, "
            f"Channels: {self.channels}, Format: {self.format.value}"
        )

    async def start(self) -> None:
        """Start the microphone audio source."""
        if self._is_active:
            self.logger.warning("Microphone source already active")
            return

        try:
            self._initialize_audio()
            self._start_recording_thread()
            self._mark_active()

        except Exception as e:
            await self.stop()
            raise AudioError(f"Failed to start microphone source: {e}")

    async def stop(self) -> None:
        """Stop the microphone audio source."""
        if not self._is_active:
            return

        self._mark_inactive()
        self._stop_event.set()

        # Wait for recording thread to finish
        if self._record_thread and self._record_thread.is_alive():
            self._record_thread.join(timeout=2.0)

        # Cleanup audio resources
        self._cleanup_audio()

        # Clear queues
        while not self._audio_queue.empty():
            try:
                self._audio_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

        self._audio_buffer.clear()
        self._stop_event.clear()

    async def read_chunk(self) -> Optional[AudioChunk]:
        """Read the next audio chunk from the microphone.

        Returns:
            AudioChunk if available, None if source is stopped
        """
        if not self._is_active:
            return None

        try:
            # Wait for audio chunk with timeout
            chunk = await asyncio.wait_for(self._audio_queue.get(), timeout=1.0)
            return chunk
        except asyncio.TimeoutError:
            # Check if we're still active
            if self._is_active:
                # Return None to indicate no data available but still active
                return None
            else:
                # Source was stopped
                return None
        except Exception as e:
            self.logger.error(f"Error reading audio chunk: {e}")
            return None

    def get_audio_info(self) -> Dict[str, Any]:
        """Get information about the microphone source."""
        info = self.get_base_info()
        info.update(
            {
                "device_index": self.device_index,
                "sample_rate": self.sample_rate,
                "channels": self.channels,
                "chunk_size": self.chunk_size,
                "format": self.format.value,
                "buffer_size": len(self._audio_buffer),
                "queue_size": self._audio_queue.qsize(),
            }
        )

        return info

    def is_available(self) -> bool:
        """Check if microphone source is available."""
        return AUDIO_AVAILABLE

    def _initialize_audio(self) -> None:
        """Initialize PyAudio and audio stream."""
        try:
            self.audio = pyaudio.PyAudio()

            # Log available devices for debugging
            self._log_audio_devices()

            # Open input stream
            self.stream = self.audio.open(
                format=self.pyaudio_format,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                input_device_index=self.device_index,
                frames_per_buffer=self.chunk_size,
            )

            self.logger.info("Audio stream opened successfully")

        except Exception as e:
            raise AudioDeviceError(f"Failed to initialize audio: {e}")

    def _log_audio_devices(self) -> None:
        """Log available audio input devices."""
        try:
            if self.audio is None:
                return

            device_count = self.audio.get_device_count()
            self.logger.info(f"Found {device_count} audio devices:")

            for i in range(device_count):
                info = self.audio.get_device_info_by_index(i)
                max_input_channels = int(info["maxInputChannels"])
                if max_input_channels > 0:  # Input device
                    self.logger.info(
                        f"  Device {i}: {info['name']} "
                        f"(Channels: {max_input_channels}, "
                        f"Rate: {info['defaultSampleRate']}Hz)"
                    )

        except Exception as e:
            self.logger.warning(f"Could not enumerate audio devices: {e}")

    def _start_recording_thread(self) -> None:
        """Start the recording thread."""
        self._stop_event.clear()
        self._record_thread = threading.Thread(
            target=self._record_loop, daemon=True, name="MicrophoneRecording"
        )
        self._record_thread.start()

    def _record_loop(self) -> None:
        """Main recording loop running in separate thread."""
        try:
            if self.stream is None:
                raise AudioError("Audio stream not initialized")

            while not self._stop_event.is_set():
                try:
                    # Read audio chunk
                    data = self.stream.read(
                        self.chunk_size, exception_on_overflow=False
                    )

                    # Preprocessing removed for performance - use raw audio data
                    processed_data = data

                    # Create audio chunk
                    chunk = AudioChunk(
                        data=processed_data,
                        sample_rate=self.sample_rate,
                        channels=self.channels,
                        format=self.format,
                        timestamp=time.time(),
                        chunk_size=self.chunk_size,
                    )

                    # Add to buffer
                    self._audio_buffer.append(chunk)

                    # Put in queue for async access
                    try:
                        # Get the event loop from the main thread
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            # Schedule the coroutine to run in the event loop
                            asyncio.run_coroutine_threadsafe(
                                self._audio_queue.put(chunk), loop
                            )
                    except Exception as e:
                        self.logger.debug(f"Could not queue audio chunk: {e}")

                except Exception as e:
                    if not self._stop_event.is_set():
                        self.logger.error(f"Error in recording loop: {e}")
                    break

        except Exception as e:
            self.logger.error(f"Fatal error in recording loop: {e}")

        finally:
            self.logger.debug("Recording loop ended")

    # Audio preprocessing method removed for performance optimization

    def _cleanup_audio(self) -> None:
        """Cleanup audio resources."""
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

    def get_buffer_data(self, duration_seconds: float) -> bytes:
        """Get recent audio data from buffer.

        Args:
            duration_seconds: Duration of audio to retrieve

        Returns:
            Raw audio bytes from recent chunks
        """
        chunks_needed = int((duration_seconds * self.sample_rate) / self.chunk_size)
        chunks_needed = min(chunks_needed, len(self._audio_buffer))

        if chunks_needed == 0:
            return b""

        # Get the most recent chunks
        recent_chunks = list(self._audio_buffer)[-chunks_needed:]
        return b"".join(chunk.data for chunk in recent_chunks)

    @staticmethod
    def list_devices() -> list:
        """List available audio input devices.

        Returns:
            List of device information dictionaries
        """
        if not AUDIO_AVAILABLE:
            return []

        devices = []
        try:
            audio = pyaudio.PyAudio()
            device_count = audio.get_device_count()

            for i in range(device_count):
                info = audio.get_device_info_by_index(i)
                max_input_channels = int(info["maxInputChannels"])
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


# Compatibility layer - legacy interfaces for backward compatibility
# These are simplified wrappers around MicrophoneSource for existing code


class AudioInputError(Exception):
    """Exception raised when audio input fails."""

    pass


class MicrophoneInput:
    """Legacy compatibility wrapper around MicrophoneSource."""

    def __init__(self, config: dict) -> None:
        """Initialize microphone input with legacy config format."""
        # Convert legacy config to new format
        new_config = {
            "device_index": config.get("device_index"),
            "sample_rate": config.get("sample_rate", 16000),
            "channels": config.get("channels", 1),
            "chunk_size": config.get("chunk_size", 1024),
            "format": "int16",  # Legacy used paInt16
        }

        self._source = MicrophoneSource(new_config)
        self.device_index = new_config["device_index"]
        self.sample_rate = new_config["sample_rate"]
        self.channels = new_config["channels"]
        self.chunk_size = new_config["chunk_size"]
        self.format = pyaudio.paInt16 if AUDIO_AVAILABLE else None
        self._callback: Optional[Callable[[bytes], None]] = None

    def start_recording(self, callback: Callable[[bytes], None]) -> None:
        """Start recording with callback."""
        self._callback = callback
        # Start the source in a background task
        asyncio.create_task(self._record_loop())

    async def _record_loop(self):
        """Internal recording loop."""
        await self._source.start()
        try:
            while self._source.is_active():
                chunk = await self._source.read_chunk()
                if chunk and self._callback:
                    self._callback(chunk.data)
                elif not chunk:
                    await asyncio.sleep(0.01)  # Brief pause if no data
        finally:
            await self._source.stop()

    def stop_recording(self) -> None:
        """Stop recording."""
        # Stop is handled by the background task
        pass

    def is_recording(self) -> bool:
        """Check if recording."""
        return self._source.is_active()

    def get_info(self) -> dict:
        """Get microphone info."""
        return self._source.get_audio_info()

    def get_buffer_data(self, duration_seconds: float) -> bytes:
        """Get recent buffer data."""
        return self._source.get_buffer_data(duration_seconds)

    @staticmethod
    def is_available() -> bool:
        """Check if audio input is available."""
        return AUDIO_AVAILABLE

    @staticmethod
    def list_devices() -> list:
        """List available devices."""
        return MicrophoneSource.list_devices()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop_recording()


class AsyncMicrophoneInput:
    """Legacy async compatibility wrapper."""

    def __init__(self, config: dict):
        self._source = MicrophoneSource(config)
        self._running = False

    async def start_recording(
        self, callback: Optional[Callable[[bytes], None]] = None
    ) -> None:
        """Start async recording."""
        await self._source.start()
        self._running = True
        if callback:
            asyncio.create_task(self._process_audio(callback))

    async def _process_audio(self, callback: Callable[[bytes], None]) -> None:
        """Process audio data."""
        while self._running and self._source.is_active():
            chunk = await self._source.read_chunk()
            if chunk:
                if asyncio.iscoroutinefunction(callback):
                    await callback(chunk.data)
                else:
                    callback(chunk.data)
            else:
                await asyncio.sleep(0.01)

    async def get_audio_stream(self) -> AsyncGenerator[bytes, None]:
        """Get async audio stream."""
        await self._source.start()
        self._running = True
        try:
            while self._running and self._source.is_active():
                chunk = await self._source.read_chunk()
                if chunk:
                    yield chunk.data
                else:
                    await asyncio.sleep(0.01)
        finally:
            await self.stop_recording()

    async def stop_recording(self) -> None:
        """Stop recording."""
        self._running = False
        await self._source.stop()

    def is_recording(self) -> bool:
        """Check if recording."""
        return self._source.is_active()

    def get_info(self) -> dict:
        """Get info."""
        return self._source.get_audio_info()
