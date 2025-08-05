"""Test API server functionality."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from fastapi.testclient import TestClient

from scribed.api.server import APIServer
from scribed.config import Config
from scribed.core.engine import ScribedEngine, EngineStatus
from scribed.core.session import TranscriptionSession, SessionStatus


class TestAPIServer:
    """Test APIServer class."""

    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return Config(api={"host": "127.0.0.1", "port": 8081})

    @pytest.fixture
    def engine(self, config):
        """Create mock engine."""
        engine = Mock(spec=ScribedEngine)
        engine.status = EngineStatus.IDLE
        engine._running = False
        engine.get_status.return_value = {
            "status": EngineStatus.IDLE.value,
            "running": False,
            "active_sessions": 0,
            "config": {
                "source_mode": "file",
                "transcription_provider": "whisper",
            },
        }
        engine.is_healthy.return_value = True
        engine.list_sessions.return_value = []
        engine.transcription_service = Mock()
        engine.transcription_service.is_available.return_value = True
        return engine

    @pytest.fixture
    def api_server(self, config, engine):
        """Create API server instance."""
        return APIServer(config, engine)

    @pytest.fixture
    def client(self, api_server):
        """Create test client."""
        return TestClient(api_server.app)

    def test_init(self, api_server, config, engine):
        """Test API server initialization."""
        assert api_server.config == config
        assert api_server.engine == engine
        assert api_server.app is not None
        assert api_server.server is None

    def test_get_status_endpoint(self, client, engine):
        """Test /status endpoint."""
        response = client.get("/status")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "idle"
        assert data["running"] is False
        engine.get_status.assert_called_once()

    def test_health_check_endpoint(self, client, engine):
        """Test /health endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "scribed"
        engine.is_healthy.assert_called_once()

    def test_create_session(self, client, engine):
        """Test /sessions POST endpoint."""
        engine.create_session.return_value = "session_123"
        response = client.post("/sessions", json={"session_type": "test"})
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == "session_123"
        assert data["status"] == "created"
        assert "created successfully" in data["message"]
        engine.create_session.assert_called_once_with(
            session_type="test", config_overrides=None
        )

    def test_list_sessions(self, client, engine):
        """Test /sessions GET endpoint."""
        mock_sessions = [
            {"session_id": "session_1", "status": "active"},
            {"session_id": "session_2", "status": "completed"},
        ]
        engine.list_sessions.return_value = mock_sessions
        response = client.get("/sessions")
        assert response.status_code == 200
        data = response.json()
        assert data["sessions"] == mock_sessions
        engine.list_sessions.assert_called_once()

    def test_get_session_status(self, client, engine):
        """Test /sessions/{session_id} GET endpoint."""
        mock_session = Mock(spec=TranscriptionSession)
        mock_session.get_status_info.return_value = {
            "session_id": "session_123",
            "status": "active",
            "running": True,
        }
        engine.get_session.return_value = mock_session

        response = client.get("/sessions/session_123")
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == "session_123"
        assert data["status"] == "active"
        engine.get_session.assert_called_once_with("session_123")

    def test_get_session_status_not_found(self, client, engine):
        """Test /sessions/{session_id} GET endpoint when session not found."""
        engine.get_session.return_value = None
        response = client.get("/sessions/nonexistent")
        assert response.status_code == 404
        assert "Session not found" in response.json()["detail"]

    def test_start_session(self, client, engine):
        """Test /sessions/{session_id}/start POST endpoint."""
        engine.start_session = AsyncMock()
        response = client.post("/sessions/session_123/start")
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == "session_123"
        assert data["status"] == "started"
        assert "started successfully" in data["message"]

    def test_stop_session(self, client, engine):
        """Test /sessions/{session_id}/stop POST endpoint."""
        engine.stop_session = AsyncMock()
        response = client.post("/sessions/session_123/stop")
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == "session_123"
        assert data["status"] == "stopped"
        assert "stopped successfully" in data["message"]

    @pytest.mark.asyncio
    async def test_start_server(self, api_server):
        """Test starting the API server."""
        with patch("scribed.api.server.uvicorn.Server") as mock_server_class:
            mock_server = AsyncMock()
            mock_server_class.return_value = mock_server

            await api_server.start()

            # Verify server was created and started
            mock_server_class.assert_called_once()
            assert api_server.server == mock_server

    @pytest.mark.asyncio
    async def test_stop_server(self, api_server):
        """Test stopping the API server."""
        # Setup mock server
        mock_server = AsyncMock()
        mock_server.should_exit = False
        api_server.server = mock_server

        await api_server.stop()

        # Verify server was signaled to stop
        assert mock_server.should_exit is True

    @pytest.mark.asyncio
    async def test_stop_server_no_server(self, api_server):
        """Test stopping when no server is running."""
        # Should not raise exception
        await api_server.stop()
        assert api_server.server is None
