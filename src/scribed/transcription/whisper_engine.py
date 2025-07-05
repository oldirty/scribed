"""Local Whisper transcription engine using openai-whisper."""

import time
from pathlib import Path
from typing import List, Optional, Union

from .base import (
    TranscriptionEngine,
    TranscriptionResult,
    TranscriptionSegment,
    TranscriptionStatus,
)


class WhisperEngine(TranscriptionEngine):
    """Local Whisper transcription engine using openai-whisper."""

    def __init__(self, config: dict) -> None:
        """Initialize the Whisper engine.

        Args:
            config: Configuration with keys:
                - model: Whisper model name (tiny, base, small, medium, large)
                - language: Language code (optional, auto-detect if None)
                - device: Device to use (cpu, cuda, auto)
        """
        super().__init__(config)
        self.model_name = config.get("model", "base")
        self.language = config.get("language")
        self.device = config.get("device", "auto")
        self._model = None
        self._whisper_available = self._check_whisper_availability()

    def _check_whisper_availability(self) -> bool:
        """Check if whisper is available."""
        try:
            import whisper

            return True
        except ImportError:
            self.logger.warning(
                "OpenAI Whisper not available. Install with: pip install openai-whisper"
            )
            return False

    def _load_model(self):
        """Load the Whisper model if not already loaded."""
        if self._model is None and self._whisper_available:
            try:
                import whisper
                import torch

                self.logger.info(f"Loading Whisper model: {self.model_name}")

                # Try to handle model loading with download fallback
                try:
                    # First try normal loading
                    self._model = whisper.load_model(
                        self.model_name, device=self.device
                    )
                except Exception as load_error:
                    self.logger.warning(f"Model loading failed: {load_error}")
                    self.logger.info("Attempting to re-download the model...")

                    # Clear any cached models that might be corrupted
                    import os

                    cache_dir = os.path.expanduser("~/.cache/whisper")
                    model_file = f"{self.model_name}.pt"
                    model_path = os.path.join(cache_dir, model_file)

                    if os.path.exists(model_path):
                        self.logger.info(
                            f"Removing potentially corrupted model: {model_path}"
                        )
                        try:
                            os.remove(model_path)
                        except OSError as e:
                            self.logger.warning(f"Could not remove cached model: {e}")

                    # Force re-download by downloading directly
                    self._model = whisper.load_model(
                        self.model_name, device=self.device, download_root=cache_dir
                    )

                self.logger.info(f"Whisper model loaded successfully on {self.device}")

            except Exception as e:
                self.logger.error(f"Failed to load Whisper model: {e}")
                self.logger.error("This may be due to a PyTorch compatibility issue.")
                self.logger.error(
                    "Try clearing the Whisper cache: rm -rf ~/.cache/whisper"
                )
                raise

    async def transcribe_file(
        self, audio_file_path: Union[str, Path]
    ) -> TranscriptionResult:
        """Transcribe an audio file using Whisper.

        Args:
            audio_file_path: Path to the audio file

        Returns:
            TranscriptionResult with transcribed text and segments
        """
        if not self.validate_audio_file(audio_file_path):
            return TranscriptionResult(
                text="",
                segments=[],
                status=TranscriptionStatus.FAILED,
                error="Invalid audio file",
            )

        if not self._whisper_available:
            return TranscriptionResult(
                text="",
                segments=[],
                status=TranscriptionStatus.FAILED,
                error="Whisper not available",
            )

        try:
            # Load model in thread pool to avoid blocking
            await self.run_sync_in_thread(self._load_model)

            # Run transcription in thread pool
            start_time = time.time()
            result = await self.run_sync_in_thread(
                self._transcribe_sync, str(audio_file_path)
            )
            processing_time = time.time() - start_time

            # Convert Whisper result to our format
            segments = []
            if "segments" in result:
                for segment in result["segments"]:
                    segments.append(
                        TranscriptionSegment(
                            text=segment["text"].strip(),
                            start_time=segment["start"],
                            end_time=segment["end"],
                            confidence=segment.get("avg_logprob"),
                        )
                    )

            return TranscriptionResult(
                text=result["text"].strip(),
                segments=segments,
                language=result.get("language"),
                processing_time=processing_time,
                status=TranscriptionStatus.COMPLETED,
            )

        except Exception as e:
            self.logger.error(f"Whisper transcription failed: {e}")
            return TranscriptionResult(
                text="", segments=[], status=TranscriptionStatus.FAILED, error=str(e)
            )

    def _transcribe_sync(self, audio_file_path: str) -> dict:
        """Synchronous transcription method to run in thread pool."""
        self.logger.info(f"Transcribing audio file: {audio_file_path}")

        if self._model is None:
            raise RuntimeError("Model not loaded. Call _load_model() first.")

        # Transcribe with segments for timing information
        result = self._model.transcribe(
            audio_file_path,
            language=self.language,
            verbose=False,
            word_timestamps=False,
        )

        return result

    async def transcribe_stream(self, audio_data: bytes) -> TranscriptionResult:
        """Transcribe streaming audio data.

        Note: This is a placeholder implementation. Real streaming transcription
        would require more sophisticated audio buffering and processing.

        Args:
            audio_data: Raw audio data bytes

        Returns:
            TranscriptionResult
        """
        # For now, return a not implemented error
        return TranscriptionResult(
            text="",
            segments=[],
            status=TranscriptionStatus.FAILED,
            error="Streaming transcription not yet implemented for Whisper",
        )

    def get_supported_formats(self) -> List[str]:
        """Get supported audio formats for Whisper.

        Returns:
            List of supported file extensions
        """
        return [".wav", ".mp3", ".mp4", ".mpeg", ".mpga", ".m4a", ".webm", ".flac"]

    def is_available(self) -> bool:
        """Check if Whisper is available.

        Returns:
            True if Whisper is available and model can be loaded
        """
        if not self._whisper_available:
            return False

        try:
            # Try to load the model to verify it's available
            if self._model is None:
                import whisper

                # Just check if the model exists without fully loading it
                available_models = whisper.available_models()
                return self.model_name in available_models
            return True
        except Exception as e:
            self.logger.error(f"Whisper availability check failed: {e}")
            return False

    def get_model_info(self) -> dict:
        """Get information about the current model.

        Returns:
            Dictionary with model information
        """
        return {
            "engine": "whisper",
            "model": self.model_name,
            "language": self.language or "auto-detect",
            "device": self.device,
            "available": self.is_available(),
        }
