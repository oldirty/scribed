"""Legacy session module - functionality moved to simplified engine."""

from enum import Enum
from typing import Any, Dict, Optional, List, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass


class SessionStatus(Enum):
    """Session status enumeration (legacy compatibility)."""

    CREATED = "created"
    STARTING = "starting"
    IDLE = "idle"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class SessionMetrics:
    """Session metrics tracking."""

    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    total_duration: timedelta = timedelta(0)
    active_duration: timedelta = timedelta(0)
    pause_duration: timedelta = timedelta(0)
    transcription_count: int = 0
    error_count: int = 0
    bytes_processed: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary."""
        return {
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "total_duration_seconds": self.total_duration.total_seconds(),
            "active_duration_seconds": self.active_duration.total_seconds(),
            "pause_duration_seconds": self.pause_duration.total_seconds(),
            "transcription_count": self.transcription_count,
            "error_count": self.error_count,
            "bytes_processed": self.bytes_processed,
        }


@dataclass
class TranscriptionResult:
    """Transcription result with metadata."""

    text: str
    confidence: float
    timestamp: datetime
    is_partial: bool = False
    processing_time: float = 0.0
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class TranscriptionSession:
    """Legacy session class for test compatibility."""

    def __init__(
        self,
        session_id: str,
        session_type: str,
        config: Dict[str, Any],
        transcription_service=None,
        logger=None,
    ):
        self.session_id = session_id
        self.session_type = session_type
        self.config = config
        self.status = SessionStatus.CREATED
        self.created_at = datetime.now()
        self.transcription_service = transcription_service
        self.logger = logger
        self.metrics = SessionMetrics()

        # Internal state
        self._running = False
        self._paused = False
        self._results: List[TranscriptionResult] = []
        self._current_result = ""

        # Timing tracking
        self._active_start_time: Optional[datetime] = None
        self._pause_start_time: Optional[datetime] = None

        # Callbacks
        self._result_callbacks: List[Callable] = []
        self._status_callbacks: List[Callable] = []
        self._error_callbacks: List[Callable] = []

    async def start(self):
        """Start session."""
        if self._running:
            return

        if (
            not self.transcription_service
            or not self.transcription_service.is_available()
        ):
            raise RuntimeError("Transcription service not available")

        self._running = True
        self._set_status(SessionStatus.ACTIVE)

    async def stop(self):
        """Stop session."""
        if not self._running:
            return

        self._running = False
        self._paused = False
        self._set_status(SessionStatus.COMPLETED)

    async def pause(self):
        """Pause session."""
        if not self._running or self._paused:
            return

        self._paused = True
        self._set_status(SessionStatus.PAUSED)

    async def resume(self):
        """Resume session."""
        if not self._running or not self._paused:
            return

        self._paused = False
        self._set_status(SessionStatus.ACTIVE)

    def add_transcription_result(
        self,
        text: str,
        confidence: float,
        is_partial: bool = False,
        processing_time: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Add transcription result."""
        if not self._running:
            return

        result = TranscriptionResult(
            text=text,
            confidence=confidence,
            timestamp=datetime.now(),
            is_partial=is_partial,
            processing_time=processing_time,
            metadata=metadata or {},
        )

        self._results.append(result)
        self._current_result = text

        if not is_partial:
            self.metrics.transcription_count += 1

        # Call result callbacks
        for callback in self._result_callbacks:
            try:
                callback(result)
            except Exception:
                pass  # Ignore callback errors

    def get_results(self, include_partial: bool = False) -> List[TranscriptionResult]:
        """Get transcription results."""
        if include_partial:
            return self._results.copy()
        return [r for r in self._results if not r.is_partial]

    def get_final_text(self, separator: str = " ") -> str:
        """Get final transcribed text."""
        final_results = self.get_results(include_partial=False)
        return separator.join(r.text for r in final_results)

    def get_metrics(self) -> Dict[str, Any]:
        """Get session metrics."""
        return {
            "session_id": self.session_id,
            "session_type": self.session_type,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "is_running": self._running,
            "is_paused": self._paused,
            "result_count": len(self._results),
            "final_result_count": len(self.get_results(include_partial=False)),
            **self.metrics.to_dict(),
        }

    def get_status_info(self) -> Dict[str, Any]:
        """Get session status info."""
        return {
            "session_id": self.session_id,
            "session_type": self.session_type,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "running": self._running,
            "paused": self._paused,
            "current_result": self._current_result,
            "result_count": len(self._results),
        }

    def get_status(self) -> Dict[str, Any]:
        """Get session status (legacy compatibility)."""
        return {
            "session_id": self.session_id,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
        }

    # Callback management
    def add_result_callback(self, callback: Callable):
        """Add result callback."""
        self._result_callbacks.append(callback)

    def remove_result_callback(self, callback: Callable):
        """Remove result callback."""
        if callback in self._result_callbacks:
            self._result_callbacks.remove(callback)

    def add_status_callback(self, callback: Callable):
        """Add status callback."""
        self._status_callbacks.append(callback)

    def remove_status_callback(self, callback: Callable):
        """Remove status callback."""
        if callback in self._status_callbacks:
            self._status_callbacks.remove(callback)

    def add_error_callback(self, callback: Callable):
        """Add error callback."""
        self._error_callbacks.append(callback)

    def remove_error_callback(self, callback: Callable):
        """Remove error callback."""
        if callback in self._error_callbacks:
            self._error_callbacks.remove(callback)

    # Properties
    @property
    def is_active(self) -> bool:
        """Check if session is active."""
        return self._running and not self._paused

    @property
    def is_running(self) -> bool:
        """Check if session is running."""
        return self._running

    @property
    def is_paused(self) -> bool:
        """Check if session is paused."""
        return self._paused

    # Internal methods
    def _set_status(self, new_status: SessionStatus):
        """Set session status and trigger callbacks."""
        if self.status == new_status:
            return

        old_status = self.status
        self.status = new_status

        # Update timing
        now = datetime.now()
        if new_status == SessionStatus.ACTIVE:
            if self.metrics.start_time is None:
                self.metrics.start_time = now
            self._active_start_time = now

            # If resuming from pause, update pause duration
            if self._pause_start_time:
                self.metrics.pause_duration += now - self._pause_start_time
                self._pause_start_time = None

        elif new_status == SessionStatus.PAUSED:
            if self._active_start_time:
                self.metrics.active_duration += now - self._active_start_time
                self._active_start_time = None
            self._pause_start_time = now

        elif new_status == SessionStatus.COMPLETED:
            self.metrics.end_time = now
            if self._active_start_time:
                self.metrics.active_duration += now - self._active_start_time
                self._active_start_time = None
            if self.metrics.start_time:
                self.metrics.total_duration = now - self.metrics.start_time

        # Call status callbacks
        for callback in self._status_callbacks:
            try:
                callback(old_status, new_status)
            except Exception:
                pass  # Ignore callback errors

    def _handle_error(self, error: Exception):
        """Handle session error."""
        self.metrics.error_count += 1
        self._set_status(SessionStatus.ERROR)

        # Call error callbacks
        for callback in self._error_callbacks:
            try:
                callback(error)
            except Exception:
                pass  # Ignore callback errors

    # String representations
    def __str__(self) -> str:
        """String representation."""
        return f"TranscriptionSession(id={self.session_id}, type={self.session_type}, status={self.status.value})"

    def __repr__(self) -> str:
        """Detailed string representation."""
        return (
            f"TranscriptionSession(id={self.session_id}, type={self.session_type}, "
            f"running={self._running}, paused={self._paused}, results={len(self._results)})"
        )
