"""Enhanced Whisper transcription engine with multiple backend support."""

import time
from pathlib import Path
from typing import List, Optional, Union

from .base import TranscriptionEngine, TranscriptionResult, TranscriptionSegment, TranscriptionStatus


class EnhancedWhisperEngine(TranscriptionEngine):
    """Enhanced Whisper transcription engine with multiple backend support."""
    
    def __init__(self, config: dict) -> None:
        """Initialize the Enhanced Whisper engine.
        
        Args:
            config: Configuration with keys:
                - model: Whisper model name (tiny, base, small, medium, large)
                - language: Language code (optional, auto-detect if None)
                - device: Device to use (cpu, cuda, auto)
                - backend: Preferred backend (auto, openai, faster)
        """
        super().__init__(config)
        self.model_name = config.get("model", "base")
        self.language = self._normalize_language_code(config.get("language"))
        self.device = config.get("device", "auto")
        self.backend = config.get("backend", "auto")
        self._model = None
        self._active_backend = None
        
        # Check available backends
        self._backends = self._check_available_backends()
        self.logger.info(f"Available Whisper backends: {list(self._backends.keys())}")
        
    def _normalize_language_code(self, language: Optional[str]) -> Optional[str]:
        """Normalize language codes for different backends."""
        if not language:
            return None
        
        # Map common language codes to the format expected by Whisper
        language_map = {
            "en-US": "en",
            "en-GB": "en", 
            "es-ES": "es",
            "fr-FR": "fr",
            "de-DE": "de",
            "it-IT": "it",
            "pt-BR": "pt",
            "ru-RU": "ru",
            "ja-JP": "ja",
            "ko-KR": "ko",
            "zh-CN": "zh",
            "zh-TW": "zh",
        }
        
        # Return mapped language or original if no mapping found
        return language_map.get(language, language)
        
    def _check_available_backends(self) -> dict:
        """Check which Whisper backends are available."""
        backends = {}
        
        # Check openai-whisper
        try:
            import whisper
            backends["openai"] = whisper
            self.logger.info("OpenAI Whisper backend available")
        except ImportError:
            self.logger.warning("OpenAI Whisper not available")
        
        # Check faster-whisper
        try:
            from faster_whisper import WhisperModel
            backends["faster"] = WhisperModel
            self.logger.info("Faster Whisper backend available")
        except ImportError:
            self.logger.warning("Faster Whisper not available")
        
        return backends
    
    def _load_model(self):
        """Load the Whisper model with the best available backend."""
        if self._model is not None:
            return
        
        if not self._backends:
            raise RuntimeError("No Whisper backends available")
        
        # Determine which backend to use
        if self.backend == "auto":
            # Prefer faster-whisper if available, fallback to openai
            backend_order = ["faster", "openai"]
        elif self.backend in self._backends:
            backend_order = [self.backend]
        else:
            raise ValueError(f"Requested backend '{self.backend}' not available")
        
        last_error = None
        for backend_name in backend_order:
            if backend_name not in self._backends:
                continue
                
            try:
                if backend_name == "faster":
                    self._load_faster_whisper()
                elif backend_name == "openai":
                    self._load_openai_whisper()
                
                self._active_backend = backend_name
                self.logger.info(f"Successfully loaded {backend_name} Whisper backend")
                return
                
            except Exception as e:
                self.logger.warning(f"Failed to load {backend_name} backend: {e}")
                last_error = e
                continue
        
        raise RuntimeError(f"Failed to load any Whisper backend. Last error: {last_error}")
    
    def _load_faster_whisper(self):
        """Load faster-whisper model."""
        from faster_whisper import WhisperModel
        
        self.logger.info(f"Loading Faster Whisper model: {self.model_name}")
        
        # Map device names
        device = "cpu" if self.device in ["cpu", "auto"] else self.device
        
        self._model = WhisperModel(
            self.model_name,
            device=device,
            compute_type="float32"  # Use float32 for better compatibility
        )
        
    def _load_openai_whisper(self):
        """Load openai-whisper model."""
        import whisper
        import torch
        import os
        
        self.logger.info(f"Loading OpenAI Whisper model: {self.model_name}")
        
        # Try to handle potential model corruption
        cache_dir = os.path.expanduser("~/.cache/whisper")
        
        try:
            self._model = whisper.load_model(self.model_name, device=self.device)
        except Exception as e:
            self.logger.warning(f"Model loading failed: {e}")
            
            # Try clearing cache and reloading
            model_file = f"{self.model_name}.pt"
            model_path = os.path.join(cache_dir, model_file)
            
            if os.path.exists(model_path):
                self.logger.info("Removing potentially corrupted model file")
                try:
                    os.remove(model_path)
                except OSError:
                    pass
            
            # Force re-download
            self._model = whisper.load_model(self.model_name, device=self.device, download_root=cache_dir)
    
    async def transcribe_file(self, audio_file_path: Union[str, Path]) -> TranscriptionResult:
        """Transcribe an audio file using the best available Whisper backend."""
        if not self.validate_audio_file(audio_file_path):
            return TranscriptionResult(
                text="",
                segments=[],
                status=TranscriptionStatus.FAILED,
                error="Invalid audio file"
            )
        
        if not self._backends:
            return TranscriptionResult(
                text="",
                segments=[],
                status=TranscriptionStatus.FAILED,
                error="No Whisper backends available"
            )
        
        try:
            # Load model in thread pool to avoid blocking
            await self.run_sync_in_thread(self._load_model)
            
            # Run transcription in thread pool
            start_time = time.time()
            
            if self._active_backend == "faster":
                result = await self.run_sync_in_thread(
                    self._transcribe_faster, str(audio_file_path)
                )
            elif self._active_backend == "openai":
                result = await self.run_sync_in_thread(
                    self._transcribe_openai, str(audio_file_path)
                )
            else:
                raise RuntimeError(f"Unknown active backend: {self._active_backend}")
            
            processing_time = time.time() - start_time
            
            # Convert result to our format
            segments = []
            if "segments" in result:
                for segment in result["segments"]:
                    segments.append(TranscriptionSegment(
                        text=segment["text"].strip(),
                        start_time=segment["start"],
                        end_time=segment["end"],
                        confidence=segment.get("confidence", segment.get("avg_logprob"))
                    ))
            
            return TranscriptionResult(
                text=result["text"].strip(),
                segments=segments,
                language=result.get("language"),
                processing_time=processing_time,
                status=TranscriptionStatus.COMPLETED
            )
            
        except Exception as e:
            self.logger.error(f"Whisper transcription failed: {e}")
            return TranscriptionResult(
                text="",
                segments=[],
                status=TranscriptionStatus.FAILED,
                error=str(e)
            )
    
    def _transcribe_faster(self, audio_file_path: str) -> dict:
        """Transcribe using faster-whisper."""
        self.logger.info(f"Transcribing with Faster Whisper: {audio_file_path}")
        
        if self._model is None:
            raise RuntimeError("Model not loaded")
        
        segments, info = self._model.transcribe(
            audio_file_path,
            language=self.language,
            word_timestamps=False
        )
        
        # Convert to compatible format
        text_segments = []
        full_text = ""
        
        for segment in segments:
            text_segments.append({
                "text": segment.text,
                "start": segment.start,
                "end": segment.end,
                "confidence": getattr(segment, 'avg_logprob', None)
            })
            full_text += segment.text
        
        return {
            "text": full_text,
            "segments": text_segments,
            "language": info.language
        }
    
    def _transcribe_openai(self, audio_file_path: str) -> dict:
        """Transcribe using openai-whisper."""
        self.logger.info(f"Transcribing with OpenAI Whisper: {audio_file_path}")
        
        if self._model is None:
            raise RuntimeError("Model not loaded")
        
        result = self._model.transcribe(
            audio_file_path,
            language=self.language,
            verbose=False,
            word_timestamps=False
        )
        
        return result
    
    async def transcribe_stream(self, audio_data: bytes) -> TranscriptionResult:
        """Transcribe streaming audio data."""
        # Enhanced streaming support could be added here
        return TranscriptionResult(
            text="",
            segments=[],
            status=TranscriptionStatus.FAILED,
            error="Streaming transcription not yet implemented"
        )
    
    def get_supported_formats(self) -> List[str]:
        """Get supported audio formats."""
        return [".wav", ".mp3", ".mp4", ".mpeg", ".mpga", ".m4a", ".webm", ".flac", ".ogg"]
    
    def is_available(self) -> bool:
        """Check if any Whisper backend is available."""
        return len(self._backends) > 0
    
    def get_model_info(self) -> dict:
        """Get information about the current model."""
        return {
            "engine": "enhanced_whisper",
            "model": self.model_name,
            "language": self.language or "auto-detect",
            "device": self.device,
            "backend": self._active_backend or "not_loaded",
            "available_backends": list(self._backends.keys()),
            "available": self.is_available()
        }
