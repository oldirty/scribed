"""File watcher for batch audio transcription."""

import asyncio
import logging
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Union
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent

from .base import AudioSource, AudioChunk, AudioError
from .file_source import FileSource

logger = logging.getLogger(__name__)


class AudioFileHandler(FileSystemEventHandler):
    """Handler for audio file events."""

    def __init__(
        self, file_watcher: "FileWatcherSource", loop: asyncio.AbstractEventLoop
    ) -> None:
        """Initialize handler."""
        super().__init__()
        self.file_watcher = file_watcher
        self.loop = loop

    def on_created(self, event: FileSystemEvent) -> None:
        """Handle file creation events."""
        if event.is_directory:
            return

        file_path = Path(str(event.src_path))
        if file_path.suffix.lower() in self.file_watcher.supported_formats:
            logger.info(f"New audio file detected: {file_path}")
            asyncio.run_coroutine_threadsafe(
                self.file_watcher._queue_file(file_path), self.loop
            )


class FileWatcherSource(AudioSource):
    """File system watcher that implements AudioSource interface for batch processing."""

    def __init__(self, config: Dict[str, Any]) -> None:
        """Initialize file watcher source.

        Args:
            config: Configuration dictionary with keys:
                - watch_directory: Directory to watch for new files
                - supported_formats: List of supported file extensions
                - recursive: Whether to watch subdirectories (default: False)
                - process_existing: Whether to process existing files on start (default: True)
                - chunk_size: Chunk size for file processing (default: 1024)
                - target_sample_rate: Target sample rate (default: 16000)
                - target_channels: Target channels (default: 1)
                - target_format: Target format (default: "int16")
        """
        super().__init__(config)

        # Directory configuration
        watch_dir = config.get("watch_directory", "./audio_input")
        self.watch_directory = Path(watch_dir)

        # File processing configuration
        self.supported_formats = set(
            config.get("supported_formats", [".wav", ".mp3", ".flac", ".m4a"])
        )
        self.recursive = config.get("recursive", False)
        self.process_existing = config.get("process_existing", True)

        # Audio configuration for file processing
        self.chunk_size = config.get("chunk_size", 1024)
        self.target_sample_rate = config.get("target_sample_rate", 16000)
        self.target_channels = config.get("target_channels", 1)
        self.target_format = config.get("target_format", "int16")

        # Ensure watch directory exists
        self.watch_directory.mkdir(parents=True, exist_ok=True)

        # File watching components
        self.observer: Optional[Observer] = None
        self.handler: Optional[AudioFileHandler] = None
        self._processed_files: Set[Path] = set()
        self._file_queue: asyncio.Queue[Path] = asyncio.Queue()
        self._current_file_source: Optional[FileSource] = None

        self.logger.info(f"File watcher configured for: {self.watch_directory}")
        self.logger.info(f"Supported formats: {', '.join(self.supported_formats)}")

    async def start(self) -> None:
        """Start watching for files."""
        if self._is_active:
            self.logger.warning("File watcher already active")
            return

        try:
            # Start file system watcher
            self.observer = Observer()
            self.handler = AudioFileHandler(self, asyncio.get_event_loop())

            self.observer.schedule(
                self.handler, str(self.watch_directory), recursive=self.recursive
            )
            self.observer.start()

            # Process existing files if configured
            if self.process_existing:
                await self._queue_existing_files()

            self._mark_active()

        except Exception as e:
            await self.stop()
            raise AudioError(f"Failed to start file watcher: {e}")

    async def stop(self) -> None:
        """Stop watching for files."""
        if not self._is_active:
            return

        self._mark_inactive()

        # Stop current file source
        if self._current_file_source:
            await self._current_file_source.stop()
            self._current_file_source = None

        # Stop file system watcher
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.observer = None

        self.handler = None

        # Clear file queue
        while not self._file_queue.empty():
            try:
                self._file_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

    async def read_chunk(self) -> Optional[AudioChunk]:
        """Read the next audio chunk from the current file or next file in queue.

        Returns:
            AudioChunk if available, None if no more files to process
        """
        if not self._is_active:
            return None

        # If we have a current file source, try to read from it
        if self._current_file_source:
            chunk = await self._current_file_source.read_chunk()
            if chunk is not None:
                return chunk

            # Current file is finished, clean up
            await self._current_file_source.stop()
            self._current_file_source = None

        # Try to get the next file from queue
        try:
            next_file = await asyncio.wait_for(self._file_queue.get(), timeout=1.0)
            await self._start_next_file(next_file)

            # Try to read from the new file
            if self._current_file_source:
                return await self._current_file_source.read_chunk()

        except asyncio.TimeoutError:
            # No files in queue, return None but stay active
            return None
        except Exception as e:
            self.logger.error(f"Error processing next file: {e}")
            return None

        return None

    def get_audio_info(self) -> Dict[str, Any]:
        """Get information about the file watcher source."""
        info = self.get_base_info()
        info.update(
            {
                "watch_directory": str(self.watch_directory),
                "supported_formats": list(self.supported_formats),
                "recursive": self.recursive,
                "process_existing": self.process_existing,
                "processed_files_count": len(self._processed_files),
                "queued_files_count": self._file_queue.qsize(),
                "current_file": (
                    str(self._current_file_source.file_path)
                    if self._current_file_source
                    else None
                ),
                "chunk_size": self.chunk_size,
                "target_sample_rate": self.target_sample_rate,
                "target_channels": self.target_channels,
                "target_format": self.target_format,
            }
        )

        # Add current file info if available
        if self._current_file_source:
            current_info = self._current_file_source.get_audio_info()
            info["current_file_info"] = {
                "progress_percent": current_info.get("progress_percent", 0),
                "duration_seconds": current_info.get("duration_seconds", 0),
                "remaining_duration": self._current_file_source.get_remaining_duration(),
            }

        return info

    def is_available(self) -> bool:
        """Check if file watcher source is available."""
        return FileSource({}).is_available()

    async def _queue_existing_files(self) -> None:
        """Queue existing audio files in the watch directory."""
        self.logger.info("Scanning for existing audio files...")

        if self.recursive:
            pattern = "**/*"
        else:
            pattern = "*"

        for file_path in self.watch_directory.glob(pattern):
            if (
                file_path.is_file()
                and file_path.suffix.lower() in self.supported_formats
                and file_path not in self._processed_files
            ):

                self.logger.info(f"Queuing existing file: {file_path}")
                await self._file_queue.put(file_path)

    async def _queue_file(self, file_path: Path) -> None:
        """Queue a new file for processing."""
        if file_path in self._processed_files:
            self.logger.debug(f"File already processed: {file_path}")
            return

        if not FileSource.is_format_supported(file_path):
            self.logger.warning(f"Unsupported file format: {file_path}")
            return

        self.logger.info(f"Queuing new file: {file_path}")
        await self._file_queue.put(file_path)

    async def _start_next_file(self, file_path: Path) -> None:
        """Start processing the next file."""
        try:
            self.logger.info(f"Starting file processing: {file_path}")

            # Create file source configuration
            file_config = {
                "file_path": str(file_path),
                "chunk_size": self.chunk_size,
                "target_sample_rate": self.target_sample_rate,
                "target_channels": self.target_channels,
                "target_format": self.target_format,
            }

            # Create and start file source
            self._current_file_source = FileSource(file_config)
            await self._current_file_source.start()

            # Mark file as processed
            self._processed_files.add(file_path)

        except Exception as e:
            self.logger.error(f"Failed to start file processing for {file_path}: {e}")
            self._processed_files.discard(file_path)  # Allow retry
            if self._current_file_source:
                await self._current_file_source.stop()
                self._current_file_source = None

    def get_processed_files(self) -> List[Path]:
        """Get list of processed files."""
        return list(self._processed_files)

    def get_queued_files_count(self) -> int:
        """Get number of files in processing queue."""
        return self._file_queue.qsize()

    def reset_processed_files(self) -> None:
        """Reset the processed files set (allows reprocessing)."""
        self._processed_files.clear()
        self.logger.info("Reset processed files list")


