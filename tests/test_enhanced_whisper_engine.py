"""Tests for the enhanced Whisper transcription engine."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from src.scribed.transcription.enhanced_whisper_engine import EnhancedWhisperEngine
from src.scribed.transcription.base import TranscriptionResult, TranscriptionStatus


class TestEnhancedWhisperEngine:
    """Test cases for EnhancedWhisperEngine."""

    def test_init_default_config(self):
        """Test initialization with default configuration."""
        config = {}
        engine = EnhancedWhisperEngine(config)
        
        assert engine.model_name == "base"
        assert engine.language is None
        assert engine.device == "auto"
        assert engine.backend == "auto"
        assert engine._model is None
        assert engine._active_backend is None

    def test_init_custom_config(self):
        """Test initialization with custom configuration."""
        config = {
            "model": "small",
            "language": "en-US",
            "device": "cpu",
            "backend": "faster"
        }
        engine = EnhancedWhisperEngine(config)
        
        assert engine.model_name == "small"
        assert engine.language == "en"  # Should be normalized from en-US
        assert engine.device == "cpu"
        assert engine.backend == "faster"

    def test_language_code_normalization(self):
        """Test language code normalization."""
        test_cases = [
            ("en-US", "en"),
            ("en-GB", "en"),
            ("es-ES", "es"),
            ("fr-FR", "fr"),
            ("de-DE", "de"),
            ("zh-CN", "zh"),
            ("pt-BR", "pt"),
            ("en", "en"),  # No change needed
            ("fr", "fr"),  # No change needed
            (None, None),  # Handle None
        ]
        
        for input_lang, expected in test_cases:
            config = {"language": input_lang}
            engine = EnhancedWhisperEngine(config)
            assert engine.language == expected

    @patch('src.scribed.transcription.enhanced_whisper_engine.EnhancedWhisperEngine._check_available_backends')
    def test_backend_availability_check(self, mock_check_backends):
        """Test backend availability checking."""
        mock_check_backends.return_value = {"faster": Mock(), "openai": Mock()}
        
        config = {}
        engine = EnhancedWhisperEngine(config)
        
        assert "faster" in engine._backends
        assert "openai" in engine._backends
        mock_check_backends.assert_called_once()

    def test_check_available_backends_openai_only(self):
        """Test backend checking when only openai-whisper is available."""
        with patch('builtins.__import__') as mock_import:
            # Mock openai-whisper available, faster-whisper not
            def import_side_effect(name, *args, **kwargs):
                if name == 'whisper':
                    return Mock()
                elif name == 'faster_whisper':
                    raise ImportError("No module named 'faster_whisper'")
                return __import__(name, *args, **kwargs)
            
            mock_import.side_effect = import_side_effect
            
            engine = EnhancedWhisperEngine({})
            backends = engine._check_available_backends()
            
            assert "openai" in backends
            assert "faster" not in backends

    def test_check_available_backends_faster_only(self):
        """Test backend checking when only faster-whisper is available."""
        with patch('builtins.__import__') as mock_import:
            # Mock faster-whisper available, openai-whisper not
            def import_side_effect(name, *args, **kwargs):
                if name == 'whisper':
                    raise ImportError("No module named 'whisper'")
                elif name == 'faster_whisper':
                    return Mock()
                return __import__(name, *args, **kwargs)
            
            mock_import.side_effect = import_side_effect
            
            engine = EnhancedWhisperEngine({})
            backends = engine._check_available_backends()
            
            assert "faster" in backends
            assert "openai" not in backends

    def test_check_available_backends_none(self):
        """Test backend checking when no backends are available."""
        with patch('builtins.__import__') as mock_import:
            # Mock both backends unavailable
            def import_side_effect(name, *args, **kwargs):
                if name in ['whisper', 'faster_whisper']:
                    raise ImportError(f"No module named '{name}'")
                return __import__(name, *args, **kwargs)
            
            mock_import.side_effect = import_side_effect
            
            engine = EnhancedWhisperEngine({})
            backends = engine._check_available_backends()
            
            assert len(backends) == 0

    def test_is_available_with_backends(self):
        """Test is_available when backends are present."""
        with patch.object(EnhancedWhisperEngine, '_check_available_backends') as mock_check:
            mock_check.return_value = {"faster": Mock()}
            
            engine = EnhancedWhisperEngine({})
            assert engine.is_available() is True

    def test_is_available_no_backends(self):
        """Test is_available when no backends are present."""
        with patch.object(EnhancedWhisperEngine, '_check_available_backends') as mock_check:
            mock_check.return_value = {}
            
            engine = EnhancedWhisperEngine({})
            assert engine.is_available() is False

    def test_get_supported_formats(self):
        """Test getting supported audio formats."""
        engine = EnhancedWhisperEngine({})
        formats = engine.get_supported_formats()
        
        expected_formats = [".wav", ".mp3", ".mp4", ".mpeg", ".mpga", ".m4a", ".webm", ".flac", ".ogg"]
        assert formats == expected_formats

    def test_get_model_info(self):
        """Test getting model information."""
        config = {
            "model": "small",
            "language": "en-US",
            "device": "cpu",
            "backend": "faster"
        }
        
        with patch.object(EnhancedWhisperEngine, '_check_available_backends') as mock_check:
            mock_check.return_value = {"faster": Mock(), "openai": Mock()}
            
            engine = EnhancedWhisperEngine(config)
            info = engine.get_model_info()
            
            assert info["engine"] == "enhanced_whisper"
            assert info["model"] == "small"
            assert info["language"] == "en"
            assert info["device"] == "cpu"
            assert info["backend"] == "not_loaded"
            assert info["available_backends"] == ["faster", "openai"]
            assert info["available"] is True

    @pytest.mark.asyncio
    async def test_transcribe_file_no_backends(self):
        """Test transcription when no backends are available."""
        with patch.object(EnhancedWhisperEngine, '_check_available_backends') as mock_check:
            mock_check.return_value = {}
            
            engine = EnhancedWhisperEngine({})
            
            # Create a temporary audio file
            audio_file = Path("/tmp/test.wav")
            
            with patch.object(engine, 'validate_audio_file', return_value=True):
                result = await engine.transcribe_file(audio_file)
                
                assert result.status == TranscriptionStatus.FAILED
                assert "No Whisper backends available" in result.error

    @pytest.mark.asyncio
    async def test_transcribe_file_invalid_file(self):
        """Test transcription with invalid audio file."""
        with patch.object(EnhancedWhisperEngine, '_check_available_backends') as mock_check:
            mock_check.return_value = {"faster": Mock()}
            
            engine = EnhancedWhisperEngine({})
            
            audio_file = Path("/tmp/nonexistent.wav")
            
            with patch.object(engine, 'validate_audio_file', return_value=False):
                result = await engine.transcribe_file(audio_file)
                
                assert result.status == TranscriptionStatus.FAILED
                assert result.error == "Invalid audio file"

    @pytest.mark.asyncio
    async def test_transcribe_stream_not_implemented(self):
        """Test that streaming transcription returns not implemented."""
        engine = EnhancedWhisperEngine({})
        
        result = await engine.transcribe_stream(b"fake_audio_data")
        
        assert result.status == TranscriptionStatus.FAILED
        assert "not yet implemented" in result.error
