"""Main daemon logic for Scribed."""

import asyncio
import logging
import signal
from pathlib import Path
from typing import Optional, Any
from enum import Enum

from .config import Config
from .api.server import APIServer
from .audio.file_watcher import FileWatcher
from .transcription.service import TranscriptionService
from .realtime.transcription_service import (
    RealTimeTranscriptionService,
    TranscriptionState,
)


class DaemonStatus(Enum):
    """Daemon status enumeration."""

    IDLE = "idle"
    LISTENING_FOR_WAKE_WORD = "listening_for_wake_word"
    TRANSCRIBING = "transcribing"
    PROCESSING_BATCH = "processing_batch"
    ERROR = "error"
    DISABLED = "disabled"


class ScribedDaemon:
    """Main daemon class for Scribed audio transcription service."""

    def __init__(self, config: Optional[Config] = None) -> None:
        """Initialize the daemon with configuration."""
        self.config = config or Config.from_env()
        self.status = DaemonStatus.DISABLED
        self.logger = self._setup_logging()

        # Core components
        self.api_server: Optional[APIServer] = None
        self.file_watcher: Optional[FileWatcher] = None
        self.transcription_service: Optional[TranscriptionService] = None
        self.realtime_service: Optional[RealTimeTranscriptionService] = None

        # State management
        self._shutdown_event = asyncio.Event()
        self._running = False

        # Initialize transcription service
        self._initialize_transcription_service()

    def _setup_logging(self) -> logging.Logger:
        """Set up logging for the daemon."""
        logger = logging.getLogger("scribed")
        logger.setLevel(logging.INFO)

        # Create console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)

        # Create file handler if enabled
        if self.config.output.log_to_file:
            log_path = Path(self.config.output.log_file_path)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(log_path)
            file_handler.setLevel(logging.DEBUG)

            # Add file handler
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

        # Add console handler
        console_formatter = logging.Formatter("%(levelname)s: %(message)s")
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)

        return logger

    def _initialize_transcription_service(self) -> None:
        """Initialize the transcription service."""
        try:
            self.transcription_service = TranscriptionService(
                self.config.transcription.model_dump()
            )
            if self.transcription_service.is_available():
                engine_info = self.transcription_service.get_engine_info()
                self.logger.info(
                    f"Transcription service initialized: {engine_info['provider']}"
                )
            else:
                self.logger.warning(
                    "Transcription service not available - check configuration"
                )
        except Exception as e:
            self.logger.error(f"Failed to initialize transcription service: {e}")
            self.transcription_service = None

    async def _start_realtime_service(self) -> None:
        """Start the real-time transcription service."""
        if not self.transcription_service:
            raise RuntimeError("Transcription service not initialized")

        try:
            # Initialize real-time service
            self.realtime_service = RealTimeTranscriptionService(
                wake_word_config=self.config.wake_word.model_dump(),
                microphone_config=self.config.microphone.model_dump(),
                transcription_config=self.config.transcription.model_dump(),
                power_words_config=self.config.power_words.model_dump(),
            )

            # Set up callbacks
            self.realtime_service.set_transcription_callback(
                self._on_transcription_result
            )
            self.realtime_service.set_wake_word_callback(self._on_wake_word_detected)
            self.realtime_service.set_state_change_callback(
                self._on_realtime_state_change
            )

            # Start the service
            await self.realtime_service.start_service()

            self.logger.info(
                "Real-time transcription service started with wake word detection"
            )

        except Exception as e:
            self.logger.error(f"Failed to start real-time service: {e}")
            self.status = DaemonStatus.ERROR
            raise

    async def _on_transcription_result(self, result: Any, partial: bool) -> None:
        """Handle transcription results from real-time service."""
        transcription = str(result)  # Convert result to string
        result_type = "partial" if partial else "final"
        self.logger.info(
            f"{result_type.capitalize()} transcription result: {transcription}"
        )

        # Only save final transcriptions to file and clipboard
        if not partial:
            try:
                output_path = Path(self.config.file_watcher.output_directory)
                output_path.mkdir(parents=True, exist_ok=True)

                # Generate output filename with timestamp
                import datetime

                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                output_file = output_path / f"realtime_{timestamp}.txt"

                with open(output_file, "w", encoding="utf-8") as f:
                    f.write(
                        f"# Real-time transcription - {datetime.datetime.now().isoformat()}\n"
                    )
                    f.write(f"# Audio source: microphone\n\n")
                    f.write(transcription)

                self.logger.info(f"Final transcription saved to: {output_file}")

                # Copy to clipboard if enabled
                if (
                    self.config.output.enable_clipboard
                    and self.config.output.clipboard_on_final
                ):
                    from .clipboard import set_clipboard_text

                    if set_clipboard_text(transcription):
                        self.logger.info("Final transcription copied to clipboard")
                    else:
                        self.logger.warning("Failed to copy transcription to clipboard")

            except Exception as e:
                self.logger.error(f"Failed to save transcription: {e}")

    def _on_wake_word_detected(self, keyword_index: int, keyword_name: str) -> None:
        """Handle wake word detection."""
        self.logger.info(f"Wake word detected: {keyword_name}")
        self.status = DaemonStatus.TRANSCRIBING

    async def _on_realtime_state_change(
        self, old_state: "TranscriptionState", new_state: "TranscriptionState"
    ) -> None:
        """Handle real-time service state changes."""
        self.logger.debug(
            f"Real-time service state changed: {old_state.value} -> {new_state.value}"
        )

        # Update daemon status based on real-time service state
        if new_state.value == "listening_for_wake_word":
            self.status = DaemonStatus.LISTENING_FOR_WAKE_WORD
        elif new_state.value == "active_transcription":
            self.status = DaemonStatus.TRANSCRIBING
        elif new_state.value == "processing":
            self.status = DaemonStatus.TRANSCRIBING
        elif new_state.value == "error":
            self.status = DaemonStatus.ERROR
        elif new_state.value == "idle":
            if self.config.source_mode == "microphone":
                self.status = DaemonStatus.LISTENING_FOR_WAKE_WORD
            else:
                self.status = DaemonStatus.IDLE

    async def start(self) -> None:
        """Start the daemon."""
        if self._running:
            self.logger.warning("Daemon is already running")
            return

        self.logger.info("Starting Scribed daemon...")
        self._running = True
        self.status = DaemonStatus.IDLE

        try:
            # Start API server
            self.api_server = APIServer(self.config, self)
            await self.api_server.start()

            # Start file watcher for batch mode
            if self.config.source_mode == "file":
                loop = asyncio.get_running_loop()
                self.file_watcher = FileWatcher(self.config, self, loop)
                await self.file_watcher.start()
                self.status = DaemonStatus.PROCESSING_BATCH
            elif self.config.source_mode == "microphone":
                # Start real-time transcription service
                await self._start_realtime_service()
                self.status = DaemonStatus.LISTENING_FOR_WAKE_WORD

            self.logger.info(f"Daemon started in {self.config.source_mode} mode")

            # Wait for shutdown signal
            await self._shutdown_event.wait()

        except Exception as e:
            self.logger.error(f"Error starting daemon: {e}")
            self.status = DaemonStatus.ERROR
            raise
        finally:
            await self.stop()

    async def stop(self) -> None:
        """Stop the daemon."""
        if not self._running:
            return

        self.logger.info("Stopping Scribed daemon...")
        self._running = False
        self.status = DaemonStatus.DISABLED

        # Stop components
        if self.realtime_service:
            await self.realtime_service.stop_service()

        if self.file_watcher:
            await self.file_watcher.stop()

        if self.api_server:
            await self.api_server.stop()

        self.logger.info("Daemon stopped")

    def shutdown(self) -> None:
        """Signal the daemon to shutdown."""
        self._shutdown_event.set()

    def get_status(self) -> dict:
        """Get current daemon status."""
        status_info = {
            "status": self.status.value,
            "running": self._running,
            "config": {
                "source_mode": self.config.source_mode,
                "api_port": self.config.api.port,
                "transcription_provider": self.config.transcription.provider,
            },
        }

        # Add transcription service info if available
        if self.transcription_service:
            status_info["transcription"] = self.transcription_service.get_engine_info()

        # Add real-time service info if available
        if self.realtime_service:
            status_info["realtime"] = self.realtime_service.get_status()

        return status_info

    def setup_signal_handlers(self) -> None:
        """Set up signal handlers for graceful shutdown."""

        def signal_handler(sig, frame):
            self.logger.info(f"Received signal {sig}, shutting down...")
            self.shutdown()

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
