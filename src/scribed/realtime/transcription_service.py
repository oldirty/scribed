"""Real-time transcription service with wake word and power words integration."""

import asyncio
import logging
import re
import tempfile
import time
from pathlib import Path
from typing import Optional, Callable, Dict, Any, Awaitable, Coroutine, List
from enum import Enum

from ..transcription.service import TranscriptionService
from ..wake_word import AsyncWakeWordEngine, WakeWordDetectionError
from ..audio.microphone_input import AsyncMicrophoneInput, AudioInputError
from ..power_words import AsyncPowerWordsEngine, PowerWordsSecurityError

# Type for wake word engines (supports both Picovoice and Whisper)
from typing import Union

try:
    from ..wake_word.whisper_engine import AsyncWhisperWakeWordEngine

    WakeWordEngineUnion = Union[AsyncWakeWordEngine, AsyncWhisperWakeWordEngine]
except ImportError:
    WakeWordEngineUnion = AsyncWakeWordEngine


class TranscriptionState(Enum):
    """States of the real-time transcription system."""

    IDLE = "idle"
    LISTENING_FOR_WAKE_WORD = "listening_for_wake_word"
    ACTIVE_TRANSCRIPTION = "active_transcription"
    PROCESSING = "processing"
    ERROR = "error"


class RealTimeTranscriptionService:
    """Real-time transcription service with wake word activation and power words."""

    def __init__(
        self,
        wake_word_config: dict,
        microphone_config: dict,
        transcription_config: dict,
        power_words_config: Optional[dict] = None,
    ):
        """Initialize the real-time transcription service.

        Args:
            wake_word_config: Wake word engine configuration
            microphone_config: Microphone input configuration
            transcription_config: Transcription service configuration
            power_words_config: Power words configuration (optional)
        """
        self.logger = logging.getLogger(__name__)

        # Configuration
        self.wake_word_config = wake_word_config
        self.microphone_config = microphone_config
        self.transcription_config = transcription_config
        self.power_words_config = power_words_config or {}

        # Components
        self.wake_word_engine: Optional[Any] = (
            None  # Can be AsyncWakeWordEngine or AsyncWhisperWakeWordEngine
        )
        self.microphone: Optional[AsyncMicrophoneInput] = None
        self.transcription_service: Optional[TranscriptionService] = None
        self.power_words_engine: Optional[AsyncPowerWordsEngine] = None

        # State management
        self.state = TranscriptionState.IDLE
        self._is_running = False
        self._transcription_active = False
        self._silence_timeout = wake_word_config.get("silence_timeout", 15)
        self._stop_phrase = wake_word_config.get("stop_phrase", "stop listening")

        # Audio buffering
        self._audio_buffer: List[bytes] = []
        self._transcription_start_time: Optional[float] = None
        self._audio_processing_queue: asyncio.Queue[bytes] = asyncio.Queue(
            maxsize=100
        )  # Limit queue size
        self._audio_processor_task: Optional[asyncio.Task] = None
        self._silence_task: Optional[asyncio.Task] = None

        # Callbacks
        self._on_wake_word_callback: Optional[Callable[[int, str], None]] = None
        self._on_transcription_callback: Optional[
            Callable[[Any, bool], Coroutine[Any, Any, None]]
        ] = None
        self._on_state_change_callback: Optional[
            Callable[
                [TranscriptionState, TranscriptionState], Coroutine[Any, Any, None]
            ]
        ] = None

        self.logger.info("Real-time transcription service initialized")

    def _initialize_components(self) -> None:
        """Initialize all service components."""
        try:
            # Initialize wake word engine
            if not self.wake_word_engine:
                from ..wake_word import create_wake_word_engine

                self.wake_word_engine = create_wake_word_engine(self.wake_word_config)
                self.logger.info(
                    f"Wake word engine initialized: {self.wake_word_config.get('engine', 'picovoice')}"
                )

            # Initialize microphone
            if not self.microphone:
                self.microphone = AsyncMicrophoneInput(self.microphone_config)
                self.logger.info("Microphone input initialized")

            # Initialize transcription service
            if not self.transcription_service:
                self.transcription_service = TranscriptionService(
                    self.transcription_config
                )
                self.logger.info("Transcription service initialized")

            # Initialize power words engine if configured
            if self.power_words_config and self.power_words_config.get(
                "enabled", False
            ):
                if not self.power_words_engine:
                    from ..config import PowerWordsConfig

                    power_config = PowerWordsConfig(**self.power_words_config)
                    self.power_words_engine = AsyncPowerWordsEngine(power_config)
                    self.power_words_engine.set_confirmation_callback(
                        self._confirm_power_word_execution
                    )
                    self.logger.info("Power words engine initialized")

        except Exception as e:
            self.logger.error(f"Failed to initialize components: {e}")
            raise

    async def start_service(self) -> None:
        """Start the real-time transcription service."""
        if self._is_running:
            self.logger.warning("Service is already running")
            return

        try:
            self._initialize_components()

            self._is_running = True
            self._set_state(TranscriptionState.LISTENING_FOR_WAKE_WORD)

            # Start wake word detection
            if not self.wake_word_engine:
                raise RuntimeError("Wake word engine not initialized")

            # Check if this is a Whisper-based wake word engine
            if hasattr(self.wake_word_engine, "queue_audio_data"):
                # Whisper wake word engine - needs audio data from our microphone
                await self.wake_word_engine.start_listening(self._on_wake_word_detected)

                # Start microphone for wake word detection
                if not self.microphone:
                    raise RuntimeError("Microphone not initialized")
                await self.microphone.start_recording(self._on_wake_word_audio_data)

            else:
                # Picovoice engine - has its own audio input
                await self.wake_word_engine.start_listening(self._on_wake_word_detected)

            self.logger.info("Real-time transcription service started")

        except Exception as e:
            self.logger.error(f"Failed to start service: {e}")
            self._set_state(TranscriptionState.ERROR)
            raise

    async def stop_service(self) -> None:
        """Stop the real-time transcription service."""
        self._is_running = False

        # Stop active transcription
        if self._transcription_active:
            await self._stop_transcription()

        # Stop wake word detection
        if self.wake_word_engine:
            await self.wake_word_engine.stop_listening()

        # Stop microphone
        if self.microphone:
            await self.microphone.stop_recording()

        self._set_state(TranscriptionState.IDLE)
        self.logger.info("Real-time transcription service stopped")

    def _on_wake_word_audio_data(self, audio_data: bytes) -> None:
        """Pass audio data to Whisper wake word engine (if applicable)."""
        if self.wake_word_engine and hasattr(self.wake_word_engine, "queue_audio_data"):
            self.wake_word_engine.queue_audio_data(audio_data)

    async def _on_wake_word_detected(
        self, keyword_index: int, keyword_name: str
    ) -> None:
        """Handle wake word detection."""
        self.logger.info(f"Wake word detected: {keyword_name}")

        # Notify callback
        if self._on_wake_word_callback:
            try:
                self._on_wake_word_callback(keyword_index, keyword_name)
            except Exception as e:
                self.logger.error(f"Error in wake word callback: {e}")

        # Start active transcription
        await self._start_transcription()

    async def _start_transcription(self) -> None:
        """Start active transcription mode."""
        if self._transcription_active:
            self.logger.warning("Transcription already active")
            return

        try:
            self._transcription_active = True
            self._transcription_start_time = time.time()
            self._audio_buffer = []

            self._set_state(TranscriptionState.ACTIVE_TRANSCRIPTION)

            # Start microphone recording
            if not self.microphone:
                raise RuntimeError("Microphone not initialized")
            await self.microphone.start_recording(self._on_audio_data_sync)

            # Start silence timeout task (ensure only one is running)
            if self._silence_task and not self._silence_task.done():
                self._silence_task.cancel()
                try:
                    await self._silence_task
                except asyncio.CancelledError:
                    pass
            self._silence_task = asyncio.create_task(self._silence_timeout_task())

            # Start audio processing task (ensure only one is running)
            if self._audio_processor_task and not self._audio_processor_task.done():
                self._audio_processor_task.cancel()
                try:
                    await self._audio_processor_task
                except asyncio.CancelledError:
                    pass
            self._audio_processor_task = asyncio.create_task(self._audio_processor())

            self.logger.info("Active transcription started")

        except Exception as e:
            self.logger.error(f"Failed to start transcription: {e}")
            self._transcription_active = False
            self._set_state(TranscriptionState.ERROR)

    async def _stop_transcription(self) -> None:
        """Stop active transcription mode."""
        if not self._transcription_active:
            return

        self._transcription_active = False

        # Cancel audio processor task
        if self._audio_processor_task and not self._audio_processor_task.done():
            self._audio_processor_task.cancel()
            try:
                await self._audio_processor_task
            except asyncio.CancelledError:
                pass

        # Cancel silence timeout task
        if self._silence_task and not self._silence_task.done():
            self._silence_task.cancel()
            try:
                await self._silence_task
            except asyncio.CancelledError:
                pass

        # Stop microphone
        if self.microphone:
            await self.microphone.stop_recording()

        # Process accumulated audio
        if self._audio_buffer:
            await self._process_final_audio()

        # Clear buffer and queue
        self._audio_buffer = []

        # Clear any remaining audio data from the queue
        while not self._audio_processing_queue.empty():
            try:
                self._audio_processing_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

        # Return to wake word listening
        self._set_state(TranscriptionState.LISTENING_FOR_WAKE_WORD)

        self.logger.info("Active transcription stopped")

    def _on_audio_data_sync(self, audio_data: bytes) -> None:
        """Synchronous wrapper for audio data callback."""
        if not self._transcription_active:
            return

        # Put audio data in queue for sequential processing
        try:
            # Non-blocking put - if queue is full, drop the data to prevent overflow
            try:
                self._audio_processing_queue.put_nowait(audio_data)
            except asyncio.QueueFull:
                # Queue is full, drop this audio chunk to prevent memory issues
                self.logger.warning("Audio processing queue full, dropping audio chunk")
        except Exception as e:
            self.logger.warning(f"Error queuing audio data: {e}")

    async def _audio_processor(self) -> None:
        """Process audio data from queue sequentially to prevent task explosion."""
        while self._transcription_active:
            try:
                # Wait for audio data with timeout
                audio_data = await asyncio.wait_for(
                    self._audio_processing_queue.get(), timeout=1.0
                )

                # Process the audio data
                await self._on_audio_data(audio_data)

            except asyncio.TimeoutError:
                # No audio data received, continue loop
                continue
            except Exception as e:
                self.logger.error(f"Error in audio processor: {e}")
                # Continue processing other audio data
                continue

    async def _on_audio_data(self, audio_data: bytes) -> None:
        """Handle incoming audio data during active transcription."""
        if not self._transcription_active:
            return

        # Add to buffer
        self._audio_buffer.append(audio_data)

        # Process in chunks for near real-time feedback
        buffer_duration = (
            len(self._audio_buffer)
            * self.microphone_config.get("chunk_size", 1024)
            / self.microphone_config.get("sample_rate", 16000)
        )

        if buffer_duration >= 2.0:  # Process every 2 seconds
            await self._process_audio_chunk()

    async def _process_audio_chunk(self) -> None:
        """Process a chunk of audio for transcription."""
        if not self._audio_buffer:
            return

        try:
            self._set_state(TranscriptionState.PROCESSING)

            # Create temporary file with current audio buffer
            audio_data = b"".join(self._audio_buffer)

            # Clear the buffer after copying to prevent reprocessing same audio
            self._audio_buffer = []

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                # Write WAV header and data
                self._write_wav_file(temp_file, audio_data)
                temp_path = temp_file.name

            try:
                # Transcribe the audio chunk
                if not self.transcription_service:
                    self.logger.error("Transcription service not initialized")
                    return

                result = await self.transcription_service.transcribe_file(temp_path)

                if result.text.strip():
                    # Check for stop phrase first
                    if self._check_for_stop_phrase(result.text):
                        self.logger.info("Stop phrase detected")
                        await self._stop_transcription()
                        return

                    # Process power words and extract remaining text for dictation
                    remaining_text = (
                        await self._process_power_words_and_extract_dictation(
                            result.text
                        )
                    )

                    # Only send remaining dictation text to transcription callback
                    if remaining_text.strip():
                        # Create a new result object with only the dictation text
                        from ..transcription.base import (
                            TranscriptionResult,
                            TranscriptionStatus,
                        )

                        dictation_result = TranscriptionResult(
                            text=remaining_text,
                            segments=getattr(result, "segments", []),
                            status=getattr(
                                result, "status", TranscriptionStatus.COMPLETED
                            ),
                        )

                        # Notify callback with partial dictation (after power word removal)
                        if self._on_transcription_callback:
                            try:
                                await self._on_transcription_callback(
                                    dictation_result, True
                                )
                            except Exception as e:
                                self.logger.error(
                                    f"Error in transcription callback: {e}"
                                )

            finally:
                # Clean up temp file
                try:
                    Path(temp_path).unlink()
                except Exception as e:
                    self.logger.warning(f"Failed to delete temp file: {e}")

            self._set_state(TranscriptionState.ACTIVE_TRANSCRIPTION)

        except Exception as e:
            self.logger.error(f"Error processing audio chunk: {e}")
            self._set_state(TranscriptionState.ACTIVE_TRANSCRIPTION)

    async def _process_final_audio(self) -> None:
        """Process final audio buffer when transcription stops."""
        if not self._audio_buffer:
            return

        try:
            self._set_state(TranscriptionState.PROCESSING)

            # Create temporary file with all accumulated audio
            audio_data = b"".join(self._audio_buffer)

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                self._write_wav_file(temp_file, audio_data)
                temp_path = temp_file.name

            try:
                # Transcribe the complete audio
                if not self.transcription_service:
                    self.logger.error(
                        "Transcription service not initialized for final processing"
                    )
                    return

                result = await self.transcription_service.transcribe_file(temp_path)

                # Process power words and extract remaining dictation text
                if result.text.strip():
                    remaining_text = (
                        await self._process_power_words_and_extract_dictation(
                            result.text
                        )
                    )

                    # Only send remaining dictation text to transcription callback
                    if remaining_text.strip():
                        # Create a new result object with only the dictation text
                        from ..transcription.base import (
                            TranscriptionResult,
                            TranscriptionStatus,
                        )

                        dictation_result = TranscriptionResult(
                            text=remaining_text,
                            segments=getattr(result, "segments", []),
                            status=getattr(
                                result, "status", TranscriptionStatus.COMPLETED
                            ),
                        )

                        # Notify callback with final dictation (after power word removal)
                        if self._on_transcription_callback:
                            try:
                                await self._on_transcription_callback(
                                    dictation_result, False
                                )
                            except Exception as e:
                                self.logger.error(
                                    f"Error in final transcription callback: {e}"
                                )

            finally:
                # Clean up temp file
                try:
                    Path(temp_path).unlink()
                except Exception:
                    pass

        except Exception as e:
            self.logger.error(f"Error processing final audio: {e}")

    def _write_wav_file(self, file, audio_data: bytes) -> None:
        """Write audio data as WAV file."""
        import wave
        import struct

        # WAV file parameters
        sample_rate = self.microphone_config.get("sample_rate", 16000)
        channels = self.microphone_config.get("channels", 1)
        sample_width = 2  # 16-bit

        # Write WAV file
        with wave.open(file.name, "wb") as wav_file:
            wav_file.setnchannels(channels)
            wav_file.setsampwidth(sample_width)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(audio_data)

    async def _silence_timeout_task(self) -> None:
        """Task to handle silence timeout."""
        timeout_start = time.time()

        while self._transcription_active:
            await asyncio.sleep(1.0)

            # Check if we've exceeded silence timeout
            if time.time() - timeout_start > self._silence_timeout:
                self.logger.info("Silence timeout reached")
                await self._stop_transcription()
                break

            # Reset timeout if we have recent audio
            if self._audio_buffer:
                timeout_start = time.time()

    def _set_state(self, new_state: TranscriptionState) -> None:
        """Change service state and notify callback."""
        if self.state != new_state:
            old_state = self.state
            self.state = new_state

            self.logger.info(f"State changed: {old_state.value} -> {new_state.value}")

            # Notify callback
            if self._on_state_change_callback:
                try:
                    # Schedule the callback to run as a coroutine
                    asyncio.create_task(
                        self._on_state_change_callback(old_state, new_state)
                    )
                except Exception as e:
                    self.logger.error(f"Error scheduling state change callback: {e}")

    # Public API methods

    def set_wake_word_callback(self, callback: Callable[[int, str], None]) -> None:
        """Set callback for wake word detection."""
        self._on_wake_word_callback = callback

    def set_transcription_callback(
        self, callback: Callable[[Any, bool], Coroutine[Any, Any, None]]
    ) -> None:
        """Set callback for transcription results."""
        self._on_transcription_callback = callback

    def set_state_change_callback(
        self,
        callback: Callable[
            [TranscriptionState, TranscriptionState], Coroutine[Any, Any, None]
        ],
    ) -> None:
        """Set callback for state changes."""
        self._on_state_change_callback = callback

    async def force_start_transcription(self) -> None:
        """Manually start transcription (bypass wake word)."""
        await self._start_transcription()

    async def force_stop_transcription(self) -> None:
        """Manually stop transcription."""
        await self._stop_transcription()

    def get_status(self) -> Dict[str, Any]:
        """Get current service status."""
        return {
            "state": self.state.value,
            "is_running": self._is_running,
            "transcription_active": self._transcription_active,
            "wake_word_engine": (
                self.wake_word_engine.get_info() if self.wake_word_engine else None
            ),
            "microphone": self.microphone.get_info() if self.microphone else None,
            "transcription_service": (
                self.transcription_service.get_engine_info()
                if self.transcription_service
                else None
            ),
            "audio_buffer_size": len(self._audio_buffer),
            "transcription_duration": (
                time.time() - self._transcription_start_time
                if self._transcription_start_time
                else None
            ),
        }

    @staticmethod
    def check_dependencies() -> Dict[str, bool]:
        """Check if all required dependencies are available."""
        from ..wake_word import WakeWordEngine
        from ..audio.microphone_input import MicrophoneInput

        return {
            "wake_word": WakeWordEngine.is_available(),
            "microphone": MicrophoneInput.is_available(),
            "transcription": True,  # Should always be available with Whisper
        }

    async def _confirm_power_word_execution(
        self, command: str = "", command_type: str = "unknown"
    ) -> bool:
        """Enhanced confirmation callback for power word execution.

        This method implements multiple confirmation strategies:
        1. Voice confirmation (listening for "yes"/"no")
        2. Safety assessment based on command content
        3. Configurable timeout and retry logic

        Args:
            command: The command that will be executed
            command_type: Type of command (safe/dangerous/unknown)

        Returns:
            True to allow execution, False to deny
        """
        if not self.power_words_config.get("require_confirmation", True):
            # If confirmation is disabled, allow execution
            self.logger.info(
                f"Power word confirmation disabled, allowing command: {command}"
            )
            return True

        # Assess command safety
        safety_level = self._assess_command_safety(command)

        # Auto-deny dangerous commands unless explicitly allowed
        if safety_level == "dangerous":
            dangerous_keywords = self.power_words_config.get("dangerous_keywords", [])
            if any(
                keyword.lower() in command.lower() for keyword in dangerous_keywords
            ):
                self.logger.warning(f"Dangerous command auto-denied: {command}")
                return False

        # Auto-approve safe commands if configured
        if safety_level == "safe" and self.power_words_config.get(
            "auto_approve_safe", False
        ):
            self.logger.info(f"Safe command auto-approved: {command}")
            return True

        # Use voice confirmation for unknown or potentially dangerous commands
        confirmation_method = self.power_words_config.get(
            "confirmation_method", "voice"
        )

        if confirmation_method == "voice":
            return await self._voice_confirmation(command, safety_level)
        elif confirmation_method == "log_only":
            self.logger.info(f"Log-only mode: would execute command: {command}")
            return self.power_words_config.get("log_only_approve", False)
        else:
            # Default to deny for unknown confirmation methods
            self.logger.warning(
                f"Unknown confirmation method '{confirmation_method}', denying command: {command}"
            )
            return False

    def _assess_command_safety(self, command: str) -> str:
        """Assess the safety level of a command.

        Args:
            command: Command to assess

        Returns:
            "safe", "dangerous", or "unknown"
        """
        command_lower = command.lower()

        # Check for dangerous keywords
        dangerous_keywords = self.power_words_config.get(
            "dangerous_keywords",
            [
                "delete",
                "format",
                "sudo",
                "admin",
                "reboot",
                "shutdown",
                "rm -rf",
                "del /f",
                "format c:",
                "registry",
                "taskkill",
                "net user",
            ],
        )

        if any(keyword.lower() in command_lower for keyword in dangerous_keywords):
            return "dangerous"

        # Check for safe patterns (applications, websites, simple shortcuts)
        safe_patterns = [
            r"\.lnk$",  # Windows shortcuts
            r"^https?://",  # URLs
            r"explorer\.exe",  # File explorer
            r"notepad",  # Simple applications
            r"chrome\.exe",  # Browser
            r"start menu",  # Start menu navigation
        ]

        for pattern in safe_patterns:
            if re.search(pattern, command_lower):
                return "safe"

        # Check allowed commands list
        allowed_commands = self.power_words_config.get("allowed_commands", [])
        if any(allowed.lower() in command_lower for allowed in allowed_commands):
            return "safe"

        return "unknown"

    async def _voice_confirmation(self, command: str, safety_level: str) -> bool:
        """Handle voice-based confirmation for power word execution.

        Args:
            command: Command to confirm
            safety_level: Safety assessment of the command

        Returns:
            True if user confirms, False otherwise
        """
        timeout = self.power_words_config.get("confirmation_timeout", 10)
        max_retries = self.power_words_config.get("confirmation_retries", 2)

        self.logger.info(
            f"Requesting voice confirmation for {safety_level} command: {command}"
        )

        for attempt in range(max_retries + 1):
            try:
                # Instead of stopping/starting transcription, use a separate confirmation listener
                # This avoids recursive task cancellation issues
                confirmation_result = await self._listen_for_confirmation_safe(timeout)

                if confirmation_result is not None:
                    return confirmation_result

                # If we get here, no clear response was detected
                if attempt < max_retries:
                    self.logger.info(
                        f"No clear confirmation received, retrying ({attempt + 1}/{max_retries})"
                    )
                    await asyncio.sleep(1)
                else:
                    self.logger.warning(
                        "Maximum confirmation retries exceeded, denying command"
                    )
                    return False

            except Exception as e:
                self.logger.error(f"Error during voice confirmation: {e}")
                return False

        return False

    async def _listen_for_confirmation_safe(self, timeout: float) -> Optional[bool]:
        """Safe confirmation listener that doesn't interfere with main transcription.

        Args:
            timeout: Maximum time to wait for response

        Returns:
            True for "yes", False for "no", None for unclear/timeout
        """
        # Create a separate microphone instance for confirmation to avoid conflicts
        try:
            from ..audio.microphone_input import AsyncMicrophoneInput

            confirmation_mic = AsyncMicrophoneInput(self.microphone_config)

            confirmation_buffer = []
            start_time = time.time()

            def confirmation_audio_handler(audio_data: bytes) -> None:
                """Synchronous audio handler for confirmation."""
                confirmation_buffer.append(audio_data)

            await confirmation_mic.start_recording(confirmation_audio_handler)

            try:
                # Wait for timeout or sufficient audio
                while time.time() - start_time < timeout:
                    await asyncio.sleep(0.2)

                    # Process audio every 1-2 seconds
                    if len(confirmation_buffer) >= 8:  # Roughly 1.6 seconds of audio
                        audio_data = b"".join(confirmation_buffer)
                        confirmation_buffer.clear()

                        # Transcribe and check for yes/no
                        response = await self._transcribe_confirmation_audio(audio_data)
                        if response is not None:
                            return response

                # Process any remaining audio
                if confirmation_buffer:
                    audio_data = b"".join(confirmation_buffer)
                    response = await self._transcribe_confirmation_audio(audio_data)
                    return response

            finally:
                await confirmation_mic.stop_recording()

            return None

        except Exception as e:
            self.logger.error(f"Error in safe confirmation listener: {e}")
            return None

    async def _transcribe_confirmation_audio(self, audio_data: bytes) -> Optional[bool]:
        """Transcribe audio and check for confirmation keywords.

        Args:
            audio_data: Raw audio data

        Returns:
            True for affirmative, False for negative, None for unclear
        """
        if not audio_data or not self.transcription_service:
            return None

        try:
            # Create temporary WAV file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                self._write_wav_file(temp_file, audio_data)
                temp_path = temp_file.name

            try:
                # Transcribe the audio
                result = await self.transcription_service.transcribe_file(temp_path)
                text = result.text.lower().strip()

                if not text:
                    return None

                self.logger.info(f"Confirmation transcription: '{text}'")

                # Check for affirmative responses
                affirmative_keywords = [
                    "yes",
                    "yeah",
                    "yep",
                    "confirm",
                    "approve",
                    "ok",
                    "okay",
                    "sure",
                    "proceed",
                ]
                negative_keywords = [
                    "no",
                    "nope",
                    "cancel",
                    "deny",
                    "stop",
                    "abort",
                    "negative",
                ]

                # Check for clear affirmative
                if any(keyword in text for keyword in affirmative_keywords):
                    self.logger.info("Affirmative confirmation detected")
                    return True

                # Check for clear negative
                if any(keyword in text for keyword in negative_keywords):
                    self.logger.info("Negative confirmation detected")
                    return False

                # No clear response
                return None

            finally:
                # Clean up temp file
                try:
                    Path(temp_path).unlink()
                except Exception:
                    pass

        except Exception as e:
            self.logger.error(f"Error transcribing confirmation audio: {e}")
            return None

    async def _process_power_words(self, transcription_text: str) -> None:
        """Process transcription text for power words and execute commands.

        Args:
            transcription_text: The transcribed text to analyze
        """
        if not self.power_words_engine:
            return

        try:
            executed_count = await self.power_words_engine.process_transcription_async(
                transcription_text
            )
            if executed_count > 0:
                self.logger.info(f"Executed {executed_count} power word commands")
        except Exception as e:
            self.logger.error(f"Error processing power words: {e}")

    async def _process_power_words_and_extract_dictation(
        self, transcription_text: str
    ) -> str:
        """Process power words and return remaining text for dictation.

        Args:
            transcription_text: The transcribed text to analyze

        Returns:
            Remaining text after power word removal for dictation
        """
        if not self.power_words_engine:
            # No power words engine, return all text for dictation
            return transcription_text

        try:
            # Get the power words mappings to identify command phrases
            mappings = self.power_words_config.get("mappings", {})

            remaining_text = transcription_text
            executed_count = 0

            # Check each power word mapping
            for phrase, command in mappings.items():
                phrase_lower = phrase.lower()
                text_lower = remaining_text.lower()

                # Check if the power word phrase is in the text
                if phrase_lower in text_lower:
                    self.logger.info(f"Power word '{phrase}' detected in transcription")

                    # Execute the power word command
                    try:
                        result = await self.power_words_engine.execute_command_async(
                            command
                        )
                        if result:
                            executed_count += 1
                            self.logger.info(f"Executed power word command: {command}")

                            # Remove the power word phrase from the text
                            # Find the exact position and remove it
                            phrase_start = text_lower.find(phrase_lower)
                            if phrase_start >= 0:
                                # Remove the phrase and clean up extra spaces
                                before = remaining_text[:phrase_start]
                                after = remaining_text[phrase_start + len(phrase) :]
                                remaining_text = (before + " " + after).strip()
                                remaining_text = " ".join(
                                    remaining_text.split()
                                )  # Clean up multiple spaces
                        else:
                            self.logger.warning(
                                f"Power word command execution failed or denied: {command}"
                            )
                    except Exception as e:
                        self.logger.error(
                            f"Error executing power word command '{command}': {e}"
                        )

            if executed_count > 0:
                self.logger.info(
                    f"Executed {executed_count} power word commands, remaining text: '{remaining_text}'"
                )

            return remaining_text

        except Exception as e:
            self.logger.error(f"Error processing power words: {e}")
            # On error, return original text to ensure dictation continues
            return transcription_text

    def _check_for_stop_phrase(self, text: str) -> bool:
        """Check if transcription contains the stop phrase.

        Args:
            text: Transcription text to check

        Returns:
            True if stop phrase detected
        """
        return self._stop_phrase.lower() in text.lower()
