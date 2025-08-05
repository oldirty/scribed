"""Simplified core engine for Scribed audio transcription service."""

import asyncio
import logging
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

from ..config import Config
from ..transcription.service import TranscriptionService


class EngineStatus(Enum):
    """Engine status enumeration."""

    IDLE = "idle"
    RUNNING = "running"
    ERROR = "error"


class ScribedEngine:
    """
    Simplified core engine for Scribed transcription service.

    Handles transcription requests directly without complex session management.
    """

    def __init__(self, config: Optional[Config] = None) -> None:
        """Initialize the ScribedEngine."""
        self.config = config or Config.from_env()
        self.status = EngineStatus.IDLE
        self.logger = self._setup_logging()

        # Core components
        self.transcription_service: Optional[TranscriptionService] = None

        # Simple state tracking
        self._is_running = False
        self._shutdown_event = asyncio.Event()

        self.logger.info("Scribed engine initialized")

    def _setup_logging(self) -> logging.Logger:
        """Set up logging for the engine."""
        logger = logging.getLogger(__name__)

        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)  # Default logging level

        return logger

    async def start(self) -> None:
        """Start the engine and initialize components."""
        if self._is_running:
            self.logger.warning("Engine already running")
            return

        try:
            self.logger.info("Starting Scribed engine...")
            self.status = EngineStatus.RUNNING

            # Initialize transcription service
            self.transcription_service = TranscriptionService(
                self.config.transcription.model_dump()
            )

            self._is_running = True
            self.logger.info("Scribed engine started successfully")

        except Exception as e:
            self.logger.error(f"Failed to start engine: {e}")
            self.status = EngineStatus.ERROR
            raise

    async def stop(self) -> None:
        """Stop the engine and cleanup components."""
        if not self._is_running:
            return

        self.logger.info("Stopping Scribed engine...")
        self._is_running = False
        self.status = EngineStatus.IDLE

        # Cleanup transcription service
        if self.transcription_service:
            # TranscriptionService doesn't need explicit cleanup in current implementation
            self.transcription_service = None

        self._shutdown_event.set()
        self.logger.info("Scribed engine stopped")

    def shutdown(self) -> None:
        """Signal shutdown (for signal handlers)."""
        self._shutdown_event.set()

    async def wait_for_shutdown(self) -> None:
        """Wait for shutdown signal."""
        await self._shutdown_event.wait()

    async def transcribe_file(self, file_path: Path) -> Any:
        """
        Transcribe a single audio file.

        Args:
            file_path: Path to the audio file

        Returns:
            Transcription result
        """
        if not self._is_running or not self.transcription_service:
            raise RuntimeError("Engine not running or not properly initialized")

        self.logger.info(f"Transcribing file: {file_path}")

        try:
            result = await self.transcription_service.transcribe_file(file_path)
            self.logger.info(f"Transcription completed: {len(result.text)} characters")
            return result

        except Exception as e:
            self.logger.error(f"Transcription failed: {e}")
            raise

    def get_status(self) -> Dict[str, Any]:
        """Get engine status information."""
        return {
            "status": self.status.value,
            "running": self._is_running,
            "active_sessions": 0,  # Simplified - no session tracking
            "config": {
                "source_mode": self.config.source_mode,
                "transcription_provider": self.config.transcription.provider,
                "output_format": self.config.output.format,
            },
            "transcription": (
                {
                    "provider": self.config.transcription.provider,
                    "available": self.transcription_service is not None,
                }
                if self.transcription_service
                else {}
            ),
        }

    def is_healthy(self) -> bool:
        """Check if engine is healthy."""
        return (
            self._is_running
            and self.status == EngineStatus.RUNNING
            and self.transcription_service is not None
        )

    # Legacy compatibility methods for existing code
    def create_session(self, session_type: str) -> str:
        """Create a fake session ID for compatibility."""
        return "simple_session"

    def get_session(self, session_id: str) -> Optional[Any]:
        """Get a fake session object for compatibility."""
        if session_id == "simple_session" and self.transcription_service:
            # Return a simple object that provides transcription_service access
            class SimpleSession:
                def __init__(self, transcription_service):
                    self.transcription_service = transcription_service

            return SimpleSession(self.transcription_service)
        return None

    def remove_session(self, session_id: str) -> bool:
        """Remove session (no-op for compatibility)."""
        return True

    def get_active_sessions(self) -> Dict[str, Any]:
        """Get active sessions (empty for simplified version)."""
        return {}
