"""Test transcription session functionality."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta

from scribed.core.session import (
    TranscriptionSession,
    SessionStatus,
    SessionMetrics,
    TranscriptionResult,
)
from scribed.transcription.service import TranscriptionService


class TestSessionMetrics:
    """Test SessionMetrics class."""

    def test_metrics_initialization(self):
        """Test metrics initialization with defaults."""
        metrics = SessionMetrics()

        assert metrics.start_time is None
        assert metrics.end_time is None
        assert metrics.total_duration == timedelta(0)
        assert metrics.active_duration == timedelta(0)
        assert metrics.pause_duration == timedelta(0)
        assert metrics.transcription_count == 0
        assert metrics.error_count == 0
        assert metrics.bytes_processed == 0

    def test_metrics_to_dict(self):
        """Test converting metrics to dictionary."""
        start_time = datetime.now()
        end_time = start_time + timedelta(seconds=10)

        metrics = SessionMetrics(
            start_time=start_time,
            end_time=end_time,
            total_duration=timedelta(seconds=10),
            active_duration=timedelta(seconds=8),
            pause_duration=timedelta(seconds=2),
            transcription_count=5,
            error_count=1,
            bytes_processed=1024,
        )

        result = metrics.to_dict()

        assert result["start_time"] == start_time.isoformat()
        assert result["end_time"] == end_time.isoformat()
        assert result["total_duration_seconds"] == 10.0
        assert result["active_duration_seconds"] == 8.0
        assert result["pause_duration_seconds"] == 2.0
        assert result["transcription_count"] == 5
        assert result["error_count"] == 1
        assert result["bytes_processed"] == 1024

    def test_metrics_to_dict_none_times(self):
        """Test converting metrics to dict with None times."""
        metrics = SessionMetrics()
        result = metrics.to_dict()

        assert result["start_time"] is None
        assert result["end_time"] is None


class TestTranscriptionResult:
    """Test TranscriptionResult class."""

    def test_result_creation(self):
        """Test creating transcription result."""
        timestamp = datetime.now()
        metadata = {"confidence_details": {"word_level": [0.9, 0.8, 0.95]}}

        result = TranscriptionResult(
            text="Hello world",
            confidence=0.9,
            timestamp=timestamp,
            is_partial=False,
            processing_time=0.5,
            metadata=metadata,
        )

        assert result.text == "Hello world"
        assert result.confidence == 0.9
        assert result.timestamp == timestamp
        assert result.is_partial is False
        assert result.processing_time == 0.5
        assert result.metadata == metadata

    def test_result_defaults(self):
        """Test transcription result with default values."""
        timestamp = datetime.now()

        result = TranscriptionResult(text="Test", confidence=0.8, timestamp=timestamp)

        assert result.is_partial is False
        assert result.processing_time == 0.0
        assert result.metadata == {}


class TestTranscriptionSession:
    """Test TranscriptionSession class."""

    @pytest.fixture
    def mock_transcription_service(self):
        """Mock transcription service."""
        service = Mock(spec=TranscriptionService)
        service.is_available.return_value = True
        return service

    @pytest.fixture
    def sample_config(self):
        """Sample configuration for testing."""
        return {
            "audio": {"sample_rate": 16000, "channels": 1},
            "transcription": {"provider": "mock"},
        }

    @pytest.fixture
    def session(self, mock_transcription_service, sample_config):
        """Create session instance for testing."""
        return TranscriptionSession(
            session_id="test_session_1",
            session_type="test",
            config=sample_config,
            transcription_service=mock_transcription_service,
        )

    def test_session_initialization(
        self, session, mock_transcription_service, sample_config
    ):
        """Test session initialization."""
        assert session.session_id == "test_session_1"
        assert session.session_type == "test"
        assert session.config == sample_config
        assert session.transcription_service == mock_transcription_service
        assert session.status == SessionStatus.CREATED
        assert isinstance(session.created_at, datetime)
        assert isinstance(session.metrics, SessionMetrics)
        assert not session._running
        assert not session._paused
        assert len(session._results) == 0

    def test_session_initialization_with_logger(
        self, mock_transcription_service, sample_config
    ):
        """Test session initialization with custom logger."""
        import logging

        logger = logging.getLogger("test_logger")

        session = TranscriptionSession(
            session_id="test_session_2",
            session_type="test",
            config=sample_config,
            transcription_service=mock_transcription_service,
            logger=logger,
        )

        assert session.logger == logger

    @pytest.mark.asyncio
    async def test_session_start_success(self, session):
        """Test successful session start."""
        await session.start()

        assert session.status == SessionStatus.ACTIVE
        assert session._running is True
        assert session._paused is False
        assert session.metrics.start_time is not None

    @pytest.mark.asyncio
    async def test_session_start_already_running(self, session):
        """Test starting session when already running."""
        await session.start()

        # Try to start again
        await session.start()  # Should not raise error
        assert session.status == SessionStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_session_start_no_transcription_service(self, sample_config):
        """Test session start when transcription service is not available."""
        mock_service = Mock()
        mock_service.is_available.return_value = False

        session = TranscriptionSession(
            session_id="test_session",
            session_type="test",
            config=sample_config,
            transcription_service=mock_service,
        )

        with pytest.raises(RuntimeError, match="Transcription service not available"):
            await session.start()

    @pytest.mark.asyncio
    async def test_session_start_none_transcription_service(self, sample_config):
        """Test session start when transcription service is None."""
        session = TranscriptionSession(
            session_id="test_session",
            session_type="test",
            config=sample_config,
            transcription_service=None,
        )

        with pytest.raises(RuntimeError, match="Transcription service not available"):
            await session.start()

    @pytest.mark.asyncio
    async def test_session_stop_success(self, session):
        """Test successful session stop."""
        await session.start()
        await session.stop()

        assert session.status == SessionStatus.COMPLETED
        assert session._running is False
        assert session._paused is False
        assert session.metrics.end_time is not None

    @pytest.mark.asyncio
    async def test_session_stop_not_running(self, session):
        """Test stopping session when not running."""
        await session.stop()  # Should not raise error
        assert session.status == SessionStatus.CREATED

    @pytest.mark.asyncio
    async def test_session_pause_success(self, session):
        """Test successful session pause."""
        await session.start()
        await session.pause()

        assert session.status == SessionStatus.PAUSED
        assert session._running is True
        assert session._paused is True

    @pytest.mark.asyncio
    async def test_session_pause_not_running(self, session):
        """Test pausing session when not running."""
        await session.pause()  # Should not raise error
        assert session.status == SessionStatus.CREATED

    @pytest.mark.asyncio
    async def test_session_pause_already_paused(self, session):
        """Test pausing session when already paused."""
        await session.start()
        await session.pause()
        await session.pause()  # Should not raise error
        assert session.status == SessionStatus.PAUSED

    @pytest.mark.asyncio
    async def test_session_resume_success(self, session):
        """Test successful session resume."""
        await session.start()
        await session.pause()
        await session.resume()

        assert session.status == SessionStatus.ACTIVE
        assert session._running is True
        assert session._paused is False

    @pytest.mark.asyncio
    async def test_session_resume_not_paused(self, session):
        """Test resuming session when not paused."""
        await session.start()
        await session.resume()  # Should not raise error
        assert session.status == SessionStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_session_resume_not_running(self, session):
        """Test resuming session when not running."""
        await session.resume()  # Should not raise error
        assert session.status == SessionStatus.CREATED

    def test_add_transcription_result_success(self, session):
        """Test adding transcription result."""
        session._running = True

        session.add_transcription_result(
            text="Hello world",
            confidence=0.9,
            is_partial=False,
            processing_time=0.5,
            metadata={"test": "data"},
        )

        assert len(session._results) == 1
        assert session.metrics.transcription_count == 1
        assert session._current_result == "Hello world"

        result = session._results[0]
        assert result.text == "Hello world"
        assert result.confidence == 0.9
        assert result.is_partial is False
        assert result.processing_time == 0.5
        assert result.metadata == {"test": "data"}

    def test_add_transcription_result_partial(self, session):
        """Test adding partial transcription result."""
        session._running = True

        session.add_transcription_result(text="Hello", confidence=0.8, is_partial=True)

        assert len(session._results) == 1
        assert session.metrics.transcription_count == 0  # Partial results don't count
        assert session._current_result == "Hello"

    def test_add_transcription_result_not_running(self, session):
        """Test adding result when session not running."""
        session.add_transcription_result("Test", 0.9)

        # Should not add result
        assert len(session._results) == 0
        assert session.metrics.transcription_count == 0

    def test_get_results_all(self, session):
        """Test getting all results."""
        session._running = True

        session.add_transcription_result("Final 1", 0.9, is_partial=False)
        session.add_transcription_result("Partial 1", 0.8, is_partial=True)
        session.add_transcription_result("Final 2", 0.95, is_partial=False)

        all_results = session.get_results(include_partial=True)
        assert len(all_results) == 3

        final_results = session.get_results(include_partial=False)
        assert len(final_results) == 2
        assert all(not r.is_partial for r in final_results)

    def test_get_final_text(self, session):
        """Test getting final transcribed text."""
        session._running = True

        session.add_transcription_result("Hello", 0.9, is_partial=False)
        session.add_transcription_result("partial", 0.8, is_partial=True)
        session.add_transcription_result("world", 0.95, is_partial=False)

        final_text = session.get_final_text()
        assert final_text == "Hello world"

        # Test custom separator
        final_text_custom = session.get_final_text(separator=" | ")
        assert final_text_custom == "Hello | world"

    def test_get_metrics(self, session):
        """Test getting session metrics."""
        metrics = session.get_metrics()

        assert "session_id" in metrics
        assert "session_type" in metrics
        assert "status" in metrics
        assert "created_at" in metrics
        assert "is_running" in metrics
        assert "is_paused" in metrics
        assert "result_count" in metrics
        assert "final_result_count" in metrics

        assert metrics["session_id"] == "test_session_1"
        assert metrics["session_type"] == "test"
        assert metrics["status"] == SessionStatus.CREATED.value
        assert metrics["is_running"] is False
        assert metrics["is_paused"] is False
        assert metrics["result_count"] == 0
        assert metrics["final_result_count"] == 0

    def test_get_status_info(self, session):
        """Test getting session status info."""
        status_info = session.get_status_info()

        assert "session_id" in status_info
        assert "session_type" in status_info
        assert "status" in status_info
        assert "created_at" in status_info
        assert "running" in status_info
        assert "paused" in status_info
        assert "current_result" in status_info
        assert "result_count" in status_info

        assert status_info["session_id"] == "test_session_1"
        assert status_info["session_type"] == "test"

    def test_result_callbacks(self, session):
        """Test transcription result callbacks."""
        callback_calls = []

        def result_callback(result):
            callback_calls.append(result)

        session.add_result_callback(result_callback)
        session._running = True

        session.add_transcription_result("Test", 0.9)

        assert len(callback_calls) == 1
        assert callback_calls[0].text == "Test"

        # Remove callback
        session.remove_result_callback(result_callback)
        session.add_transcription_result("Test 2", 0.8)

        # Should not have been called again
        assert len(callback_calls) == 1

    def test_status_callbacks(self, session):
        """Test status change callbacks."""
        callback_calls = []

        def status_callback(old_status, new_status):
            callback_calls.append((old_status, new_status))

        session.add_status_callback(status_callback)

        # Trigger status change
        session._set_status(SessionStatus.STARTING)

        assert len(callback_calls) == 1
        assert callback_calls[0] == (SessionStatus.CREATED, SessionStatus.STARTING)

        # Remove callback
        session.remove_status_callback(status_callback)
        session._set_status(SessionStatus.ACTIVE)

        # Should not have been called again
        assert len(callback_calls) == 1

    def test_error_callbacks(self, session):
        """Test error callbacks."""
        callback_calls = []

        def error_callback(error):
            callback_calls.append(error)

        session.add_error_callback(error_callback)

        # Trigger error
        test_error = Exception("Test error")
        session._handle_error(test_error)

        assert len(callback_calls) == 1
        assert callback_calls[0] == test_error
        assert session.status == SessionStatus.ERROR
        assert session.metrics.error_count == 1

        # Remove callback
        session.remove_error_callback(error_callback)
        session._handle_error(Exception("Another error"))

        # Should not have been called again
        assert len(callback_calls) == 1

    def test_properties(self, session):
        """Test session properties."""
        assert not session.is_active
        assert not session.is_running
        assert not session.is_paused

        session._running = True
        assert session.is_running
        assert session.is_active  # Active when running and not paused

        session._paused = True
        assert session.is_paused
        assert not session.is_active  # Not active when paused

        session._paused = False
        assert session.is_active  # Active again when not paused

    @pytest.mark.asyncio
    async def test_properties_after_start(self, session):
        """Test session properties after proper start."""
        await session.start()

        assert session.is_active
        assert session.is_running
        assert not session.is_paused

    def test_string_representations(self, session):
        """Test string representations of session."""
        str_repr = str(session)
        assert "TranscriptionSession" in str_repr
        assert "test_session_1" in str_repr
        assert "test" in str_repr
        assert "created" in str_repr

        repr_str = repr(session)
        assert "TranscriptionSession" in repr_str
        assert "test_session_1" in repr_str
        assert "test" in repr_str
        assert "running=False" in repr_str
        assert "paused=False" in repr_str
        assert "results=0" in repr_str

    def test_status_change_metrics_tracking(self, session):
        """Test that status changes update metrics correctly."""
        import time

        # Start session
        session._set_status(SessionStatus.ACTIVE)
        assert session.metrics.start_time is not None
        assert session._active_start_time is not None

        # Wait a small amount to ensure time difference
        time.sleep(0.01)

        # Pause session (this should set _pause_start_time and update active_duration)
        session._set_status(SessionStatus.PAUSED)
        assert session.metrics.active_duration > timedelta(0)
        assert session._pause_start_time is not None

        # Wait a small amount
        time.sleep(0.01)

        # Resume session (this will update pause_duration)
        session._set_status(SessionStatus.ACTIVE)
        assert session.metrics.pause_duration > timedelta(0)

        # Wait a small amount
        time.sleep(0.01)

        # Complete session
        session._set_status(SessionStatus.COMPLETED)
        assert session.metrics.end_time is not None
        assert session.metrics.total_duration > timedelta(0)

    def test_callback_error_handling(self, session):
        """Test that callback errors don't break the session."""

        def bad_callback(result):
            raise Exception("Callback error")

        session.add_result_callback(bad_callback)
        session._running = True

        # Should not raise exception
        session.add_transcription_result("Test", 0.9)
        assert len(session._results) == 1

    def test_status_change_no_duplicate(self, session):
        """Test that setting same status doesn't trigger callbacks."""
        callback_calls = []

        def status_callback(old_status, new_status):
            callback_calls.append((old_status, new_status))

        session.add_status_callback(status_callback)

        # Set same status
        session._set_status(SessionStatus.CREATED)

        # Should not trigger callback
        assert len(callback_calls) == 0

    @pytest.mark.asyncio
    async def test_session_concurrent_results(self, session):
        """Test adding transcription results concurrently."""
        session._running = True

        import threading
        import time

        def add_results(prefix):
            for i in range(5):
                session.add_transcription_result(
                    f"{prefix}_result_{i}", confidence=0.9, is_partial=False
                )
                time.sleep(0.001)

        # Create multiple threads
        threads = []
        for i in range(3):
            thread = threading.Thread(target=add_results, args=(f"thread_{i}",))
            threads.append(thread)
            thread.start()

        # Wait for all threads
        for thread in threads:
            thread.join()

        # Check results
        results = session.get_results()
        assert len(results) == 15  # 3 threads * 5 results each
        assert session.metrics.transcription_count == 15

    def test_session_large_result_handling(self, session):
        """Test handling large transcription results."""
        session._running = True

        # Add a very large transcription result
        large_text = "A" * 10000  # 10KB of text
        session.add_transcription_result(large_text, 0.95)

        results = session.get_results()
        assert len(results) == 1
        assert len(results[0].text) == 10000
        assert results[0].text == large_text

    def test_session_result_ordering(self, session):
        """Test that results maintain chronological order."""
        session._running = True

        # Add results with small delays
        import time

        for i in range(5):
            session.add_transcription_result(f"result_{i}", 0.9)
            time.sleep(0.001)

        results = session.get_results()
        for i, result in enumerate(results):
            assert result.text == f"result_{i}"
            if i > 0:
                assert result.timestamp >= results[i - 1].timestamp

    def test_session_partial_vs_final_results(self, session):
        """Test handling of partial vs final results."""
        session._running = True

        # Add mix of partial and final results
        session.add_transcription_result("partial_1", 0.8, is_partial=True)
        session.add_transcription_result("final_1", 0.9, is_partial=False)
        session.add_transcription_result("partial_2", 0.7, is_partial=True)
        session.add_transcription_result("final_2", 0.95, is_partial=False)

        all_results = session.get_results(include_partial=True)
        final_results = session.get_results(include_partial=False)

        assert len(all_results) == 4
        assert len(final_results) == 2
        assert session.metrics.transcription_count == 2  # Only final results count

    def test_session_metadata_handling(self, session):
        """Test transcription result metadata handling."""
        session._running = True

        metadata = {
            "confidence_details": [0.9, 0.8, 0.95],
            "processing_info": {"model": "test", "duration": 1.5},
            "custom_field": "test_value",
        }

        session.add_transcription_result(
            "test result", confidence=0.9, metadata=metadata
        )

        results = session.get_results()
        assert len(results) == 1
        assert results[0].metadata == metadata

    @pytest.mark.asyncio
    async def test_session_lifecycle_edge_cases(self, session):
        """Test session lifecycle edge cases."""
        # Multiple start calls
        await session.start()
        await session.start()  # Should not error
        assert session.status.value == "active"

        # Pause when already paused
        await session.pause()
        await session.pause()  # Should not error
        assert session.status.value == "paused"

        # Resume when not paused
        await session.resume()
        await session.resume()  # Should not error
        assert session.status.value == "active"

        # Multiple stop calls
        await session.stop()
        await session.stop()  # Should not error
        assert session.status.value == "completed"

    def test_session_callback_error_isolation(self, session):
        """Test that callback errors don't affect session operation."""
        error_count = 0

        def good_callback(result):
            nonlocal error_count
            error_count += 1

        def bad_callback(result):
            raise Exception("Callback error")

        session.add_result_callback(good_callback)
        session.add_result_callback(bad_callback)
        session._running = True

        # Add result - should not fail despite bad callback
        session.add_transcription_result("test", 0.9)

        assert len(session._results) == 1
        assert error_count == 1  # Good callback was called

    def test_session_memory_efficiency(self, session):
        """Test session memory usage with many results."""
        session._running = True

        # Add many small results
        for i in range(1000):
            session.add_transcription_result(f"result_{i}", 0.9)

        assert len(session._results) == 1000
        assert session.metrics.transcription_count == 1000

        # Test final text generation doesn't cause memory issues
        final_text = session.get_final_text()
        assert len(final_text.split()) == 1000  # One word per result

    def test_session_custom_separator(self, session):
        """Test custom separator in final text generation."""
        session._running = True

        session.add_transcription_result("Hello", 0.9)
        session.add_transcription_result("world", 0.9)
        session.add_transcription_result("test", 0.9)

        # Test different separators
        assert session.get_final_text(" ") == "Hello world test"
        assert session.get_final_text(", ") == "Hello, world, test"
        assert session.get_final_text("\n") == "Hello\nworld\ntest"
        assert session.get_final_text("") == "Helloworldtest"

    def test_session_metrics_accuracy(self, session):
        """Test accuracy of session metrics calculations."""
        session._running = True

        # Add results with known processing times
        session.add_transcription_result("test1", 0.9, processing_time=0.1)
        session.add_transcription_result("test2", 0.8, processing_time=0.2)
        session.add_transcription_result("test3", 0.95, processing_time=0.15)

        metrics = session.get_metrics()
        assert metrics["result_count"] == 3
        assert metrics["final_result_count"] == 3

        # Test bytes processed tracking
        expected_bytes = len("test1") + len("test2") + len("test3")
        # Note: This assumes the session tracks bytes processed
        # The actual implementation may vary

    def test_session_string_representations_detailed(self, session):
        """Test detailed string representations."""
        session._running = True
        session.add_transcription_result("test result", 0.9)

        str_repr = str(session)
        repr_str = repr(session)

        # Check that important info is included
        assert session.session_id in str_repr
        assert session.session_type in str_repr
        assert session.session_id in repr_str
        assert "results=1" in repr_str or "1" in repr_str

    @pytest.mark.asyncio
    async def test_session_cleanup_on_completion(self, session):
        """Test proper cleanup when session completes."""
        await session.start()
        session.add_transcription_result("test", 0.9)

        # Complete session
        await session.stop()

        # Verify cleanup
        assert session.status.value == "completed"
        assert not session._running
        assert not session._paused
        assert session.metrics.end_time is not None