# Legacy FileWatcher class for backward compatibility
class FileWatcher:
    """Legacy file watcher for backward compatibility."""

    def __init__(
        self, config: Any, daemon: Any, loop: asyncio.AbstractEventLoop
    ) -> None:
        """Initialize legacy file watcher."""
        self.logger = logging.getLogger(__name__)
        self.logger.warning("FileWatcher is deprecated. Use FileWatcherSource instead.")

        # Extract configuration
        watcher_config = {
            "watch_directory": getattr(
                config.file_watcher, "watch_directory", "./audio_input"
            ),
            "supported_formats": getattr(
                config.file_watcher, "supported_formats", [".wav", ".mp3"]
            ),
            "recursive": False,
            "process_existing": True,
        }

        self.file_watcher_source = FileWatcherSource(watcher_config)
        self.daemon = daemon
        self.loop = loop

        # Legacy attributes for compatibility
        self.supported_formats = set(watcher_config["supported_formats"])
        self.watch_directory = Path(watcher_config["watch_directory"])
        self.output_directory = getattr(
            config.file_watcher, "output_directory", "./transcripts"
        )
        if isinstance(self.output_directory, str):
            self.output_directory = Path(self.output_directory)
        self.output_directory.mkdir(parents=True, exist_ok=True)

        self._processed_files: Set[Path] = set()

    async def start(self) -> None:
        """Start the legacy file watcher."""
        await self.file_watcher_source.start()

        # Start processing task
        asyncio.create_task(self._process_files_task())

    async def stop(self) -> None:
        """Stop the legacy file watcher."""
        await self.file_watcher_source.stop()

    async def _process_files_task(self) -> None:
        """Task to process files and create transcriptions."""
        async for chunk in self.file_watcher_source.read_stream():
            # For legacy compatibility, we need to handle file-by-file processing
            current_file = self.file_watcher_source._current_file_source
            if current_file and current_file.file_path not in self._processed_files:
                await self.process_file(current_file.file_path)
                self._processed_files.add(current_file.file_path)

    async def process_file(self, file_path: Path) -> None:
        """Process a single audio file (legacy method)."""
        try:
            self.logger.info(f"Processing audio file: {file_path}")

            # Generate output file path
            output_file = self.output_directory / f"{file_path.stem}.txt"

            # Try to get transcription service from daemon
            transcription_service = getattr(self.daemon, "transcription_service", None)

            if transcription_service and transcription_service.is_available():
                # Use actual transcription service
                self.logger.info(f"Transcribing with {transcription_service.provider}")
                result = await transcription_service.transcribe_file(file_path)

                if result.status.value == "completed":
                    # Create transcript content with metadata
                    content_lines = [
                        f"# Transcription of {file_path.name}",
                        f"# Generated by Scribed using {transcription_service.provider}",
                        (
                            f"# Processing time: {result.processing_time:.2f}s"
                            if result.processing_time
                            else ""
                        ),
                        f"# Language: {result.language}" if result.language else "",
                        "",
                        result.text,
                    ]

                    # Add segment information if available
                    if result.segments:
                        content_lines.extend(["", "## Segments", ""])
                        for i, segment in enumerate(result.segments, 1):
                            start_time = (
                                f"{segment.start_time:.2f}s"
                                if segment.start_time
                                else "N/A"
                            )
                            end_time = (
                                f"{segment.end_time:.2f}s"
                                if segment.end_time
                                else "N/A"
                            )
                            content_lines.append(
                                f"{i}. [{start_time} - {end_time}] {segment.text}"
                            )

                    transcript_content = "\n".join(content_lines)

                else:
                    # Transcription failed
                    transcript_content = f"# Transcription Failed\n\nError: {result.error}\nFile: {file_path.name}"
                    self.logger.error(
                        f"Transcription failed for {file_path}: {result.error}"
                    )
            else:
                # Fallback to placeholder transcription
                self.logger.warning(
                    "No transcription service available, creating placeholder"
                )
                transcript_content = (
                    f"[Transcription placeholder for {file_path.name}]\n"
                )
                transcript_content += f"File: {file_path}\n"
                transcript_content += f"Format: {file_path.suffix}\n"
                transcript_content += f"Size: {file_path.stat().st_size} bytes\n"
                transcript_content += "\nActual transcription will be available when transcription engines are properly configured."

            # Write transcription to output file
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(transcript_content)

            self.logger.info(f"Transcription saved to: {output_file}")

        except Exception as e:
            self.logger.error(f"Error processing file {file_path}: {e}")
