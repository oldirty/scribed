"""Wake word detection engine using Picovoice Porcupine."""

import asyncio
import logging
import struct
import threading
import time
from typing import Callable, Optional, Any
from pathlib import Path

try:
    import pvporcupine
    import pyaudio

    PORCUPINE_AVAILABLE = True
except ImportError:
    pvporcupine = None
    pyaudio = None
    PORCUPINE_AVAILABLE = False


class WakeWordDetectionError(Exception):
    """Exception raised when wake word detection fails."""

    pass


class WakeWordEngine:
    """Wake word detection engine using Picovoice Porcupine."""

    def __init__(self, config: dict) -> None:
        """Initialize the wake word engine.

        Args:
            config: Configuration with keys:
                - access_key: Picovoice access key (required)
                - keywords: List of built-in keywords or paths to custom models
                - sensitivities: List of sensitivity values (0.0-1.0)
                - input_device_index: Audio input device index (None for default)
                - model_path: Path to custom Porcupine model (optional)
        """
        self.logger = logging.getLogger(__name__)

        if not PORCUPINE_AVAILABLE:
            raise WakeWordDetectionError(
                "Porcupine dependencies not available. Install with: pip install pvporcupine pyaudio"
            )

        self.access_key = config.get("access_key")
        if not self.access_key:
            raise WakeWordDetectionError(
                "Picovoice access key is required. Get a free access key at: https://console.picovoice.ai/\n"
                "Add it to your config file under wake_word.access_key"
            )

        self.keywords = config.get("keywords", ["porcupine"])
        self.sensitivities = config.get("sensitivities", [0.5] * len(self.keywords))
        self.input_device_index = config.get("input_device_index")
        self.model_path = config.get("model_path")

        # Validate sensitivities
        if len(self.sensitivities) != len(self.keywords):
            self.sensitivities = [0.5] * len(self.keywords)

        # Initialize components
        self.porcupine = None
        self.audio = None
        self.audio_stream = None
        self._is_listening = False
        self._listen_thread = None
        self._callback = None

        self.logger.info(f"Wake word engine initialized with keywords: {self.keywords}")

    def _initialize_porcupine(self) -> None:
        """Initialize Porcupine wake word detection."""
        try:
            # Parse keywords (can be built-in names or paths to .ppn files)
            keyword_paths = []
            for keyword in self.keywords:
                if isinstance(keyword, str) and keyword.endswith(".ppn"):
                    # Custom model file
                    if not Path(keyword).exists():
                        raise WakeWordDetectionError(
                            f"Custom model file not found: {keyword}"
                        )
                    keyword_paths.append(keyword)
                else:
                    # Built-in keyword - Porcupine will handle this
                    keyword_paths.append(keyword)

            # Initialize Porcupine
            if self.model_path and Path(self.model_path).exists():
                self.porcupine = pvporcupine.create(
                    access_key=self.access_key,
                    keywords=keyword_paths,
                    sensitivities=self.sensitivities,
                    model_path=self.model_path,
                )
            else:
                self.porcupine = pvporcupine.create(
                    access_key=self.access_key,
                    keywords=keyword_paths,
                    sensitivities=self.sensitivities,
                )

            self.logger.info("Porcupine initialized successfully")

        except Exception as e:
            raise WakeWordDetectionError(f"Failed to initialize Porcupine: {e}")

    def _initialize_audio(self) -> None:
        """Initialize PyAudio for microphone input."""
        try:
            self.audio = pyaudio.PyAudio()

            # Open audio stream
            self.audio_stream = self.audio.open(
                rate=self.porcupine.sample_rate,
                channels=1,
                format=pyaudio.paInt16,
                input=True,
                frames_per_buffer=self.porcupine.frame_length,
                input_device_index=self.input_device_index,
            )

            self.logger.info(
                f"Audio stream opened - Sample rate: {self.porcupine.sample_rate}Hz"
            )

        except Exception as e:
            raise WakeWordDetectionError(f"Failed to initialize audio: {e}")

    def start_listening(self, callback: Callable[[int, str], None]) -> None:
        """Start listening for wake words.

        Args:
            callback: Function to call when wake word is detected.
                     Receives (keyword_index, keyword_name) as arguments.
        """
        if self._is_listening:
            self.logger.warning("Already listening for wake words")
            return

        self._callback = callback

        try:
            # Initialize components
            self._initialize_porcupine()
            self._initialize_audio()

            # Start listening thread
            self._is_listening = True
            self._listen_thread = threading.Thread(
                target=self._listen_loop, daemon=True
            )
            self._listen_thread.start()

            self.logger.info("Started listening for wake words")

        except Exception as e:
            self.stop_listening()
            raise WakeWordDetectionError(f"Failed to start listening: {e}")

    def stop_listening(self) -> None:
        """Stop listening for wake words."""
        self._is_listening = False

        if self._listen_thread and self._listen_thread.is_alive():
            self._listen_thread.join(timeout=2.0)

        # Cleanup audio
        if self.audio_stream:
            try:
                self.audio_stream.stop_stream()
                self.audio_stream.close()
            except Exception as e:
                self.logger.warning(f"Error closing audio stream: {e}")
            finally:
                self.audio_stream = None

        if self.audio:
            try:
                self.audio.terminate()
            except Exception as e:
                self.logger.warning(f"Error terminating audio: {e}")
            finally:
                self.audio = None

        # Cleanup Porcupine
        if self.porcupine:
            try:
                self.porcupine.delete()
            except Exception as e:
                self.logger.warning(f"Error deleting Porcupine: {e}")
            finally:
                self.porcupine = None

        self.logger.info("Stopped listening for wake words")

    def _listen_loop(self) -> None:
        """Main listening loop running in separate thread."""
        try:
            while self._is_listening:
                # Read audio frame
                pcm = self.audio_stream.read(
                    self.porcupine.frame_length, exception_on_overflow=False
                )
                pcm = struct.unpack_from("h" * self.porcupine.frame_length, pcm)

                # Process frame for wake word detection
                keyword_index = self.porcupine.process(pcm)

                if keyword_index >= 0:
                    # Wake word detected!
                    keyword_name = self.keywords[keyword_index]
                    self.logger.info(
                        f"Wake word detected: {keyword_name} (index: {keyword_index})"
                    )

                    if self._callback:
                        try:
                            self._callback(keyword_index, keyword_name)
                        except Exception as e:
                            self.logger.error(f"Error in wake word callback: {e}")

        except Exception as e:
            self.logger.error(f"Error in wake word listening loop: {e}")
            self._is_listening = False

    def is_listening(self) -> bool:
        """Check if currently listening for wake words."""
        return self._is_listening

    def get_info(self) -> dict:
        """Get information about the wake word engine."""
        return {
            "engine": "porcupine",
            "keywords": self.keywords,
            "sensitivities": self.sensitivities,
            "is_listening": self._is_listening,
            "available": PORCUPINE_AVAILABLE,
            "sample_rate": self.porcupine.sample_rate if self.porcupine else None,
            "frame_length": self.porcupine.frame_length if self.porcupine else None,
        }

    @staticmethod
    def is_available() -> bool:
        """Check if Porcupine is available."""
        return PORCUPINE_AVAILABLE

    @staticmethod
    def get_built_in_keywords() -> list:
        """Get list of built-in Porcupine keywords."""
        if not PORCUPINE_AVAILABLE:
            return []

        try:
            # These are common built-in keywords in Porcupine
            return [
                "alexa",
                "americano",
                "blueberry",
                "bumblebee",
                "computer",
                "grapefruit",
                "grasshopper",
                "hey google",
                "hey siri",
                "jarvis",
                "ok google",
                "picovoice",
                "porcupine",
                "terminator",
            ]
        except Exception:
            return ["porcupine"]  # Fallback

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - cleanup resources."""
        self.stop_listening()


class AsyncWakeWordEngine:
    """Async wrapper for WakeWordEngine."""

    def __init__(self, config: dict):
        """Initialize async wake word engine."""
        self.engine = WakeWordEngine(config)
        self.logger = logging.getLogger(__name__)
        self._callback_queue = asyncio.Queue()
        self._running = False

    async def start_listening(self, callback: Callable[[int, str], Any]) -> None:
        """Start async listening for wake words."""
        self._running = True

        # Start the sync engine with our queue-based callback
        def queue_callback(keyword_index: int, keyword_name: str):
            try:
                # Put the detection in the queue
                asyncio.create_task(
                    self._callback_queue.put((keyword_index, keyword_name))
                )
            except Exception as e:
                self.logger.error(f"Error queuing wake word detection: {e}")

        # Start listening in thread
        await asyncio.get_event_loop().run_in_executor(
            None, self.engine.start_listening, queue_callback
        )

        # Start processing detections
        asyncio.create_task(self._process_detections(callback))

    async def _process_detections(self, callback: Callable[[int, str], Any]) -> None:
        """Process wake word detections from queue."""
        while self._running:
            try:
                # Wait for detection with timeout
                keyword_index, keyword_name = await asyncio.wait_for(
                    self._callback_queue.get(), timeout=1.0
                )

                # Call the user callback
                if asyncio.iscoroutinefunction(callback):
                    await callback(keyword_index, keyword_name)
                else:
                    callback(keyword_index, keyword_name)

            except asyncio.TimeoutError:
                # Normal timeout, continue listening
                continue
            except Exception as e:
                self.logger.error(f"Error processing wake word detection: {e}")

    async def stop_listening(self) -> None:
        """Stop async listening."""
        self._running = False
        await asyncio.get_event_loop().run_in_executor(None, self.engine.stop_listening)

    def is_listening(self) -> bool:
        """Check if listening."""
        return self.engine.is_listening()

    def get_info(self) -> dict:
        """Get engine info."""
        return self.engine.get_info()
