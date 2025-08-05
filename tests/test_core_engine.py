"""Test core engine functionality."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime

from scribed.core.engine import ScribedEngine, EngineStatus
from scribed.core.session import TranscriptionSession, SessionStatus
from scribed.config import Config
from scribed.transcription.service import TranscriptionService


class TestScribedEngine:
    """Test ScribedEngine class."""

    @pytest.fixture
    def mock_transcription_service(self):
        """Mock transcription service."""
        service = Mock(spec=TranscriptionService)
        service.is_available.return_value = True
        service.get_engine_info.return_value = {"provider": "mock", "model": "test"}
        return service

    @pytest.fixture
    def sample_config(self):
        """Sample configuration for testing."""
        return Config()

    @pytest.fixture
    def engine(self, sample_config, mock_transcription_service):
        """Create engine instance for testing."""
        with patch(
            "scribed.core.engine.TranscriptionService",
            return_value=mock_transcription_service,
        ):
            engine = ScribedEngine(sample_config)
            return engine

    def test_engine_initialization(self, sample_config):
        """Test engine initialization."""
        with patch("scribed.core.engine.TranscriptionService") as mock_service_class:
            mock_service = Mock()
            mock_service.is_available.return_value = True
            mock_service.get_engine_info.return_value = {"provider": "test"}
            mock_service_class.return_value = mock_service

            engine = ScribedEngine(sample_config)

            assert engine.config == sample_config
            assert engine.status == EngineStatus.DISABLED
            assert engine.transcription_service == mock_service
            assert len(engine._active_sessions) == 0
            assert not engine._running

    def test_engine_initialization_with_no_config(self):
        """Test engine initialization with no config (loads from env)."""
        with patch("scribed.config.Config.from_env") as mock_from_env:
            mock_config = Mock(spec=Config)
            mock_from_env.return_value = mock_config

            with patch("scribed.core.engine.TranscriptionService"):
                engine = ScribedEngine()
                assert engine.config == mock_config

    def test_engine_initialization_service_unavailable(self, sample_config):
        """Test engine initialization when transcription service is unavailable."""
        with patch("scribed.core.engine.TranscriptionService") as mock_service_class:
            mock_service = Mock()
            mock_service.is_available.return_value = False
            mock_service_class.return_value = mock_service

            engine = ScribedEngine(sample_config)
            assert engine.status == EngineStatus.DISABLED

    def test_engine_initialization_service_error(self, sample_config):
        """Test engine initialization when transcription service fails."""
        with patch(
            "scribed.core.engine.TranscriptionService",
            side_effect=Exception("Service error"),
        ):
            engine = ScribedEngine(sample_config)
            assert engine.status == EngineStatus.ERROR
            assert engine.transcription_service is None

    @pytest.mark.asyncio
    async def test_engine_start_success(self, engine):
        """Test successful engine start."""
        await engine.start()

        assert engine.status == EngineStatus.RUNNING
        assert engine._running is True

    @pytest.mark.asyncio
    async def test_engine_start_already_running(self, engine):
        """Test starting engine when already running."""
        await engine.start()

        # Try to start again
        await engine.start()  # Should not raise error
        assert engine.status == EngineStatus.RUNNING

    @pytest.mark.asyncio
    async def test_engine_start_no_transcription_service(self, sample_config):
        """Test engine start when transcription service is not available."""
        with patch("scribed.core.engine.TranscriptionService", return_value=None):
            engine = ScribedEngine(sample_config)
            engine.transcription_service = None

            with pytest.raises(
                RuntimeError, match="Transcription service not available"
            ):
                await engine.start()

    @pytest.mark.asyncio
    async def test_engine_stop_success(self, engine):
        """Test successful engine stop."""
        await engine.start()
        await engine.stop()

        assert engine.status == EngineStatus.DISABLED
        assert engine._running is False

    @pytest.mark.asyncio
    async def test_engine_stop_not_running(self, engine):
        """Test stopping engine when not running."""
        await engine.stop()  # Should not raise error
        assert engine.status == EngineStatus.DISABLED

    @pytest.mark.asyncio
    async def test_engine_stop_with_active_sessions(self, engine):
        """Test stopping engine with active sessions."""
        await engine.start()

        # Create a session
        session_id = engine.create_session()
        await engine.start_session(session_id)

        # Stop engine should stop all sessions
        await engine.stop()

        assert engine.status == EngineStatus.DISABLED
        assert len(engine._active_sessions) == 0

    def test_engine_shutdown(self, engine):
        """Test engine shutdown signal."""
        assert not engine._shutdown_event.is_set()
        engine.shutdown()
        assert engine._shutdown_event.is_set()

    @pytest.mark.asyncio
    async def test_engine_wait_for_shutdown(self, engine):
        """Test waiting for shutdown signal."""
        # Start wait task
        wait_task = asyncio.create_task(engine.wait_for_shutdown())

        # Give it a moment to start waiting
        await asyncio.sleep(0.01)
        assert not wait_task.done()

        # Signal shutdown
        engine.shutdown()

        # Wait should complete
        await wait_task
        assert wait_task.done()

    @pytest.mark.asyncio
    async def test_create_session_success(self, engine):
        """Test successful session creation."""
        await engine.start()  # Engine needs to be running
        session_id = engine.create_session("test_type", {"test": "config"})

        assert session_id.startswith("session_1_")
        assert session_id in engine._active_sessions

        session = engine.get_session(session_id)
        assert session is not None
        assert session.session_type == "test_type"

    def test_create_session_engine_not_running(self, engine):
        """Test session creation when engine is not running."""
        with pytest.raises(RuntimeError, match="Engine is not running"):
            engine.create_session()

    @pytest.mark.asyncio
    async def test_create_session_running_engine(self, engine):
        """Test session creation when engine is running."""
        await engine.start()

        session_id = engine.create_session()
        assert session_id in engine._active_sessions

    def test_get_session_exists(self, engine):
        """Test getting existing session."""
        # Need to start engine first
        engine._running = True
        session_id = engine.create_session()

        session = engine.get_session(session_id)
        assert session is not None
        assert session.session_id == session_id

    def test_get_session_not_exists(self, engine):
        """Test getting non-existent session."""
        session = engine.get_session("non_existent")
        assert session is None

    @pytest.mark.asyncio
    async def test_start_session_success(self, engine):
        """Test starting a session."""
        await engine.start()
        session_id = engine.create_session()

        await engine.start_session(session_id)

        session = engine.get_session(session_id)
        assert session.status == SessionStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_start_session_not_found(self, engine):
        """Test starting non-existent session."""
        await engine.start()

        with pytest.raises(ValueError, match="Session not found"):
            await engine.start_session("non_existent")

    @pytest.mark.asyncio
    async def test_stop_session_success(self, engine):
        """Test stopping a session."""
        await engine.start()
        session_id = engine.create_session()
        await engine.start_session(session_id)

        await engine.stop_session(session_id)

        # Session should be removed from active sessions
        assert session_id not in engine._active_sessions

    @pytest.mark.asyncio
    async def test_stop_session_not_found(self, engine):
        """Test stopping non-existent session."""
        await engine.start()

        # Should not raise error
        await engine.stop_session("non_existent")

    @pytest.mark.asyncio
    async def test_list_sessions(self, engine):
        """Test listing sessions."""
        await engine.start()

        # Create multiple sessions
        session_id1 = engine.create_session("type1")
        session_id2 = engine.create_session("type2")

        sessions = engine.list_sessions()

        assert len(sessions) == 2
        session_ids = [s["session_id"] for s in sessions]
        assert session_id1 in session_ids
        assert session_id2 in session_ids

    def test_get_status(self, engine):
        """Test getting engine status."""
        status = engine.get_status()

        assert "status" in status
        assert "running" in status
        assert "active_sessions" in status
        assert "config" in status
        assert status["status"] == EngineStatus.DISABLED.value
        assert status["running"] is False
        assert status["active_sessions"] == 0

    def test_get_status_with_transcription_info(self, engine):
        """Test getting status with transcription service info."""
        status = engine.get_status()

        # Should include transcription info if service is available
        if engine.transcription_service:
            assert "transcription" in status

    def test_status_callbacks(self, engine):
        """Test status change callbacks."""
        callback_calls = []

        def status_callback(old_status, new_status):
            callback_calls.append((old_status, new_status))

        engine.add_status_callback(status_callback)

        # Trigger status change
        engine._set_status(EngineStatus.STARTING)

        assert len(callback_calls) == 1
        assert callback_calls[0] == (EngineStatus.DISABLED, EngineStatus.STARTING)

        # Remove callback
        engine.remove_status_callback(status_callback)
        engine._set_status(EngineStatus.RUNNING)

        # Should not have been called again
        assert len(callback_calls) == 1

    def test_error_callbacks(self, engine):
        """Test error callbacks."""
        callback_calls = []

        def error_callback(error):
            callback_calls.append(error)

        engine.add_error_callback(error_callback)

        # Trigger error
        test_error = Exception("Test error")
        engine._handle_error(test_error)

        assert len(callback_calls) == 1
        assert callback_calls[0] == test_error
        assert engine.status == EngineStatus.ERROR

        # Remove callback
        engine.remove_error_callback(error_callback)
        engine._handle_error(Exception("Another error"))

        # Should not have been called again
        assert len(callback_calls) == 1

    def test_is_healthy_true(self, engine):
        """Test health check when engine is healthy."""
        engine.status = EngineStatus.RUNNING
        assert engine.is_healthy() is True

    def test_is_healthy_false_bad_status(self, engine):
        """Test health check when engine status is bad."""
        engine.status = EngineStatus.ERROR
        assert engine.is_healthy() is False

    def test_is_healthy_false_no_service(self, engine):
        """Test health check when transcription service is unavailable."""
        engine.status = EngineStatus.RUNNING
        engine.transcription_service = None
        assert engine.is_healthy() is False

    def test_is_healthy_false_service_unavailable(self, engine):
        """Test health check when transcription service is not available."""
        engine.status = EngineStatus.RUNNING
        engine.transcription_service.is_available.return_value = False
        assert engine.is_healthy() is False

    def test_status_change_no_duplicate(self, engine):
        """Test that setting same status doesn't trigger callbacks."""
        callback_calls = []

        def status_callback(old_status, new_status):
            callback_calls.append((old_status, new_status))

        engine.add_status_callback(status_callback)

        # Set same status
        engine._set_status(EngineStatus.DISABLED)

        # Should not trigger callback
        assert len(callback_calls) == 0

    def test_callback_error_handling(self, engine):
        """Test that callback errors don't break the engine."""

        def bad_callback(old_status, new_status):
            raise Exception("Callback error")

        engine.add_status_callback(bad_callback)

        # Should not raise exception
        engine._set_status(EngineStatus.STARTING)
        assert engine.status == EngineStatus.STARTING

    @pytest.mark.asyncio
    async def test_engine_concurrent_sessions(self, engine):
        """Test handling multiple concurrent sessions."""
        await engine.start()

        # Create multiple sessions
        session_ids = []
        for i in range(3):
            session_id = engine.create_session(f"type_{i}")
            session_ids.append(session_id)

        # Start all sessions
        for session_id in session_ids:
            await engine.start_session(session_id)

        # Verify all sessions are active
        sessions = engine.list_sessions()
        assert len(sessions) == 3

        # Stop all sessions
        for session_id in session_ids:
            await engine.stop_session(session_id)

        assert len(engine._active_sessions) == 0

    def test_engine_session_id_uniqueness(self, engine):
        """Test that session IDs are unique."""
        engine._running = True

        session_ids = set()
        for i in range(10):
            session_id = engine.create_session()
            assert session_id not in session_ids
            session_ids.add(session_id)

    @pytest.mark.asyncio
    async def test_engine_graceful_shutdown_with_sessions(self, engine):
        """Test graceful shutdown with active sessions."""
        await engine.start()

        # Create and start sessions
        session_ids = []
        for i in range(2):
            session_id = engine.create_session()
            await engine.start_session(session_id)
            session_ids.append(session_id)

        # Shutdown should stop all sessions
        engine.shutdown()
        await engine.stop()

        assert len(engine._active_sessions) == 0
        assert engine._shutdown_event.is_set()

    def test_engine_max_sessions_limit(self, engine):
        """Test engine behavior with many sessions."""
        engine._running = True

        # Create many sessions
        session_ids = []
        for i in range(100):
            session_id = engine.create_session()
            session_ids.append(session_id)

        assert len(engine._active_sessions) == 100
        assert len(set(session_ids)) == 100  # All unique

    @pytest.mark.asyncio
    async def test_engine_session_cleanup_on_error(self, engine):
        """Test session cleanup when errors occur."""
        await engine.start()
        session_id = engine.create_session()

        # Simulate session error
        session = engine.get_session(session_id)
        session._handle_error(Exception("Test error"))

        # Session should still exist but be in error state
        assert session_id in engine._active_sessions
        assert session.status.value == "error"

    def test_engine_callback_management(self, engine):
        """Test adding and removing multiple callbacks."""
        status_callbacks = []
        error_callbacks = []

        # Create multiple callbacks
        for i in range(3):

            def status_cb(old, new, idx=i):
                status_callbacks.append((idx, old, new))

            def error_cb(error, idx=i):
                error_callbacks.append((idx, error))

            engine.add_status_callback(status_cb)
            engine.add_error_callback(error_cb)

        # Trigger status callback only
        engine._set_status(engine.status.__class__.STARTING)
        assert len(status_callbacks) == 3

        # Trigger error callback (this also changes status, so we'll get more status callbacks)
        engine._handle_error(Exception("Test"))
        assert len(error_callbacks) == 3
        # Status callbacks will be called twice: once for STARTING and once for ERROR
        assert len(status_callbacks) == 6

    def test_engine_configuration_access(self, engine):
        """Test accessing engine configuration."""
        assert hasattr(engine, "config")
        assert engine.config is not None

        status = engine.get_status()
        assert "config" in status
        assert isinstance(status["config"], dict)

    @pytest.mark.asyncio
    async def test_engine_restart_behavior(self, engine):
        """Test engine restart behavior."""
        # Start engine
        await engine.start()
        assert engine.status.value == "running"

        # Stop engine
        await engine.stop()
        assert engine.status.value == "disabled"

        # Restart engine
        await engine.start()
        assert engine.status.value == "running"
        assert engine._running is True

    def test_engine_thread_safety_simulation(self, engine):
        """Test engine behavior under simulated concurrent access."""
        import threading
        import time

        results = []

        def create_sessions():
            try:
                engine._running = True
                for i in range(5):
                    session_id = engine.create_session(f"thread_session_{i}")
                    results.append(session_id)
                    time.sleep(0.001)  # Small delay
            except Exception as e:
                results.append(f"error: {e}")

        # Create multiple threads
        threads = []
        for i in range(3):
            thread = threading.Thread(target=create_sessions)
            threads.append(thread)
            thread.start()

        # Wait for all threads
        for thread in threads:
            thread.join()

        # Check results
        session_ids = [r for r in results if not str(r).startswith("error")]
        assert len(session_ids) == 15  # 3 threads * 5 sessions each
        assert len(set(session_ids)) == 15  # All unique
