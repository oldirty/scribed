"""Test API server functionality."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from fastapi.testclient import TestClient

from scribed.api.server import APIServer
from scribed.config import Config
from scribed.daemon import ScribedDaemon, DaemonStatus


class TestAPIServer:
    """Test APIServer class."""
    
    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return Config(
            api={"host": "127.0.0.1", "port": 8081}
        )
    
    @pytest.fixture
    def daemon(self, config):
        """Create mock daemon."""
        daemon = Mock(spec=ScribedDaemon)
        daemon._running = False
        daemon.get_status.return_value = {
            "status": DaemonStatus.IDLE.value,
            "running": False,
            "config": {
                "source_mode": "file",
                "api_port": 8081,
                "transcription_provider": "whisper"
            }
        }
        return daemon
    
    @pytest.fixture
    def api_server(self, config, daemon):
        """Create API server instance."""
        return APIServer(config, daemon)
    
    @pytest.fixture
    def client(self, api_server):
        """Create test client."""
        return TestClient(api_server.app)
    
    def test_init(self, api_server, config, daemon):
        """Test API server initialization."""
        assert api_server.config == config
        assert api_server.daemon == daemon
        assert api_server.app is not None
        assert api_server.server is None
    
    def test_get_status_endpoint(self, client, daemon):
        """Test /status endpoint."""
        response = client.get("/status")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "idle"
        assert data["running"] is False
        daemon.get_status.assert_called_once()
    
    def test_health_check_endpoint(self, client):
        """Test /health endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "scribed"
    
    def test_start_transcription_not_running(self, client, daemon):
        """Test /start endpoint when daemon is not running."""
        daemon._running = False
        response = client.post("/start", json={"mode": "test"})
        assert response.status_code == 200
        data = response.json()
        assert "Transcription started" in data["message"]
        assert data["mode"] == "test"
    
    def test_start_transcription_already_running(self, client, daemon):
        """Test /start endpoint when daemon is already running."""
        daemon._running = True
        response = client.post("/start", json={})
        assert response.status_code == 200
        data = response.json()
        assert "already running" in data["message"]
    
    def test_stop_transcription(self, client):
        """Test /stop endpoint."""
        response = client.post("/stop", json={"save_output": True})
        assert response.status_code == 200
        data = response.json()
        assert "Transcription stopped" in data["message"]
        assert data["output_saved"] is True
    
    def test_stop_transcription_no_save(self, client):
        """Test /stop endpoint without saving output."""
        response = client.post("/stop", json={"save_output": False})
        assert response.status_code == 200
        data = response.json()
        assert data["output_saved"] is False
    
    def test_transcribe_endpoint_not_implemented(self, client):
        """Test /transcribe endpoint (not yet implemented)."""
        response = client.post("/transcribe")
        assert response.status_code == 501
        data = response.json()
        assert "not yet implemented" in data["message"]
    
    def test_get_job_status(self, client):
        """Test /jobs/{job_id} endpoint."""
        job_id = "test-job-123"
        response = client.get(f"/jobs/{job_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == job_id
        assert data["status"] == "pending"
        assert data["progress"] == 0.0
    
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
