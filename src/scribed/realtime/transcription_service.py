"""Simplified real-time transcription service focused on core functionality."""

import asyncio
import logging
import time
from enum import Enum
from typing import Optional, Callable, Dict, Any, Awaitable, List

from ..transcription.service import TranscriptionService
from ..wake_word import AsyncWakeWordEngine, WakeWordDetectionError
from ..audio.microphone import AsyncMicrophoneInput, AudioInputError
from ..power_words import AsyncPowerWordsEngine, PowerWordsSecurityError


class TranscriptionState(Enum):
    """States of the real-time transcription system."""

    IDLE = "idle"
    LISTENING_FOR_WAKE_WORD = "listening_for_wake_word"
    ACTIVE_TRANSCRIPTION = "active_transcription"
    ERROR = "error"


class RealTimeTranscriptionService:
    """Simplified real-time transcription service with wake word activation."""

    def __init__(
        self,
        wake_word_config: dict,
        microphone_config: dict,
        transcription_config: dict,
        power_words_config: Optional[dict] = None,
    ):
        """Initialize the real-time transcription service."""
        self.logger = logging.getLogger(__name__)

        # Configuration
        self.wake_word_config = wake_word_config
        self.microphone_config = microphone_config
        self.transcription_config = transcription_config
        self.power_words_config = power_words_config or {}

        # Components
        self.wake_word_engine: Optional[AsyncWakeWordEngine] = None
        self.microphone: Optional[AsyncMicrophoneInput] = None
        self.transcription_service: Optional[TranscriptionService] = None
        self.power_words_engine: Optional[AsyncPowerWordsEngine] = None

        # State
        self.state = TranscriptionState.IDLE
        self._is_running = False
        self._transcription_active = False

        # Audio processing
        self._audio_buffer: List[bytes] = []
        self._audio_queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=50)
        self._processor_task: Optional[asyncio.Task] = None

        # Timeouts
        self._silence_timeout = wake_word_config.get("silence_timeout", 15)
        self._silence_task: Optional[asyncio.Task] = None

        # Callbacks
        self._on_wake_word_callback: Optional[Callable[[int, str], None]] = None
        self._on_transcription_callback: Optional[Callable] = None
        self._on_state_change_callback: Optional[Callable] = None

        self.logger.info("Real-time transcription service initialized")

    def _initialize_components(self) -> None:
        """Initialize service components."""
        try:
            # Initialize wake word engine
            if not self.wake_word_engine:
                from ..wake_word import create_wake_word_engine

                self.wake_word_engine = create_wake_word_engine(self.wake_word_config)

            # Initialize microphone
            if not self.microphone:
                self.microphone = AsyncMicrophoneInput(self.microphone_config)

            # Initialize transcription service
            if not self.transcription_service:
                self.transcription_service = TranscriptionService(
                    self.transcription_config
                )

            # Initialize power words engine if configured
            if (
                self.power_words_config.get("enabled", False)
                and not self.power_words_engine
            ):
                self.power_words_engine = AsyncPowerWordsEngine(self.power_words_config)

            self.logger.info("All components initialized successfully")

        except Exception as e:
            self.logger.error(f"Failed to initialize components: {e}")
            raise

    async def start_service(self) -> None:
        """Start the real-time transcription service."""
        if self._is_running:
            self.logger.warning("Service already running")
            return

        try:
            self._initialize_components()

            # Start wake word engine
            if self.wake_word_engine:
                self.wake_word_engine.set_callback(self._on_wake_word_detected)
                await self.wake_word_engine.start()

            # Start audio processor
            self._processor_task = asyncio.create_task(self._audio_processor())

            # Start microphone
            if self.microphone:
                await self.microphone.start_recording(self._on_audio_data)

            self._is_running = True
            self._set_state(TranscriptionState.LISTENING_FOR_WAKE_WORD)
            self.logger.info("Real-time transcription service started")

        except Exception as e:
            self.logger.error(f"Failed to start service: {e}")
            await self.stop_service()
            raise

    async def stop_service(self) -> None:
        """Stop the real-time transcription service."""
        if not self._is_running:
            return

        self._is_running = False
        self.logger.info("Stopping real-time transcription service...")

        # Stop microphone
        if self.microphone:
            await self.microphone.stop_recording()

        # Stop wake word engine
        if self.wake_word_engine:
            await self.wake_word_engine.stop()

        # Stop processor task
        if self._processor_task:
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                pass

        # Stop silence timeout
        if self._silence_task:
            self._silence_task.cancel()
            try:
                await self._silence_task
            except asyncio.CancelledError:
                pass

        self._set_state(TranscriptionState.IDLE)
        self.logger.info("Real-time transcription service stopped")

    async def _on_wake_word_detected(
        self, wake_word_index: int, wake_word: str
    ) -> None:
        """Handle wake word detection."""
        self.logger.info(
            f"Wake word detected: '{wake_word}' (index: {wake_word_index})"
        )

        if self._on_wake_word_callback:
            self._on_wake_word_callback(wake_word_index, wake_word)

        await self._start_transcription()

    async def _start_transcription(self) -> None:
        """Start active transcription."""
        if self._transcription_active:
            return

        self.logger.info("Starting active transcription")
        self._transcription_active = True
        self._audio_buffer = []
        self._set_state(TranscriptionState.ACTIVE_TRANSCRIPTION)

        # Start silence timeout
        self._silence_task = asyncio.create_task(self._silence_timeout_task())

    async def _stop_transcription(self) -> None:
        """Stop active transcription."""
        if not self._transcription_active:
            return

        self.logger.info("Stopping active transcription")
        self._transcription_active = False

        # Cancel silence timeout
        if self._silence_task:
            self._silence_task.cancel()
            try:
                await self._silence_task
            except asyncio.CancelledError:
                pass

        # Process final audio
        await self._process_final_audio()
        self._set_state(TranscriptionState.LISTENING_FOR_WAKE_WORD)

    async def _on_audio_data(self, audio_data: bytes) -> None:
        """Handle incoming audio data."""
        try:
            await self._audio_queue.put(audio_data)
        except asyncio.QueueFull:
            self.logger.warning("Audio queue full, dropping audio data")

    async def _audio_processor(self) -> None:
        """Process audio data from queue."""
        while self._is_running:
            try:
                audio_data = await asyncio.wait_for(
                    self._audio_queue.get(), timeout=1.0
                )

                # Send to wake word engine
                if (
                    self.wake_word_engine
                    and self.state == TranscriptionState.LISTENING_FOR_WAKE_WORD
                ):
                    self.wake_word_engine.process_audio_data(audio_data)

                # Buffer audio during transcription
                if self._transcription_active:
                    self._audio_buffer.append(audio_data)

                    # Process chunks periodically
                    if (
                        len(self._audio_buffer) >= 10
                    ):  # Process every ~0.64 seconds at 1024 chunk size
                        await self._process_audio_chunk()

            except asyncio.TimeoutError:
                continue
            except Exception as e:
                self.logger.error(f"Error in audio processor: {e}")

    async def _process_audio_chunk(self) -> None:
        """Process current audio buffer for transcription."""
        if not self._audio_buffer or not self.transcription_service:
            return

        try:
            # Create temporary audio file
            import tempfile
            import wave

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                # Write audio data to WAV file
                with wave.open(temp_file.name, "wb") as wav_file:
                    wav_file.setnchannels(self.microphone_config.get("channels", 1))
                    wav_file.setsampwidth(2)  # 16-bit
                    wav_file.setframerate(
                        self.microphone_config.get("sample_rate", 16000)
                    )
                    wav_file.writeframes(b"".join(self._audio_buffer))

                # Transcribe audio
                result = await self.transcription_service.transcribe_file(
                    temp_file.name
                )

                if result.text.strip():
                    self.logger.info(f"Transcription chunk: {result.text}")

                    # Check for stop phrase
                    if self._check_for_stop_phrase(result.text):
                        await self._stop_transcription()
                        return

                    # Process power words if enabled
                    if self.power_words_engine:
                        await self._process_power_words(result.text)

                    # Call transcription callback
                    if self._on_transcription_callback:
                        await self._on_transcription_callback(result, False)

                # Clear processed audio
                self._audio_buffer = []

        except Exception as e:
            self.logger.error(f"Error processing audio chunk: {e}")

    async def _process_final_audio(self) -> None:
        """Process remaining audio when transcription stops."""
        if not self._audio_buffer:
            return

        try:
            await self._process_audio_chunk()

            if self._on_transcription_callback:
                # Signal end of transcription
                await self._on_transcription_callback(None, True)

        except Exception as e:
            self.logger.error(f"Error processing final audio: {e}")

    async def _process_power_words(self, transcription_text: str) -> None:
        """Process power words in transcription."""
        if not self.power_words_engine:
            return

        try:
            matches = await self.power_words_engine.find_matches(transcription_text)
            for match in matches:
                # Execute power word command directly (simplified - no voice confirmation)
                await self.power_words_engine.execute_command(match)

        except PowerWordsSecurityError as e:
            self.logger.warning(f"Power words security error: {e}")
        except Exception as e:
            self.logger.error(f"Error processing power words: {e}")

    async def _silence_timeout_task(self) -> None:
        """Handle silence timeout during transcription."""
        try:
            await asyncio.sleep(self._silence_timeout)
            self.logger.info("Silence timeout reached, stopping transcription")
            await self._stop_transcription()
        except asyncio.CancelledError:
            pass

    def _check_for_stop_phrase(self, text: str) -> bool:
        """Check if text contains stop phrase."""
        stop_phrase = self.wake_word_config.get("stop_phrase", "stop listening")
        return stop_phrase.lower() in text.lower()

    def _set_state(self, new_state: TranscriptionState) -> None:
        """Set new state and trigger callback."""
        old_state = self.state
        self.state = new_state
        self.logger.debug(f"State changed: {old_state.value} -> {new_state.value}")

        if self._on_state_change_callback:
            asyncio.create_task(self._on_state_change_callback(old_state, new_state))

    # Callback setters
    def set_wake_word_callback(self, callback: Callable[[int, str], None]) -> None:
        self._on_wake_word_callback = callback

    def set_transcription_callback(self, callback: Callable) -> None:
        self._on_transcription_callback = callback

    def set_state_change_callback(self, callback: Callable) -> None:
        self._on_state_change_callback = callback

    # Status and control methods
    def get_status(self) -> Dict[str, Any]:
        """Get service status."""
        return {
            "running": self._is_running,
            "state": self.state.value,
            "transcription_active": self._transcription_active,
            "audio_buffer_size": len(self._audio_buffer),
            "components": {
                "wake_word_engine": self.wake_word_engine is not None,
                "microphone": self.microphone is not None,
                "transcription_service": self.transcription_service is not None,
                "power_words_engine": self.power_words_engine is not None,
            },
        }

    async def force_start_transcription(self) -> None:
        """Force start transcription (for testing/debugging)."""
        await self._start_transcription()

    async def force_stop_transcription(self) -> None:
        """Force stop transcription (for testing/debugging)."""
        await self._stop_transcription()

    @staticmethod
    def check_dependencies() -> Dict[str, bool]:
        """Check if all required dependencies are available."""
        from ..wake_word import WakeWordEngine
        from ..audio.microphone import MicrophoneInput

        return {
            "wake_word": WakeWordEngine.is_available(),
            "microphone": MicrophoneInput.is_available(),
        }
