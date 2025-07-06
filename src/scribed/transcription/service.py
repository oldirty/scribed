"""Transcription service that manages different transcription engines."""

import logging
from typing import Dict, List, Optional, Type, Union
from pathlib import Path

from .base import TranscriptionEngine, TranscriptionResult, TranscriptionStatus
from .whisper_engine import WhisperEngine
from .enhanced_whisper_engine import EnhancedWhisperEngine
from .openai_engine import OpenAIEngine
from .mock_engine import MockTranscriptionEngine


class TranscriptionService:
    """Service that manages and provides access to transcription engines."""

    # Registry of available engines
    ENGINES: Dict[str, Type[TranscriptionEngine]] = {
        "whisper": EnhancedWhisperEngine,  # Use enhanced engine by default
        "whisper_original": WhisperEngine,  # Keep original for fallback
        "openai": OpenAIEngine,
        "mock": MockTranscriptionEngine,  # For testing
    }

    def __init__(self, config: dict) -> None:
        """Initialize the transcription service.

        Args:
            config: Configuration dictionary with transcription settings
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.provider = config.get("provider", "whisper")
        self._engine: Optional[TranscriptionEngine] = None

        # Initialize the selected engine
        self._initialize_engine()

    def _initialize_engine(self) -> None:
        """Initialize the selected transcription engine."""
        if self.provider not in self.ENGINES:
            self.logger.error(f"Unknown transcription provider: {self.provider}")
            self.logger.info(f"Available providers: {list(self.ENGINES.keys())}")
            return

        try:
            engine_class = self.ENGINES[self.provider]
            engine_config = self._get_engine_config()
            self._engine = engine_class(engine_config)

            if self._engine.is_available():
                self.logger.info(
                    f"Transcription engine '{self.provider}' initialized successfully"
                )
            else:
                self.logger.warning(
                    f"Transcription engine '{self.provider}' is not available"
                )

        except Exception as e:
            self.logger.error(
                f"Failed to initialize transcription engine '{self.provider}': {e}"
            )
            self._engine = None

    def _get_engine_config(self) -> dict:
        """Get configuration for the current engine."""
        base_config = {
            "language": self.config.get("language", "en"),
            "model": self.config.get("model", "base"),
        }

        if self.provider == "openai":
            base_config.update(
                {
                    "api_key": self.config.get("api_key"),
                    "temperature": self.config.get("temperature", 0.0),
                }
            )
        elif self.provider == "whisper":
            base_config.update(
                {
                    "device": self.config.get("device", "auto"),
                }
            )

        return base_config

    async def transcribe_file(
        self, audio_file_path: Union[str, Path]
    ) -> TranscriptionResult:
        """Transcribe an audio file.

        Args:
            audio_file_path: Path to the audio file

        Returns:
            TranscriptionResult with transcribed text and metadata
        """
        if not self._engine:
            return TranscriptionResult(
                text="",
                segments=[],
                status=TranscriptionStatus.FAILED,
                error="No transcription engine available",
            )

        if not self._engine.is_available():
            return TranscriptionResult(
                text="",
                segments=[],
                status=TranscriptionStatus.FAILED,
                error=f"Transcription engine '{self.provider}' is not available",
            )

        self.logger.info(f"Transcribing file: {audio_file_path}")
        result = await self._engine.transcribe_file(audio_file_path)

        if result.status == TranscriptionStatus.COMPLETED:
            self.logger.info(
                f"Transcription completed in {result.processing_time:.2f}s"
            )
        else:
            self.logger.error(f"Transcription failed: {result.error}")

        return result

    async def transcribe_stream(self, audio_data: bytes) -> TranscriptionResult:
        """Transcribe streaming audio data.

        Args:
            audio_data: Raw audio data bytes

        Returns:
            TranscriptionResult with transcribed text and metadata
        """
        if not self._engine:
            return TranscriptionResult(
                text="",
                segments=[],
                status=TranscriptionStatus.FAILED,
                error="No transcription engine available",
            )

        return await self._engine.transcribe_stream(audio_data)

    def get_supported_formats(self) -> List[str]:
        """Get supported audio formats.

        Returns:
            List of supported file extensions
        """
        if not self._engine:
            return []
        return self._engine.get_supported_formats()

    def is_available(self) -> bool:
        """Check if transcription service is available.

        Returns:
            True if a transcription engine is available and ready
        """
        return self._engine is not None and self._engine.is_available()

    def get_engine_info(self) -> dict:
        """Get information about the current transcription engine.

        Returns:
            Dictionary with engine information
        """
        if not self._engine:
            return {
                "provider": self.provider,
                "available": False,
                "error": "Engine not initialized",
            }

        info = {
            "provider": self.provider,
            "available": self._engine.is_available(),
            "supported_formats": self._engine.get_supported_formats(),
        }

        # Add engine-specific info if available
        if hasattr(self._engine, "get_model_info"):
            info.update(self._engine.get_model_info())

        return info

    def switch_provider(
        self, provider: str, config_override: Optional[dict] = None
    ) -> bool:
        """Switch to a different transcription provider.

        Args:
            provider: Name of the provider to switch to
            config_override: Optional configuration overrides

        Returns:
            True if the switch was successful
        """
        if provider not in self.ENGINES:
            self.logger.error(f"Unknown provider: {provider}")
            return False

        old_provider = self.provider
        self.provider = provider

        # Update config if overrides provided
        if config_override:
            self.config.update(config_override)

        # Reinitialize engine
        self._initialize_engine()

        if self.is_available():
            self.logger.info(
                f"Successfully switched from '{old_provider}' to '{provider}'"
            )
            return True
        else:
            self.logger.error(
                f"Failed to switch to '{provider}', reverting to '{old_provider}'"
            )
            self.provider = old_provider
            self._initialize_engine()
            return False

    @classmethod
    def get_available_providers(cls) -> List[str]:
        """Get list of available transcription providers.

        Returns:
            List of provider names
        """
        return list(cls.ENGINES.keys())
