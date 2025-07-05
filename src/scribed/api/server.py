"""REST API server for Scribed daemon."""

import asyncio
import logging
from typing import TYPE_CHECKING, Optional
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

if TYPE_CHECKING:
    from ..config import Config
    from ..daemon import ScribedDaemon

logger = logging.getLogger(__name__)


class StartTranscriptionRequest(BaseModel):
    """Request model for starting transcription."""

    mode: Optional[str] = None


class StopTranscriptionRequest(BaseModel):
    """Request model for stopping transcription."""

    save_output: bool = True


class TranscriptionJobResponse(BaseModel):
    """Response model for transcription job status."""

    job_id: str
    status: str
    progress: float
    result: Optional[str] = None
    error: Optional[str] = None


class APIServer:
    """FastAPI server for daemon control."""

    def __init__(self, config: "Config", daemon: "ScribedDaemon") -> None:
        """Initialize API server."""
        self.config = config
        self.daemon = daemon
        self.app = FastAPI(
            title="Scribed API",
            description="Audio transcription daemon API",
            version="0.1.0",
        )
        self.server: Optional[uvicorn.Server] = None
        self._setup_routes()

    def _setup_routes(self) -> None:
        """Set up API routes."""

        @self.app.get("/status")
        async def get_status():
            """Get daemon status."""
            return JSONResponse(self.daemon.get_status())

        @self.app.post("/start")
        async def start_transcription(request: StartTranscriptionRequest):
            """Start transcription service."""
            try:
                if self.daemon._running:
                    return JSONResponse(
                        {"message": "Transcription already running"}, status_code=200
                    )

                # For now, just return success - actual implementation pending
                return JSONResponse(
                    {
                        "message": "Transcription started",
                        "mode": request.mode or "default",
                    }
                )
            except Exception as e:
                logger.error(f"Error starting transcription: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/stop")
        async def stop_transcription(request: StopTranscriptionRequest):
            """Stop transcription service."""
            try:
                # For now, just return success - actual implementation pending
                return JSONResponse(
                    {
                        "message": "Transcription stopped",
                        "output_saved": request.save_output,
                    }
                )
            except Exception as e:
                logger.error(f"Error stopping transcription: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/transcribe")
        async def submit_transcription():
            """Submit audio for transcription."""
            # TODO: Implement file upload and transcription queueing
            return JSONResponse(
                {"message": "Transcription endpoint not yet implemented"},
                status_code=501,
            )

        @self.app.get("/jobs/{job_id}")
        async def get_job_status(job_id: str):
            """Get transcription job status."""
            # TODO: Implement job tracking
            return TranscriptionJobResponse(
                job_id=job_id, status="pending", progress=0.0
            )

        @self.app.get("/health")
        async def health_check():
            """Health check endpoint."""
            return JSONResponse({"status": "healthy", "service": "scribed"})

    async def start(self) -> None:
        """Start the API server."""
        config = uvicorn.Config(
            self.app,
            host=self.config.api.host,
            port=self.config.api.port,
            log_level="info" if self.config.api.debug else "warning",
            access_log=self.config.api.debug,
        )
        self.server = uvicorn.Server(config)

        logger.info(
            f"Starting API server on {self.config.api.host}:{self.config.api.port}"
        )

        # Start server in background task
        asyncio.create_task(self.server.serve())

    async def stop(self) -> None:
        """Stop the API server."""
        if self.server:
            logger.info("Stopping API server...")
            self.server.should_exit = True
            await asyncio.sleep(0.1)  # Give it a moment to shutdown gracefully
