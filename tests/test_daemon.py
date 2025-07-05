"""Test daemon functionality."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch

from scribed.daemon import ScribedDaemon, DaemonStatus
from scribed.config import Config
from .mocks import MockAsyncWakeWordEngine, MockAsyncMicrophoneInput


class TestScribedDaemon:
    """Test ScribedDaemon class."""

    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return Config(
            source_mode="file",
            api={
                "host": "127.0.0.1",
                "port": 8081,
            },  # Use different port for tests # type: ignore
            output={
                "log_to_file": False
            },  # Disable file logging for tests # type: ignore
        )

    @pytest.fixture
    def daemon(self, config):
        """Create test daemon instance."""
        return ScribedDaemon(config)

    def test_init_default_config(self):
        """Test daemon initialization with default config."""
        with patch("scribed.daemon.Config.from_env") as mock_config:
            mock_config.return_value = Config()
            daemon = ScribedDaemon()
            assert daemon.status == DaemonStatus.DISABLED
            assert not daemon._running

    def test_init_custom_config(self, config):
        """Test daemon initialization with custom config."""
        daemon = ScribedDaemon(config)
        assert daemon.config == config
        assert daemon.status == DaemonStatus.DISABLED
        assert not daemon._running

    def test_get_status(self, daemon):
        """Test status reporting."""
        status = daemon.get_status()
        assert isinstance(status, dict)
        assert "status" in status
        assert "running" in status
        assert "config" in status
        assert status["status"] == DaemonStatus.DISABLED.value
        assert status["running"] is False

    @pytest.mark.asyncio
    async def test_start_file_mode(self, daemon):
        """Test starting daemon in file mode."""
        # Mock the components to avoid actual startup
        with patch("scribed.daemon.APIServer") as mock_api, patch(
            "scribed.daemon.FileWatcher"
        ) as mock_watcher:

            # Setup mocks
            mock_api_instance = AsyncMock()
            mock_watcher_instance = AsyncMock()
            mock_api.return_value = mock_api_instance
            mock_watcher.return_value = mock_watcher_instance

            # Start daemon with immediate shutdown
            daemon._shutdown_event.set()  # Signal shutdown immediately

            await daemon.start()

            # Verify components were created and started
            mock_api.assert_called_once_with(daemon.config, daemon)
            mock_api_instance.start.assert_called_once()
            mock_watcher.assert_called_once_with(daemon.config, daemon)
            mock_watcher_instance.start.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_microphone_mode(self):
        """Test starting daemon in microphone mode."""
        config = Config(source_mode="microphone")
        daemon = ScribedDaemon(config)

        with patch("scribed.daemon.APIServer") as mock_api, patch(
            "scribed.realtime.transcription_service.AsyncWakeWordEngine", MockAsyncWakeWordEngine
        ), patch(
            "scribed.realtime.transcription_service.AsyncMicrophoneInput", MockAsyncMicrophoneInput
        ), patch(
            "scribed.realtime.transcription_service.TranscriptionService"
        ) as mock_transcription:

            mock_api_instance = AsyncMock()
            mock_api.return_value = mock_api_instance
            
            # Mock transcription service
            mock_transcription_instance = Mock()
            mock_transcription_instance.is_available.return_value = True
            mock_transcription.return_value = mock_transcription_instance

            # Create a task that will set the shutdown event after a brief delay
            async def delayed_shutdown():
                await asyncio.sleep(0.2)  # Allow status to be set
                daemon._shutdown_event.set()

            shutdown_task = asyncio.create_task(delayed_shutdown())

            try:
                await daemon.start()
            finally:
                shutdown_task.cancel()

            # Verify API was started
            mock_api.assert_called_once_with(daemon.config, daemon)
            mock_api_instance.start.assert_called_once()
            # Status should be set to LISTENING_FOR_WAKE_WORD when in microphone mode
            assert daemon.status == DaemonStatus.LISTENING_FOR_WAKE_WORD

    @pytest.mark.asyncio
    async def test_start_already_running(self, daemon):
        """Test starting daemon when already running."""
        daemon._running = True

        # Should not raise exception, just log warning
        await daemon.start()

        # Status should remain as it was
        assert daemon._running is True

    @pytest.mark.asyncio
    async def test_stop(self, daemon):
        """Test stopping daemon."""
        # Setup mock components
        daemon.api_server = AsyncMock()
        daemon.file_watcher = AsyncMock()
        daemon._running = True

        await daemon.stop()

        # Verify components were stopped
        daemon.api_server.stop.assert_called_once()
        daemon.file_watcher.stop.assert_called_once()
        assert daemon._running is False
        assert daemon.status == DaemonStatus.DISABLED

    @pytest.mark.asyncio
    async def test_stop_not_running(self, daemon):
        """Test stopping daemon when not running."""
        # Should not raise exception
        await daemon.stop()
        assert daemon._running is False

    def test_shutdown(self, daemon):
        """Test shutdown signal."""
        assert not daemon._shutdown_event.is_set()
        daemon.shutdown()
        assert daemon._shutdown_event.is_set()

    def test_setup_signal_handlers(self, daemon):
        """Test signal handler setup."""
        with patch("scribed.daemon.signal.signal") as mock_signal:
            daemon.setup_signal_handlers()

            # Verify signal handlers were registered
            assert mock_signal.call_count == 2
            
            # Get the calls made to signal.signal
            calls = mock_signal.call_args_list
            
            # Verify SIGINT and SIGTERM were registered
            import signal
            signals_registered = [call[0][0] for call in calls]
            assert signal.SIGINT in signals_registered
            assert signal.SIGTERM in signals_registered
