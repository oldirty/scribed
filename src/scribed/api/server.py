"""REST API server for Scribed daemon."""

import asyncio
import logging
import tempfile
import numpy as np
import wave
from typing import TYPE_CHECKING, Optional, Dict, Any
import uvicorn
from fastapi import FastAPI, HTTPException, UploadFile, File
from .. import __version__
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from pathlib import Path

if TYPE_CHECKING:
    from ..config import Config
    from ..core.engine import ScribedEngine

logger = logging.getLogger(__name__)


class SessionRequest(BaseModel):
    """Request model for session operations."""

    session_type: Optional[str] = "default"
    config_overrides: Optional[Dict[str, Any]] = None


class TranscribeFileRequest(BaseModel):
    """Request model for file transcription."""

    provider: Optional[str] = None


class RecordToClipboardRequest(BaseModel):
    """Request model for recording audio and transcribing to clipboard."""

    duration: int = 10
    provider: Optional[str] = None


class SessionResponse(BaseModel):
    """Response model for session operations."""

    session_id: str
    status: str
    message: Optional[str] = None


class TranscriptionResponse(BaseModel):
    """Response model for transcription results."""

    success: bool
    text: Optional[str] = None
    processing_time: Optional[float] = None
    error: Optional[str] = None


class APIServer:
    """FastAPI server for Scribed engine control."""

    def __init__(self, config: "Config", engine: "ScribedEngine") -> None:
        """Initialize API server."""
        self.config = config
        self.engine = engine
        self.app = FastAPI(
            title="Scribed API",
            description="Audio transcription service API",
            version=__version__,
        )
        self.server: Optional[uvicorn.Server] = None
        self._setup_routes()

    def _setup_routes(self) -> None:
        """Set up API routes."""

        @self.app.get("/status")
        async def get_status():
            """Get engine status."""
            return JSONResponse(self.engine.get_status())

        @self.app.get("/health")
        async def health_check():
            """Health check endpoint."""
            return JSONResponse(
                {
                    "status": "healthy" if self.engine.is_healthy() else "unhealthy",
                    "service": "scribed",
                }
            )

        @self.app.post("/sessions")
        async def create_session(request: SessionRequest):
            """Create a new transcription session."""
            try:
                session_id = self.engine.create_session(
                    session_type=request.session_type or "default",
                    config_overrides=request.config_overrides,
                )
                return SessionResponse(
                    session_id=session_id,
                    status="created",
                    message="Session created successfully",
                )
            except Exception as e:
                logger.error(f"Error creating session: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/sessions")
        async def list_sessions():
            """List all active sessions."""
            try:
                sessions = self.engine.list_sessions()
                return JSONResponse({"sessions": sessions})
            except Exception as e:
                logger.error(f"Error listing sessions: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/sessions/{session_id}")
        async def get_session_status(session_id: str):
            """Get session status."""
            try:
                session = self.engine.get_session(session_id)
                if not session:
                    raise HTTPException(status_code=404, detail="Session not found")
                return JSONResponse(session.get_status_info())
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Error getting session status: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/sessions/{session_id}/start")
        async def start_session(session_id: str):
            """Start a transcription session."""
            try:
                await self.engine.start_session(session_id)
                return SessionResponse(
                    session_id=session_id,
                    status="started",
                    message="Session started successfully",
                )
            except ValueError as e:
                raise HTTPException(status_code=404, detail=str(e))
            except Exception as e:
                logger.error(f"Error starting session: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/sessions/{session_id}/stop")
        async def stop_session(session_id: str):
            """Stop a transcription session."""
            try:
                await self.engine.stop_session(session_id)
                return SessionResponse(
                    session_id=session_id,
                    status="stopped",
                    message="Session stopped successfully",
                )
            except Exception as e:
                logger.error(f"Error stopping session: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/transcribe/file")
        async def transcribe_file(
            file: UploadFile = File(...),
            request: TranscribeFileRequest = TranscribeFileRequest(),
        ):
            """Transcribe an uploaded audio file."""
            try:
                # Save uploaded file to temporary location
                with tempfile.NamedTemporaryFile(
                    suffix=Path(file.filename).suffix, delete=False
                ) as temp_file:
                    temp_path = Path(temp_file.name)
                    content = await file.read()
                    temp_file.write(content)

                try:
                    # Get transcription service from engine
                    service = self.engine.transcription_service
                    if not service or not service.is_available():
                        raise HTTPException(
                            status_code=503,
                            detail="Transcription service not available",
                        )

                    # Override provider if requested
                    if request.provider:
                        config = self.config.transcription.model_dump()
                        config["provider"] = request.provider
                        from ..transcription.service import TranscriptionService

                        service = TranscriptionService(config)

                    # Transcribe the file
                    result = await service.transcribe_file(temp_path)

                    if result.status.value == "completed":
                        return TranscriptionResponse(
                            success=True,
                            text=result.text,
                            processing_time=result.processing_time,
                        )
                    else:
                        return TranscriptionResponse(
                            success=False, error=f"Transcription failed: {result.error}"
                        )

                finally:
                    # Clean up temporary file
                    try:
                        temp_path.unlink()
                    except Exception:
                        pass

            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Error transcribing file: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/record-to-clipboard")
        async def record_to_clipboard(request: RecordToClipboardRequest):
            """Record audio and transcribe directly to clipboard."""
            try:
                # Import required modules for audio recording
                import sounddevice as sd
                from ..transcription.service import TranscriptionService
                from ..clipboard import set_clipboard_text, is_clipboard_available

                # Check clipboard availability
                if not is_clipboard_available():
                    return TranscriptionResponse(
                        success=False,
                        error="Clipboard functionality not available. On Linux, install xclip or xsel.",
                    )

                # Get config with optional provider override
                config = self.config.transcription.model_dump()
                if request.provider:
                    config["provider"] = request.provider

                logger.info(
                    f"Starting {request.duration}s recording for clipboard transcription"
                )
                logger.info(f"Using provider: {config['provider']}")

                # Recording parameters
                sample_rate = 16000
                channels = 1

                # Record audio
                audio_data = sd.rec(
                    int(request.duration * sample_rate),
                    samplerate=sample_rate,
                    channels=channels,
                    dtype=np.int16,
                )

                # Wait for recording to complete
                sd.wait()

                # Save to temporary file
                with tempfile.NamedTemporaryFile(
                    suffix=".wav", delete=False
                ) as temp_file:
                    temp_path = Path(temp_file.name)

                    # Write WAV file
                    with wave.open(str(temp_path), "wb") as wav_file:
                        wav_file.setnchannels(channels)
                        wav_file.setsampwidth(2)  # 16-bit
                        wav_file.setframerate(sample_rate)
                        wav_file.writeframes(audio_data.tobytes())

                try:
                    # Use engine's transcription service or create new one with override
                    service = self.engine.transcription_service
                    if request.provider:
                        service = TranscriptionService(config)

                    if not service or not service.is_available():
                        engine_info = (
                            service.get_engine_info()
                            if service
                            else "Service unavailable"
                        )
                        return TranscriptionResponse(
                            success=False,
                            error=f"Transcription service not available: {engine_info}",
                        )

                    # Transcribe the recording
                    result = await service.transcribe_file(temp_path)

                    if result.status.value == "completed":
                        # Copy to clipboard
                        if set_clipboard_text(result.text):
                            logger.info(
                                "Transcription copied to clipboard successfully"
                            )
                            return TranscriptionResponse(
                                success=True,
                                text=result.text,
                                processing_time=result.processing_time,
                            )
                        else:
                            return TranscriptionResponse(
                                success=False,
                                text=result.text,
                                error="Failed to copy to clipboard",
                            )
                    else:
                        return TranscriptionResponse(
                            success=False, error=f"Transcription failed: {result.error}"
                        )

                finally:
                    # Clean up temporary file
                    try:
                        temp_path.unlink()
                    except Exception:
                        pass

            except ImportError as e:
                if "sounddevice" in str(e):
                    error_msg = "sounddevice not installed. Install with: pip install sounddevice"
                else:
                    error_msg = f"Import error: {e}"
                logger.error(error_msg)
                return TranscriptionResponse(success=False, error=error_msg)
            except Exception as e:
                logger.error(f"Error in record_to_clipboard: {e}")
                return TranscriptionResponse(success=False, error=str(e))

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
