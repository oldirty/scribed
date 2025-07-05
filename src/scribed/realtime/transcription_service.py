"""Real-time transcription service with wake word and power words integration."""

import asyncio
import logging
import tempfile
import time
from pathlib import Path
from typing import Optional, Callable, Dict, Any, Awaitable, Coroutine
from enum import Enum

from ..transcription.service import TranscriptionService
from ..wake_word import AsyncWakeWordEngine, WakeWordDetectionError
from ..audio.microphone_input import AsyncMicrophoneInput, AudioInputError
from ..power_words import AsyncPowerWordsEngine, PowerWordsSecurityError


class TranscriptionState(Enum):
    """States of the real-time transcription system."""
    IDLE = "idle"
    LISTENING_FOR_WAKE_WORD = "listening_for_wake_word"
    ACTIVE_TRANSCRIPTION = "active_transcription"
    PROCESSING = "processing"
    ERROR = "error"


class RealTimeTranscriptionService:
    """Real-time transcription service with wake word activation and power words."""
    
    def __init__(self, wake_word_config: dict, microphone_config: dict, transcription_config: dict, power_words_config: Optional[dict] = None):
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
        self.wake_word_engine: Optional[AsyncWakeWordEngine] = None
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
        self._audio_buffer = []
        self._transcription_start_time = None
        
        # Callbacks
        self._on_wake_word_callback = None
        self._on_transcription_callback = None
        self._on_state_change_callback = None
        
        self.logger.info("Real-time transcription service initialized")
    
    def _initialize_components(self) -> None:
        """Initialize all service components."""
        try:
            # Initialize wake word engine
            if not self.wake_word_engine:
                self.wake_word_engine = AsyncWakeWordEngine(self.wake_word_config)
                self.logger.info("Wake word engine initialized")
            
            # Initialize microphone
            if not self.microphone:
                self.microphone = AsyncMicrophoneInput(self.microphone_config)
                self.logger.info("Microphone input initialized")
            
            # Initialize transcription service
            if not self.transcription_service:
                self.transcription_service = TranscriptionService(self.transcription_config)
                self.logger.info("Transcription service initialized")
            
            # Initialize power words engine if configured
            if self.power_words_config and self.power_words_config.get("enabled", False):
                if not self.power_words_engine:
                    from ..config import PowerWordsConfig
                    power_config = PowerWordsConfig(**self.power_words_config)
                    self.power_words_engine = AsyncPowerWordsEngine(power_config)
                    self.power_words_engine.set_confirmation_callback(self._confirm_power_word_execution)
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
    
    async def _on_wake_word_detected(self, keyword_index: int, keyword_name: str) -> None:
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
            
            # Start silence timeout task
            asyncio.create_task(self._silence_timeout_task())
            
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
        
        # Stop microphone
        if self.microphone:
            await self.microphone.stop_recording()
        
        # Process accumulated audio
        if self._audio_buffer:
            await self._process_final_audio()
        
        # Clear buffer
        self._audio_buffer = []
        
        # Return to wake word listening
        self._set_state(TranscriptionState.LISTENING_FOR_WAKE_WORD)
        
        self.logger.info("Active transcription stopped")
    
    def _on_audio_data_sync(self, audio_data: bytes) -> None:
        """Synchronous wrapper for audio data callback."""
        # Create a task to handle the async audio processing
        try:
            asyncio.create_task(self._on_audio_data(audio_data))
        except RuntimeError:
            # If no event loop is running, we can't process async
            self.logger.warning("No event loop available for audio processing")
    
    async def _on_audio_data(self, audio_data: bytes) -> None:
        """Handle incoming audio data during active transcription."""
        if not self._transcription_active:
            return
        
        # Add to buffer
        self._audio_buffer.append(audio_data)
        
        # Process in chunks for near real-time feedback
        buffer_duration = len(self._audio_buffer) * self.microphone_config.get("chunk_size", 1024) / self.microphone_config.get("sample_rate", 16000)
        
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
                    # Check for stop phrase
                    if self._check_for_stop_phrase(result.text):
                        self.logger.info("Stop phrase detected")
                        await self._stop_transcription()
                        return
                    
                    # Process power words for partial transcription
                    await self._process_power_words(result.text)
                    
                    # Notify callback with partial transcription
                    if self._on_transcription_callback:
                        try:
                            await self._on_transcription_callback(result, True)
                        except Exception as e:
                            self.logger.error(f"Error in transcription callback: {e}")
                
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
                    self.logger.error("Transcription service not initialized for final processing")
                    return
                    
                result = await self.transcription_service.transcribe_file(temp_path)
                
                # Process power words for final transcription
                if result.text.strip():
                    await self._process_power_words(result.text)
                
                # Notify callback with final transcription
                if self._on_transcription_callback:
                    try:
                        await self._on_transcription_callback(result, False)
                    except Exception as e:
                        self.logger.error(f"Error in final transcription callback: {e}")
                
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
        with wave.open(file.name, 'wb') as wav_file:
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
                    asyncio.create_task(self._on_state_change_callback(old_state, new_state))
                except Exception as e:
                    self.logger.error(f"Error scheduling state change callback: {e}")
    
    # Public API methods
    
    def set_wake_word_callback(self, callback: Callable[[int, str], None]) -> None:
        """Set callback for wake word detection."""
        self._on_wake_word_callback = callback
    
    def set_transcription_callback(self, callback: Callable[[Any, bool], Coroutine[Any, Any, None]]) -> None:
        """Set callback for transcription results."""
        self._on_transcription_callback = callback
    
    def set_state_change_callback(self, callback: Callable[[TranscriptionState, TranscriptionState], Coroutine[Any, Any, None]]) -> None:
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
            "wake_word_engine": self.wake_word_engine.get_info() if self.wake_word_engine else None,
            "microphone": self.microphone.get_info() if self.microphone else None,
            "transcription_service": self.transcription_service.get_engine_info() if self.transcription_service else None,
            "audio_buffer_size": len(self._audio_buffer),
            "transcription_duration": time.time() - self._transcription_start_time if self._transcription_start_time else None,
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
    
    async def _confirm_power_word_execution(self) -> bool:
        """Confirmation callback for power word execution.
        
        In a real implementation, this would show a UI prompt or use voice confirmation.
        For now, we'll auto-approve safe commands and log dangerous ones.
        
        Returns:
            True to allow execution, False to deny
        """
        # For safety, we'll require explicit confirmation for power words
        # In a full implementation, this could be a voice prompt, GUI dialog, etc.
        self.logger.warning("Power word execution requires confirmation - auto-denying for safety")
        return False  # Deny by default for security
    
    async def _process_power_words(self, transcription_text: str) -> None:
        """Process transcription text for power words and execute commands.
        
        Args:
            transcription_text: The transcribed text to analyze
        """
        if not self.power_words_engine:
            return
        
        try:
            executed_count = await self.power_words_engine.process_transcription_async(transcription_text)
            if executed_count > 0:
                self.logger.info(f"Executed {executed_count} power word commands")
        except Exception as e:
            self.logger.error(f"Error processing power words: {e}")
    
    def _check_for_stop_phrase(self, text: str) -> bool:
        """Check if transcription contains the stop phrase.
        
        Args:
            text: Transcription text to check
            
        Returns:
            True if stop phrase detected
        """
        return self._stop_phrase.lower() in text.lower()
