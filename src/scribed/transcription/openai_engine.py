"""OpenAI API transcription engine using Whisper API."""

import time
from pathlib import Path
from typing import List, Optional, Union

from .base import TranscriptionEngine, TranscriptionResult, TranscriptionSegment, TranscriptionStatus


class OpenAIEngine(TranscriptionEngine):
    """OpenAI API transcription engine using Whisper API."""
    
    def __init__(self, config: dict) -> None:
        """Initialize the OpenAI engine.
        
        Args:
            config: Configuration with keys:
                - api_key: OpenAI API key
                - model: Model name (whisper-1)
                - language: Language code (optional)
                - temperature: Temperature for sampling (0.0-1.0)
        """
        super().__init__(config)
        self.api_key = config.get("api_key")
        self.model = config.get("model", "whisper-1")
        self.language = config.get("language")
        self.temperature = config.get("temperature", 0.0)
        self._openai_available = self._check_openai_availability()
    
    def _check_openai_availability(self) -> bool:
        """Check if OpenAI library is available."""
        try:
            import openai
            return True
        except ImportError:
            self.logger.warning(
                "OpenAI library not available. Install with: pip install openai"
            )
            return False
    
    async def transcribe_file(self, audio_file_path: Union[str, Path]) -> TranscriptionResult:
        """Transcribe an audio file using OpenAI Whisper API.
        
        Args:
            audio_file_path: Path to the audio file
            
        Returns:
            TranscriptionResult with transcribed text
        """
        if not self.validate_audio_file(audio_file_path):
            return TranscriptionResult(
                text="",
                segments=[],
                status=TranscriptionStatus.FAILED,
                error="Invalid audio file"
            )
        
        if not self._openai_available:
            return TranscriptionResult(
                text="",
                segments=[],
                status=TranscriptionStatus.FAILED,
                error="OpenAI library not available"
            )
        
        if not self.api_key:
            return TranscriptionResult(
                text="",
                segments=[],
                status=TranscriptionStatus.FAILED,
                error="OpenAI API key not provided"
            )
        
        try:
            start_time = time.time()
            result = await self.run_sync_in_thread(
                self._transcribe_sync, str(audio_file_path)
            )
            processing_time = time.time() - start_time
            
            # OpenAI API doesn't return segments by default
            # We create a single segment for the entire text
            segments = [TranscriptionSegment(
                text=result["text"].strip(),
                start_time=0.0,
                end_time=0.0  # We don't have timing info from basic API
            )] if result["text"].strip() else []
            
            return TranscriptionResult(
                text=result["text"].strip(),
                segments=segments,
                language=result.get("language"),
                processing_time=processing_time,
                status=TranscriptionStatus.COMPLETED
            )
            
        except Exception as e:
            self.logger.error(f"OpenAI transcription failed: {e}")
            return TranscriptionResult(
                text="",
                segments=[],
                status=TranscriptionStatus.FAILED,
                error=str(e)
            )
    
    def _transcribe_sync(self, audio_file_path: str) -> dict:
        """Synchronous transcription method to run in thread pool."""
        import openai
        
        self.logger.info(f"Transcribing audio file with OpenAI: {audio_file_path}")
        
        # Set up the client
        client = openai.OpenAI(api_key=self.api_key)
        
        # Open and transcribe the audio file
        with open(audio_file_path, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(
                model=self.model,
                file=audio_file,
                language=self.language,
                temperature=self.temperature,
                response_format="json"
            )
        
        return {
            "text": transcript.text,
            "language": self.language
        }
    
    async def transcribe_stream(self, audio_data: bytes) -> TranscriptionResult:
        """Transcribe streaming audio data.
        
        Note: OpenAI API doesn't support streaming transcription directly.
        This would require saving the audio data to a temporary file.
        
        Args:
            audio_data: Raw audio data bytes
            
        Returns:
            TranscriptionResult
        """
        return TranscriptionResult(
            text="",
            segments=[],
            status=TranscriptionStatus.FAILED,
            error="Streaming transcription not supported by OpenAI API"
        )
    
    def get_supported_formats(self) -> List[str]:
        """Get supported audio formats for OpenAI Whisper API.
        
        Returns:
            List of supported file extensions
        """
        return [".mp3", ".mp4", ".mpeg", ".mpga", ".m4a", ".wav", ".webm", ".flac"]
    
    def is_available(self) -> bool:
        """Check if OpenAI API is available.
        
        Returns:
            True if OpenAI library is available and API key is provided
        """
        return self._openai_available and bool(self.api_key)
    
    def get_model_info(self) -> dict:
        """Get information about the current model.
        
        Returns:
            Dictionary with model information
        """
        return {
            "engine": "openai",
            "model": self.model,
            "language": self.language or "auto-detect",
            "temperature": self.temperature,
            "available": self.is_available(),
            "api_key_provided": bool(self.api_key)
        }
