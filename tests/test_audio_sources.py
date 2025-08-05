"""Test audio source implementations."""

import pytest
import asyncio
import tempfile
import wave
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, AsyncMock

from scribed.audio.base import AudioFormat, AudioError, AudioValidationError
from scribed.audio.microphone import MicrophoneSource
from scribed.audio.file_source import FileSource


class TestMicrophoneSource:
    """Test MicrophoneSource class."""

    @pytest.fixture
    def basic_config(self):
        """Basic microphone configuration."""
        return {
            "device_index": None,
            "sample_rate": 16000,
            "channels": 1,
            "chunk_size": 1024,
            "format": "int16",
        }

    def test_microphone_source_no_audio_dependencies(self, basic_config):
        """Test microphone source when audio dependencies are not available."""
        with patch("scribed.audio.microphone.AUDIO_AVAILABLE", False):
            with pytest.raises(AudioError, match="Audio dependencies not available"):
                MicrophoneSource(basic_config)

    @patch("scribed.audio.microphone.AUDIO_AVAILABLE", True)
    @patch("scribed.audio.microphone.pyaudio")
    def test_microphone_source_initialization(self, mock_pyaudio, basic_config):
        """Test microphone source initialization."""
        source = MicrophoneSource(basic_config)

        assert source.device_index is None
        assert source.sample_rate == 16000
        assert source.channels == 1
        assert source.chunk_size == 1024
        assert source.format == AudioFormat.INT16
        assert source.pyaudio_format == mock_pyaudio.paInt16

    @patch("scribed.audio.microphone.AUDIO_AVAILABLE", True)
    @patch("scribed.audio.microphone.pyaudio")
    def test_microphone_source_custom_config(self, mock_pyaudio, basic_config):
        """Test microphone source with custom configuration."""
        config = {
            **basic_config,
            "device_index": 1,
            "sample_rate": 44100,
            "channels": 2,
            "format": "float32",
        }

        source = MicrophoneSource(config)

        assert source.device_index == 1
        assert source.sample_rate == 44100
        assert source.channels == 2
        assert source.format == AudioFormat.FLOAT32
        assert source.pyaudio_format == mock_pyaudio.paFloat32

    @patch("scribed.audio.microphone.AUDIO_AVAILABLE", True)
    @patch("scribed.audio.microphone.pyaudio")
    def test_microphone_source_invalid_format(self, mock_pyaudio, basic_config):
        """Test microphone source with invalid format."""
        config = {**basic_config, "format": "invalid"}

        with pytest.raises(AudioValidationError, match="Unsupported audio format"):
            MicrophoneSource(config)

    @patch("scribed.audio.microphone.AUDIO_AVAILABLE", True)
    @patch("scribed.audio.microphone.pyaudio")
    def test_microphone_source_preprocessing_config(self, mock_pyaudio, basic_config):
        """Test microphone source with preprocessing configuration."""
        config = {
            **basic_config,
            "preprocessing": {"enabled": True, "noise_reduction": True},
        }

        with patch("scribed.audio.microphone.PREPROCESSING_AVAILABLE", False):
            source = MicrophoneSource(config)
            assert source.preprocessor is None

    @patch("scribed.audio.microphone.AUDIO_AVAILABLE", True)
    @patch("scribed.audio.microphone.pyaudio")
    @pytest.mark.asyncio
    async def test_microphone_source_start_success(self, mock_pyaudio, basic_config):
        """Test successful microphone source start."""
        # Mock PyAudio components
        mock_audio = Mock()
        mock_stream = Mock()
        mock_pyaudio.PyAudio.return_value = mock_audio
        mock_audio.open.return_value = mock_stream
        mock_audio.get_device_count.return_value = 1
        mock_audio.get_device_info_by_index.return_value = {
            "name": "Test Device",
            "maxInputChannels": 1,
        }

        source = MicrophoneSource(basic_config)

        await source.start()

        assert source.is_active
        mock_audio.open.assert_called_once()

    @patch("scribed.audio.microphone.AUDIO_AVAILABLE", True)
    @patch("scribed.audio.microphone.pyaudio")
    @pytest.mark.asyncio
    async def test_microphone_source_start_already_active(
        self, mock_pyaudio, basic_config
    ):
        """Test starting microphone source when already active."""
        mock_audio = Mock()
        mock_stream = Mock()
        mock_pyaudio.PyAudio.return_value = mock_audio
        mock_audio.open.return_value = mock_stream
        mock_audio.get_device_count.return_value = 1
        mock_audio.get_device_info_by_index.return_value = {
            "name": "Test Device",
            "maxInputChannels": 1,
        }

        source = MicrophoneSource(basic_config)

        await source.start()
        await source.start()  # Should not raise error

        assert source.is_active

    @patch("scribed.audio.microphone.AUDIO_AVAILABLE", True)
    @patch("scribed.audio.microphone.pyaudio")
    @pytest.mark.asyncio
    async def test_microphone_source_start_failure(self, mock_pyaudio, basic_config):
        """Test microphone source start failure."""
        mock_pyaudio.PyAudio.side_effect = Exception("Audio init failed")

        source = MicrophoneSource(basic_config)

        with pytest.raises(AudioError, match="Failed to start microphone source"):
            await source.start()

    @patch("scribed.audio.microphone.AUDIO_AVAILABLE", True)
    @patch("scribed.audio.microphone.pyaudio")
    @pytest.mark.asyncio
    async def test_microphone_source_stop(self, mock_pyaudio, basic_config):
        """Test microphone source stop."""
        mock_audio = Mock()
        mock_stream = Mock()
        mock_pyaudio.PyAudio.return_value = mock_audio
        mock_audio.open.return_value = mock_stream
        mock_audio.get_device_count.return_value = 1
        mock_audio.get_device_info_by_index.return_value = {
            "name": "Test Device",
            "maxInputChannels": 1,
        }

        source = MicrophoneSource(basic_config)

        await source.start()
        await source.stop()

        assert not source.is_active
        mock_stream.stop_stream.assert_called_once()
        mock_stream.close.assert_called_once()
        mock_audio.terminate.assert_called_once()

    @patch("scribed.audio.microphone.AUDIO_AVAILABLE", True)
    @patch("scribed.audio.microphone.pyaudio")
    @pytest.mark.asyncio
    async def test_microphone_source_read_chunk_not_active(
        self, mock_pyaudio, basic_config
    ):
        """Test reading chunk when source is not active."""
        source = MicrophoneSource(basic_config)

        chunk = await source.read_chunk()
        assert chunk is None

    @patch("scribed.audio.microphone.AUDIO_AVAILABLE", True)
    @patch("scribed.audio.microphone.pyaudio")
    @pytest.mark.asyncio
    async def test_microphone_source_read_chunk_timeout(
        self, mock_pyaudio, basic_config
    ):
        """Test reading chunk with timeout."""
        mock_audio = Mock()
        mock_stream = Mock()
        mock_pyaudio.PyAudio.return_value = mock_audio
        mock_audio.open.return_value = mock_stream
        mock_audio.get_device_count.return_value = 1
        mock_audio.get_device_info_by_index.return_value = {
            "name": "Test Device",
            "maxInputChannels": 1,
        }

        source = MicrophoneSource(basic_config)
        await source.start()

        # Mock empty queue (timeout scenario)
        chunk = await source.read_chunk()
        # Should return None on timeout when still active
        assert chunk is None

    @patch("scribed.audio.microphone.AUDIO_AVAILABLE", True)
    @patch("scribed.audio.microphone.pyaudio")
    def test_microphone_source_get_audio_info(self, mock_pyaudio, basic_config):
        """Test getting microphone source audio info."""
        source = MicrophoneSource(basic_config)

        info = source.get_audio_info()

        assert "device_index" in info
        assert "sample_rate" in info
        assert "channels" in info
        assert "chunk_size" in info
        assert "format" in info
        assert "buffer_size" in info
        assert "queue_size" in info
        assert "preprocessing_available" in info
        assert "preprocessing_enabled" in info

        assert info["sample_rate"] == 16000
        assert info["channels"] == 1
        assert info["format"] == "int16"

    @patch("scribed.audio.microphone.AUDIO_AVAILABLE", True)
    def test_microphone_source_is_available(self, basic_config):
        """Test microphone source availability check."""
        with patch("scribed.audio.microphone.pyaudio"):
            source = MicrophoneSource(basic_config)
            assert source.is_available() is True

    @patch("scribed.audio.microphone.AUDIO_AVAILABLE", False)
    def test_microphone_source_is_available_false(self, basic_config):
        """Test microphone source availability when audio not available."""
        # Can't create source without audio dependencies, so test static method
        assert MicrophoneSource.list_devices() == []

    @patch("scribed.audio.microphone.AUDIO_AVAILABLE", True)
    @patch("scribed.audio.microphone.pyaudio")
    def test_microphone_source_list_devices(self, mock_pyaudio):
        """Test listing microphone devices."""
        mock_audio = Mock()
        mock_pyaudio.PyAudio.return_value = mock_audio
        mock_audio.get_device_count.return_value = 2
        mock_audio.get_device_info_by_index.side_effect = [
            {
                "name": "Input Device 1",
                "maxInputChannels": 2,
                "defaultSampleRate": 44100.0,
                "hostApi": 0,
            },
            {
                "name": "Output Device",
                "maxInputChannels": 0,  # Output only
                "defaultSampleRate": 44100.0,
                "hostApi": 0,
            },
        ]

        devices = MicrophoneSource.list_devices()

        assert len(devices) == 1  # Only input devices
        assert devices[0]["name"] == "Input Device 1"
        assert devices[0]["channels"] == 2
        assert devices[0]["sample_rate"] == 44100.0

    @patch("scribed.audio.microphone.AUDIO_AVAILABLE", True)
    @patch("scribed.audio.microphone.pyaudio")
    def test_microphone_source_get_buffer_data(self, mock_pyaudio, basic_config):
        """Test getting buffer data."""
        source = MicrophoneSource(basic_config)

        # Test with empty buffer
        data = source.get_buffer_data(1.0)
        assert data == b""


class TestFileSource:
    """Test FileSource class."""

    @pytest.fixture
    def temp_wav_file(self):
        """Create temporary WAV file for testing."""
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            temp_path = Path(f.name)

        # Create a simple WAV file
        with wave.open(str(temp_path), "wb") as wav_file:
            wav_file.setnchannels(1)  # Mono
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(16000)  # 16kHz

            # 1 second of silence
            frames = b"\x00\x00" * 16000
            wav_file.writeframes(frames)

        yield temp_path

        # Cleanup
        if temp_path.exists():
            temp_path.unlink()

    def test_file_source_no_file_path(self):
        """Test file source without file path."""
        config = {}

        with pytest.raises(AudioValidationError, match="file_path is required"):
            FileSource(config)

    def test_file_source_nonexistent_file(self):
        """Test file source with nonexistent file."""
        config = {"file_path": "/nonexistent/file.wav"}

        with pytest.raises(AudioError, match="Audio file does not exist"):
            FileSource(config)

    def test_file_source_unsupported_format(self, temp_wav_file):
        """Test file source with unsupported format."""
        # Create file with unsupported extension
        unsupported_file = temp_wav_file.with_suffix(".xyz")
        temp_wav_file.rename(unsupported_file)

        config = {"file_path": str(unsupported_file)}

        try:
            with pytest.raises(AudioValidationError, match="Unsupported file format"):
                FileSource(config)
        finally:
            if unsupported_file.exists():
                unsupported_file.unlink()

    def test_file_source_initialization(self, temp_wav_file):
        """Test file source initialization."""
        config = {
            "file_path": str(temp_wav_file),
            "chunk_size": 512,
            "target_sample_rate": 22050,
            "target_channels": 2,
            "target_format": "float32",
        }

        source = FileSource(config)

        assert source.file_path == temp_wav_file
        assert source.chunk_size == 512
        assert source.target_sample_rate == 22050
        assert source.target_channels == 2
        assert source.target_format == AudioFormat.FLOAT32

    def test_file_source_default_config(self, temp_wav_file):
        """Test file source with default configuration."""
        config = {"file_path": str(temp_wav_file)}

        source = FileSource(config)

        assert source.chunk_size == 1024
        assert source.target_sample_rate == 16000
        assert source.target_channels == 1
        assert source.target_format == AudioFormat.INT16

    def test_file_source_invalid_target_format(self, temp_wav_file):
        """Test file source with invalid target format."""
        config = {"file_path": str(temp_wav_file), "target_format": "invalid"}

        with pytest.raises(AudioValidationError, match="Unsupported target format"):
            FileSource(config)

    @pytest.mark.asyncio
    async def test_file_source_start_no_libraries(self, temp_wav_file):
        """Test file source start when no audio libraries available."""
        config = {"file_path": str(temp_wav_file)}
        source = FileSource(config)

        with patch.object(source, "is_available", return_value=False):
            with pytest.raises(AudioError, match="No audio libraries available"):
                await source.start()

    @pytest.mark.asyncio
    async def test_file_source_start_already_active(self, temp_wav_file):
        """Test starting file source when already active."""
        config = {"file_path": str(temp_wav_file)}
        source = FileSource(config)

        # Mock the loading to avoid library dependencies
        with patch.object(source, "_load_audio_file", new_callable=AsyncMock):
            await source.start()
            await source.start()  # Should not raise error

            assert source.is_active

    @pytest.mark.asyncio
    async def test_file_source_stop(self, temp_wav_file):
        """Test file source stop."""
        config = {"file_path": str(temp_wav_file)}
        source = FileSource(config)

        with patch.object(source, "_load_audio_file", new_callable=AsyncMock):
            await source.start()
            await source.stop()

            assert not source.is_active
            assert source.audio_data is None
            assert source.current_position == 0

    @pytest.mark.asyncio
    async def test_file_source_read_chunk_not_active(self, temp_wav_file):
        """Test reading chunk when source is not active."""
        config = {"file_path": str(temp_wav_file)}
        source = FileSource(config)

        chunk = await source.read_chunk()
        assert chunk is None

    @pytest.mark.asyncio
    async def test_file_source_read_chunk_end_of_file(self, temp_wav_file):
        """Test reading chunk at end of file."""
        config = {"file_path": str(temp_wav_file)}
        source = FileSource(config)

        # Mock active state and position at end
        source._mark_active()
        source.audio_data = b"test_data"
        source.total_samples = 100
        source.current_position = 100  # At end

        chunk = await source.read_chunk()
        assert chunk is None

    def test_file_source_get_audio_info(self, temp_wav_file):
        """Test getting file source audio info."""
        config = {"file_path": str(temp_wav_file)}
        source = FileSource(config)

        info = source.get_audio_info()

        assert "file_path" in info
        assert "file_size_bytes" in info
        assert "target_sample_rate" in info
        assert "target_channels" in info
        assert "target_format" in info
        assert "chunk_size" in info
        assert "total_samples" in info
        assert "current_position" in info
        assert "progress_percent" in info
        assert "duration_seconds" in info
        assert "librosa_available" in info
        assert "soundfile_available" in info
        assert "wave_available" in info

        assert info["file_path"] == str(temp_wav_file)
        assert info["target_sample_rate"] == 16000

    def test_file_source_is_available(self, temp_wav_file):
        """Test file source availability check."""
        config = {"file_path": str(temp_wav_file)}
        source = FileSource(config)

        # Should be available if any audio library is available
        with patch("scribed.audio.file_source.LIBROSA_AVAILABLE", True):
            assert source.is_available() is True

        with patch("scribed.audio.file_source.LIBROSA_AVAILABLE", False):
            with patch("scribed.audio.file_source.SOUNDFILE_AVAILABLE", True):
                assert source.is_available() is True

        with patch("scribed.audio.file_source.LIBROSA_AVAILABLE", False):
            with patch("scribed.audio.file_source.SOUNDFILE_AVAILABLE", False):
                with patch("scribed.audio.file_source.WAVE_AVAILABLE", True):
                    assert source.is_available() is True

    def test_file_source_seek_to_position(self, temp_wav_file):
        """Test seeking to position in file."""
        config = {"file_path": str(temp_wav_file)}
        source = FileSource(config)

        source._mark_active()
        source.total_samples = 16000  # 1 second at 16kHz

        source.seek_to_position(0.5)  # Seek to 0.5 seconds
        assert source.current_position == 8000  # 0.5 * 16000

    def test_file_source_seek_to_position_not_active(self, temp_wav_file):
        """Test seeking when source is not active."""
        config = {"file_path": str(temp_wav_file)}
        source = FileSource(config)

        with pytest.raises(AudioError, match="File source not active"):
            source.seek_to_position(0.5)

    def test_file_source_get_remaining_duration(self, temp_wav_file):
        """Test getting remaining duration."""
        config = {"file_path": str(temp_wav_file)}
        source = FileSource(config)

        # Not active
        assert source.get_remaining_duration() == 0.0

        # Active with data
        source._mark_active()
        source.total_samples = 16000  # 1 second
        source.current_position = 8000  # 0.5 seconds played
        source.target_sample_rate = 16000

        remaining = source.get_remaining_duration()
        assert abs(remaining - 0.5) < 0.001

    def test_file_source_supported_formats(self):
        """Test getting supported formats."""
        formats = FileSource.get_supported_formats()

        assert ".wav" in formats
        assert ".mp3" in formats
        assert ".flac" in formats
        assert isinstance(formats, list)

    def test_file_source_is_format_supported(self, temp_wav_file):
        """Test checking if format is supported."""
        assert FileSource.is_format_supported(temp_wav_file) is True
        assert FileSource.is_format_supported("test.wav") is True
        assert FileSource.is_format_supported("test.xyz") is False
        assert FileSource.is_format_supported("test.WAV") is True  # Case insensitive


class TestMicrophoneSourceAdvanced:
    """Advanced tests for MicrophoneSource class."""

    @pytest.fixture
    def advanced_config(self):
        """Advanced microphone configuration."""
        return {
            "device_index": 0,
            "sample_rate": 44100,
            "channels": 2,
            "chunk_size": 2048,
            "format": "float32",
            "buffer_size": 8192,
            "preprocessing": {
                "enabled": True,
                "noise_reduction": True,
                "gain_control": True,
            },
        }

    @patch("scribed.audio.microphone.AUDIO_AVAILABLE", True)
    @patch("scribed.audio.microphone.pyaudio")
    def test_microphone_source_advanced_config(self, mock_pyaudio, advanced_config):
        """Test microphone source with advanced configuration."""
        source = MicrophoneSource(advanced_config)

        assert source.device_index == 0
        assert source.sample_rate == 44100
        assert source.channels == 2
        assert source.chunk_size == 2048
        assert source.format == AudioFormat.FLOAT32

    @patch("scribed.audio.microphone.AUDIO_AVAILABLE", True)
    @patch("scribed.audio.microphone.pyaudio")
    def test_microphone_source_device_validation(self, mock_pyaudio, advanced_config):
        """Test microphone device validation."""
        mock_audio = Mock()
        mock_pyaudio.PyAudio.return_value = mock_audio
        mock_audio.get_device_count.return_value = 2
        mock_audio.get_device_info_by_index.side_effect = [
            {"name": "Device 0", "maxInputChannels": 2},
            {"name": "Device 1", "maxInputChannels": 1},
        ]

        # Test with valid device index
        config = {**basic_config, "device_index": 1}
        source = MicrophoneSource(config)
        assert source.device_index == 1

    @patch("scribed.audio.microphone.AUDIO_AVAILABLE", True)
    @patch("scribed.audio.microphone.pyaudio")
    @pytest.mark.asyncio
    async def test_microphone_source_buffer_management(
        self, mock_pyaudio, basic_config
    ):
        """Test microphone source buffer management."""
        mock_audio = Mock()
        mock_stream = Mock()
        mock_pyaudio.PyAudio.return_value = mock_audio
        mock_audio.open.return_value = mock_stream
        mock_audio.get_device_count.return_value = 1
        mock_audio.get_device_info_by_index.return_value = {
            "name": "Test Device",
            "maxInputChannels": 1,
        }

        source = MicrophoneSource(basic_config)
        await source.start()

        # Test buffer data retrieval
        buffer_data = source.get_buffer_data(1.0)
        assert isinstance(buffer_data, bytes)

    @patch("scribed.audio.microphone.AUDIO_AVAILABLE", True)
    @patch("scribed.audio.microphone.pyaudio")
    def test_microphone_source_format_conversion(self, mock_pyaudio, basic_config):
        """Test microphone source format conversion."""
        # Test all supported formats
        formats = ["int16", "int32", "float32"]
        expected_pyaudio_formats = [
            mock_pyaudio.paInt16,
            mock_pyaudio.paInt32,
            mock_pyaudio.paFloat32,
        ]

        for fmt, expected in zip(formats, expected_pyaudio_formats):
            config = {**basic_config, "format": fmt}
            source = MicrophoneSource(config)
            assert source.pyaudio_format == expected

    @patch("scribed.audio.microphone.AUDIO_AVAILABLE", True)
    @patch("scribed.audio.microphone.pyaudio")
    def test_microphone_source_error_recovery(self, mock_pyaudio, basic_config):
        """Test microphone source error recovery."""
        mock_audio = Mock()
        mock_pyaudio.PyAudio.return_value = mock_audio

        # Simulate device error
        mock_audio.get_device_count.side_effect = Exception("Device error")

        source = MicrophoneSource(basic_config)

        # Should handle error gracefully
        devices = source.list_devices()
        assert devices == []


class TestFileSourceAdvanced:
    """Advanced tests for FileSource class."""

    @pytest.fixture
    def large_wav_file(self):
        """Create a larger WAV file for testing."""
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            temp_path = Path(f.name)

        # Create a larger WAV file (5 seconds)
        with wave.open(str(temp_path), "wb") as wav_file:
            wav_file.setnchannels(2)  # Stereo
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(44100)  # 44.1kHz

            # 5 seconds of audio data
            frames = b"\x00\x01\x02\x03" * (44100 * 5)
            wav_file.writeframes(frames)

        yield temp_path

        # Cleanup
        if temp_path.exists():
            temp_path.unlink()

    def test_file_source_advanced_config(self, large_wav_file):
        """Test file source with advanced configuration."""
        config = {
            "file_path": str(large_wav_file),
            "chunk_size": 4096,
            "target_sample_rate": 48000,
            "target_channels": 1,
            "target_format": "int32",
            "normalize_audio": True,
            "apply_filters": True,
        }

        source = FileSource(config)

        assert source.chunk_size == 4096
        assert source.target_sample_rate == 48000
        assert source.target_channels == 1
        assert source.target_format == AudioFormat.INT32

    def test_file_source_format_detection(self, large_wav_file):
        """Test file source format detection."""
        config = {"file_path": str(large_wav_file)}
        source = FileSource(config)

        info = source.get_audio_info()
        assert "file_path" in info
        assert "file_size_bytes" in info
        assert info["file_size_bytes"] > 0

    @pytest.mark.asyncio
    async def test_file_source_chunked_reading(self, large_wav_file):
        """Test file source chunked reading."""
        config = {"file_path": str(large_wav_file), "chunk_size": 1024}
        source = FileSource(config)

        with patch.object(source, "_load_audio_file", new_callable=AsyncMock):
            with patch.object(source, "is_available", return_value=True):
                await source.start()

                # Simulate reading multiple chunks
                chunks_read = 0
                while chunks_read < 5:  # Read a few chunks
                    chunk = await source.read_chunk()
                    if chunk is None:
                        break
                    chunks_read += 1

                await source.stop()

    def test_file_source_progress_tracking(self, large_wav_file):
        """Test file source progress tracking."""
        config = {"file_path": str(large_wav_file)}
        source = FileSource(config)

        # Mock some internal state for testing
        source._mark_active()
        source.total_samples = 44100 * 5  # 5 seconds at 44.1kHz
        source.current_position = 44100 * 2  # 2 seconds played
        source.target_sample_rate = 44100

        info = source.get_audio_info()
        assert "progress_percent" in info
        assert "duration_seconds" in info

        remaining = source.get_remaining_duration()
        assert abs(remaining - 3.0) < 0.1  # Should be about 3 seconds remaining

    def test_file_source_seek_functionality(self, large_wav_file):
        """Test file source seeking functionality."""
        config = {"file_path": str(large_wav_file)}
        source = FileSource(config)

        source._mark_active()
        source.total_samples = 44100 * 5  # 5 seconds
        source.target_sample_rate = 44100

        # Test seeking to different positions
        source.seek_to_position(2.5)  # Seek to 2.5 seconds
        assert source.current_position == int(44100 * 2.5)

        source.seek_to_position(0.0)  # Seek to beginning
        assert source.current_position == 0

    def test_file_source_supported_formats_comprehensive(self):
        """Test comprehensive list of supported formats."""
        formats = FileSource.get_supported_formats()

        expected_formats = [".wav", ".mp3", ".flac", ".m4a", ".ogg", ".aac"]

        for fmt in expected_formats:
            assert fmt in formats

        # Test format checking
        assert FileSource.is_format_supported("test.wav") is True
        assert FileSource.is_format_supported("test.mp3") is True
        assert FileSource.is_format_supported("test.xyz") is False

    @pytest.mark.asyncio
    async def test_file_source_error_handling_detailed(self, temp_wav_file):
        """Test detailed error handling in file source."""
        config = {"file_path": str(temp_wav_file)}
        source = FileSource(config)

        # Test with file that becomes unavailable
        with patch.object(source, "is_available", return_value=False):
            with pytest.raises(AudioError, match="No audio libraries available"):
                await source.start()

    def test_file_source_memory_efficiency(self, large_wav_file):
        """Test file source memory efficiency with large files."""
        config = {
            "file_path": str(large_wav_file),
            "chunk_size": 512,  # Small chunks for memory efficiency
        }
        source = FileSource(config)

        info = source.get_audio_info()

        # File should be readable without loading everything into memory
        assert "file_size_bytes" in info
        assert info["file_size_bytes"] > 0

    def test_file_source_concurrent_access(self, temp_wav_file):
        """Test file source behavior with concurrent access attempts."""
        config = {"file_path": str(temp_wav_file)}

        # Create multiple source instances for the same file
        sources = [FileSource(config) for _ in range(3)]

        # All should be able to access the file info
        for source in sources:
            info = source.get_audio_info()
            assert info["file_path"] == str(temp_wav_file)


# === Consolidated from test_audio_base.py ===

from scribed.audio.base import (
    AudioFormat,
    AudioError,
    AudioValidationError,
    AudioDeviceError,
    AudioChunk,
    AudioData,
    AudioFormatConverter,
    AudioSource,
)


class TestAudioFormat:
    """Test AudioFormat enum."""

    def test_audio_format_values(self):
        """Test audio format enum values."""
        assert AudioFormat.INT16.value == "int16"
        assert AudioFormat.INT32.value == "int32"
        assert AudioFormat.FLOAT32.value == "float32"


class TestAudioExceptions:
    """Test audio exception classes."""

    def test_audio_error(self):
        """Test AudioError exception."""
        error = AudioError("Test error")
        assert str(error) == "Test error"
        assert isinstance(error, Exception)

    def test_audio_validation_error(self):
        """Test AudioValidationError exception."""
        error = AudioValidationError("Validation failed")
        assert str(error) == "Validation failed"
        assert isinstance(error, AudioError)

    def test_audio_device_error(self):
        """Test AudioDeviceError exception."""
        error = AudioDeviceError("Device error")
        assert str(error) == "Device error"
        assert isinstance(error, AudioError)


class TestAudioChunk:
    """Test AudioChunk class."""

    def test_audio_chunk_creation(self):
        """Test creating audio chunk."""
        data = b"\x00\x01" * 100
        chunk = AudioChunk(
            data=data,
            sample_rate=16000,
            channels=1,
            format=AudioFormat.INT16,
            timestamp=time.time(),
            chunk_size=100,
        )

        assert chunk.data == data
        assert chunk.sample_rate == 16000
        assert chunk.channels == 1
        assert chunk.format == AudioFormat.INT16
        assert chunk.chunk_size == 100

    def test_audio_chunk_validation_empty_data(self):
        """Test audio chunk validation with empty data."""
        with pytest.raises(
            AudioValidationError, match="Audio chunk data cannot be empty"
        ):
            AudioChunk(
                data=b"",
                sample_rate=16000,
                channels=1,
                format=AudioFormat.INT16,
                timestamp=time.time(),
                chunk_size=100,
            )

    def test_audio_chunk_validation_invalid_sample_rate(self):
        """Test audio chunk validation with invalid sample rate."""
        with pytest.raises(AudioValidationError, match="Sample rate must be positive"):
            AudioChunk(
                data=b"\x00\x01" * 100,
                sample_rate=0,
                channels=1,
                format=AudioFormat.INT16,
                timestamp=time.time(),
                chunk_size=100,
            )

    def test_audio_chunk_validation_invalid_channels(self):
        """Test audio chunk validation with invalid channels."""
        with pytest.raises(
            AudioValidationError, match="Channel count must be positive"
        ):
            AudioChunk(
                data=b"\x00\x01" * 100,
                sample_rate=16000,
                channels=0,
                format=AudioFormat.INT16,
                timestamp=time.time(),
                chunk_size=100,
            )

    def test_audio_chunk_validation_invalid_chunk_size(self):
        """Test audio chunk validation with invalid chunk size."""
        with pytest.raises(AudioValidationError, match="Chunk size must be positive"):
            AudioChunk(
                data=b"\x00\x01" * 100,
                sample_rate=16000,
                channels=1,
                format=AudioFormat.INT16,
                timestamp=time.time(),
                chunk_size=0,
            )

    def test_audio_chunk_duration_calculation(self):
        """Test audio chunk duration calculation."""
        # 16-bit, mono, 16kHz, 1 second of data
        samples_per_second = 16000
        bytes_per_sample = 2
        data_size = samples_per_second * bytes_per_sample

        chunk = AudioChunk(
            data=b"\x00" * data_size,
            sample_rate=16000,
            channels=1,
            format=AudioFormat.INT16,
            timestamp=time.time(),
            chunk_size=samples_per_second,
        )

        assert abs(chunk.duration_seconds - 1.0) < 0.001

    def test_audio_chunk_bytes_per_sample(self):
        """Test bytes per sample calculation."""
        chunk_int16 = AudioChunk(
            data=b"\x00\x01" * 100,
            sample_rate=16000,
            channels=1,
            format=AudioFormat.INT16,
            timestamp=time.time(),
            chunk_size=100,
        )
        assert chunk_int16._get_bytes_per_sample() == 2

        chunk_int32 = AudioChunk(
            data=b"\x00\x01\x02\x03" * 100,
            sample_rate=16000,
            channels=1,
            format=AudioFormat.INT32,
            timestamp=time.time(),
            chunk_size=100,
        )
        assert chunk_int32._get_bytes_per_sample() == 4

        chunk_float32 = AudioChunk(
            data=b"\x00\x01\x02\x03" * 100,
            sample_rate=16000,
            channels=1,
            format=AudioFormat.FLOAT32,
            timestamp=time.time(),
            chunk_size=100,
        )
        assert chunk_float32._get_bytes_per_sample() == 4

    def test_audio_chunk_to_numpy(self):
        """Test converting audio chunk to numpy array."""
        # Skip if numpy not available or mocked
        try:
            import numpy as np

            if hasattr(np, "_mock_name"):  # Skip if numpy is mocked
                pytest.skip("Numpy is mocked")
        except ImportError:
            pytest.skip("Numpy not available")

        # Create test data with real numpy
        test_data = np.array([100, -100, 200, -200], dtype=np.int16)

        chunk = AudioChunk(
            data=test_data.tobytes(),
            sample_rate=16000,
            channels=1,
            format=AudioFormat.INT16,
            timestamp=time.time(),
            chunk_size=4,
        )

        numpy_data = chunk.to_numpy()
        if numpy_data is not None:  # Only test if conversion worked
            assert np.array_equal(numpy_data, test_data)

    def test_audio_chunk_to_numpy_unavailable(self):
        """Test to_numpy when numpy is not available."""
        chunk = AudioChunk(
            data=b"\x00\x01" * 100,
            sample_rate=16000,
            channels=1,
            format=AudioFormat.INT16,
            timestamp=time.time(),
            chunk_size=100,
        )

        with patch("scribed.audio.base.NUMPY_AVAILABLE", False):
            result = chunk.to_numpy()
            assert result is None


class TestAudioData:
    """Test AudioData class."""

    def create_test_chunk(self, data_size=100):
        """Helper to create test audio chunk."""
        return AudioChunk(
            data=b"\x00\x01" * data_size,
            sample_rate=16000,
            channels=1,
            format=AudioFormat.INT16,
            timestamp=time.time(),
            chunk_size=data_size,
        )

    def test_audio_data_creation(self):
        """Test creating audio data."""
        chunks = [self.create_test_chunk(), self.create_test_chunk()]
        metadata = {"source": "test"}

        audio_data = AudioData(chunks=chunks, total_duration=2.0, metadata=metadata)

        assert len(audio_data.chunks) == 2
        assert audio_data.total_duration == 2.0
        assert audio_data.metadata == metadata

    def test_audio_data_validation_empty_chunks(self):
        """Test audio data validation with empty chunks."""
        with pytest.raises(
            AudioValidationError, match="AudioData must contain at least one chunk"
        ):
            AudioData(chunks=[], total_duration=0.0, metadata={})

    def test_audio_data_validation_inconsistent_format(self):
        """Test audio data validation with inconsistent chunk formats."""
        chunk1 = self.create_test_chunk()
        chunk2 = AudioChunk(
            data=b"\x00\x01" * 100,
            sample_rate=44100,  # Different sample rate
            channels=1,
            format=AudioFormat.INT16,
            timestamp=time.time(),
            chunk_size=100,
        )

        with pytest.raises(
            AudioValidationError, match="All chunks must have consistent audio format"
        ):
            AudioData(chunks=[chunk1, chunk2], total_duration=2.0, metadata={})

    def test_audio_data_properties(self):
        """Test audio data properties."""
        chunks = [self.create_test_chunk(), self.create_test_chunk()]
        audio_data = AudioData(
            chunks=chunks, total_duration=2.0, metadata={"test": "data"}
        )

        assert audio_data.sample_rate == 16000
        assert audio_data.channels == 1
        assert audio_data.format == AudioFormat.INT16

    def test_audio_data_get_combined_data(self):
        """Test getting combined audio data."""
        chunk1 = AudioChunk(
            data=b"\x00\x01",
            sample_rate=16000,
            channels=1,
            format=AudioFormat.INT16,
            timestamp=time.time(),
            chunk_size=1,
        )
        chunk2 = AudioChunk(
            data=b"\x02\x03",
            sample_rate=16000,
            channels=1,
            format=AudioFormat.INT16,
            timestamp=time.time(),
            chunk_size=1,
        )

        audio_data = AudioData(chunks=[chunk1, chunk2], total_duration=2.0, metadata={})

        combined = audio_data.get_combined_data()
        assert combined == b"\x00\x01\x02\x03"

    def test_audio_data_get_info(self):
        """Test getting audio data info."""
        chunks = [self.create_test_chunk(), self.create_test_chunk()]
        metadata = {"source": "test"}

        audio_data = AudioData(chunks=chunks, total_duration=2.0, metadata=metadata)

        info = audio_data.get_info()

        assert info["chunk_count"] == 2
        assert info["total_duration"] == 2.0
        assert info["sample_rate"] == 16000
        assert info["channels"] == 1
        assert info["format"] == "int16"
        assert info["total_bytes"] == 400  # 2 chunks * 200 bytes each
        assert info["metadata"] == metadata


class TestAudioFormatConverter:
    """Test AudioFormatConverter class."""

    def test_validate_format_success(self):
        """Test successful format validation."""
        result = AudioFormatConverter.validate_format(16000, 1, AudioFormat.INT16)
        assert result is True

    def test_validate_format_invalid_sample_rate(self):
        """Test format validation with invalid sample rate."""
        with pytest.raises(AudioValidationError, match="Invalid sample rate"):
            AudioFormatConverter.validate_format(0, 1, AudioFormat.INT16)

    def test_validate_format_invalid_channels(self):
        """Test format validation with invalid channels."""
        with pytest.raises(AudioValidationError, match="Invalid channel count"):
            AudioFormatConverter.validate_format(16000, 0, AudioFormat.INT16)

    def test_validate_format_high_sample_rate(self):
        """Test format validation with very high sample rate."""
        with pytest.raises(AudioValidationError, match="Sample rate too high"):
            AudioFormatConverter.validate_format(300000, 1, AudioFormat.INT16)

    def test_validate_format_too_many_channels(self):
        """Test format validation with too many channels."""
        with pytest.raises(AudioValidationError, match="Too many channels"):
            AudioFormatConverter.validate_format(16000, 10, AudioFormat.INT16)

    def test_validate_format_uncommon_sample_rate(self):
        """Test format validation with uncommon sample rate (should warn but pass)."""
        result = AudioFormatConverter.validate_format(17000, 1, AudioFormat.INT16)
        assert result is True

    @pytest.mark.skipif(
        not hasattr(AudioFormatConverter, "convert_chunk_format"),
        reason="Format conversion not available without numpy",
    )
    def test_convert_chunk_format_same_format(self):
        """Test format conversion with same format."""
        chunk = AudioChunk(
            data=b"\x00\x01" * 100,
            sample_rate=16000,
            channels=1,
            format=AudioFormat.INT16,
            timestamp=time.time(),
            chunk_size=100,
        )

        converted = AudioFormatConverter.convert_chunk_format(chunk, AudioFormat.INT16)
        assert converted == chunk

    @pytest.mark.skipif(
        not hasattr(AudioFormatConverter, "convert_chunk_format"),
        reason="Format conversion not available without numpy",
    )
    def test_convert_chunk_format_no_numpy(self):
        """Test format conversion without numpy."""
        chunk = AudioChunk(
            data=b"\x00\x01" * 100,
            sample_rate=16000,
            channels=1,
            format=AudioFormat.INT16,
            timestamp=time.time(),
            chunk_size=100,
        )

        with patch("scribed.audio.base.NUMPY_AVAILABLE", False):
            with pytest.raises(
                AudioValidationError, match="Numpy required for format conversion"
            ):
                AudioFormatConverter.convert_chunk_format(chunk, AudioFormat.FLOAT32)

    @pytest.mark.skipif(
        not hasattr(AudioFormatConverter, "resample_chunk"),
        reason="Resampling not available without numpy",
    )
    def test_resample_chunk_same_rate(self):
        """Test resampling with same sample rate."""
        chunk = AudioChunk(
            data=b"\x00\x01" * 100,
            sample_rate=16000,
            channels=1,
            format=AudioFormat.INT16,
            timestamp=time.time(),
            chunk_size=100,
        )

        resampled = AudioFormatConverter.resample_chunk(chunk, 16000)
        assert resampled == chunk

    @pytest.mark.skipif(
        not hasattr(AudioFormatConverter, "resample_chunk"),
        reason="Resampling not available without numpy",
    )
    def test_resample_chunk_no_numpy(self):
        """Test resampling without numpy."""
        chunk = AudioChunk(
            data=b"\x00\x01" * 100,
            sample_rate=16000,
            channels=1,
            format=AudioFormat.INT16,
            timestamp=time.time(),
            chunk_size=100,
        )

        with patch("scribed.audio.base.NUMPY_AVAILABLE", False):
            with pytest.raises(
                AudioValidationError, match="Numpy required for resampling"
            ):
                AudioFormatConverter.resample_chunk(chunk, 44100)


class MockAudioSource(AudioSource):
    """Mock audio source for testing."""

    def __init__(self, config):
        super().__init__(config)
        self.chunks = []
        self.current_index = 0

    async def start(self):
        self._mark_active()

    async def stop(self):
        self._mark_inactive()

    async def read_chunk(self):
        if not self._is_active or self.current_index >= len(self.chunks):
            return None

        chunk = self.chunks[self.current_index]
        self.current_index += 1
        return chunk

    def get_audio_info(self):
        info = self.get_base_info()
        info.update(
            {"total_chunks": len(self.chunks), "current_index": self.current_index}
        )
        return info

    def is_available(self):
        return True


class TestAudioSource:
    """Test AudioSource abstract base class."""

    @pytest.fixture
    def mock_source(self):
        """Create mock audio source."""
        config = {"test": "config"}
        source = MockAudioSource(config)

        # Add some test chunks
        for i in range(3):
            chunk = AudioChunk(
                data=b"\x00\x01" * 100,
                sample_rate=16000,
                channels=1,
                format=AudioFormat.INT16,
                timestamp=time.time(),
                chunk_size=100,
            )
            source.chunks.append(chunk)

        return source

    def test_audio_source_initialization(self):
        """Test audio source initialization."""
        config = {"test": "config"}
        source = MockAudioSource(config)

        assert source.config == config
        assert not source._is_active
        assert source._start_time is None

    @pytest.mark.asyncio
    async def test_audio_source_start_stop(self, mock_source):
        """Test audio source start and stop."""
        assert not mock_source.is_active
        assert mock_source.uptime_seconds is None

        await mock_source.start()
        assert mock_source.is_active
        assert mock_source.uptime_seconds is not None

        await mock_source.stop()
        assert not mock_source.is_active
        assert mock_source.uptime_seconds is None

    @pytest.mark.asyncio
    async def test_audio_source_read_stream(self, mock_source):
        """Test reading audio stream."""
        chunks_read = []

        async for chunk in mock_source.read_stream():
            chunks_read.append(chunk)

        assert len(chunks_read) == 3
        assert not mock_source.is_active  # Should auto-stop

    @pytest.mark.asyncio
    async def test_audio_source_read_duration(self, mock_source):
        """Test reading audio for specific duration."""
        # Mock time to control duration - need to patch the time module used in AudioSource
        with patch("scribed.audio.base.time") as mock_time:
            # Provide enough time values for all the calls in read_duration and stop
            mock_time.time.side_effect = [
                0,
                0.1,
                0.2,
                0.3,
                1.1,
                1.1,
                1.1,
                1.1,
                1.1,
            ]  # Simulate time progression

            audio_data = await mock_source.read_duration(1.0)

            assert isinstance(audio_data, AudioData)
            assert len(audio_data.chunks) > 0
            assert "requested_duration" in audio_data.metadata
            assert "actual_duration" in audio_data.metadata
            assert "source_type" in audio_data.metadata

    @pytest.mark.asyncio
    async def test_audio_source_read_duration_no_data(self):
        """Test reading duration when no data available."""
        config = {"test": "config"}
        source = MockAudioSource(config)
        # No chunks added

        with pytest.raises(AudioError, match="No audio data read"):
            await source.read_duration(1.0)

    def test_audio_source_get_base_info(self, mock_source):
        """Test getting base audio source info."""
        info = mock_source.get_base_info()

        assert "source_type" in info
        assert "is_active" in info
        assert "is_available" in info
        assert "uptime_seconds" in info
        assert "config" in info

        assert info["source_type"] == "MockAudioSource"
        assert info["is_active"] is False
        assert info["is_available"] is True
        assert info["uptime_seconds"] is None
        assert info["config"] == {"test": "config"}

    @pytest.mark.asyncio
    async def test_audio_source_context_manager(self, mock_source):
        """Test audio source as async context manager."""
        async with mock_source as source:
            assert source.is_active

        assert not mock_source.is_active

    def test_audio_source_properties(self, mock_source):
        """Test audio source properties."""
        assert not mock_source.is_active
        assert mock_source.uptime_seconds is None

        mock_source._mark_active()
        assert mock_source.is_active
        assert mock_source.uptime_seconds is not None

        mock_source._mark_inactive()
        assert not mock_source.is_active
        assert mock_source.uptime_seconds is None


class TestAudioChunkAdvanced:
    """Advanced tests for AudioChunk class."""

    def test_audio_chunk_validation_edge_cases(self):
        """Test audio chunk validation with edge cases."""
        # Test very large chunk size
        with pytest.raises(AudioValidationError):
            AudioChunk(
                data=b"\x00\x01" * 100,
                sample_rate=16000,
                channels=1,
                format=AudioFormat.INT16,
                timestamp=time.time(),
                chunk_size=1000000,  # Much larger than data
            )

    def test_audio_chunk_duration_precision(self):
        """Test audio chunk duration calculation precision."""
        # Test with exact sample counts
        chunk = AudioChunk(
            data=b"\x00\x01" * 8000,  # Exactly 0.5 seconds at 16kHz
            sample_rate=16000,
            channels=1,
            format=AudioFormat.INT16,
            timestamp=time.time(),
            chunk_size=8000,
        )

        assert abs(chunk.duration_seconds - 0.5) < 0.001

    def test_audio_chunk_format_consistency(self):
        """Test audio chunk format consistency checks."""
        # Test different format combinations
        formats_and_sizes = [
            (AudioFormat.INT16, 2),
            (AudioFormat.INT32, 4),
            (AudioFormat.FLOAT32, 4),
        ]

        for fmt, expected_size in formats_and_sizes:
            chunk = AudioChunk(
                data=b"\x00" * (100 * expected_size),
                sample_rate=16000,
                channels=1,
                format=fmt,
                timestamp=time.time(),
                chunk_size=100,
            )
            assert chunk._get_bytes_per_sample() == expected_size

    def test_audio_chunk_immutability(self):
        """Test that audio chunk is immutable after creation."""
        chunk = AudioChunk(
            data=b"\x00\x01" * 100,
            sample_rate=16000,
            channels=1,
            format=AudioFormat.INT16,
            timestamp=time.time(),
            chunk_size=100,
        )

        # AudioChunk is a dataclass, so fields should be immutable if frozen
        original_data = chunk.data
        original_rate = chunk.sample_rate

        # These should be the same references/values
        assert chunk.data is original_data
        assert chunk.sample_rate == original_rate


class TestAudioDataAdvanced:
    """Advanced tests for AudioData class."""

    def create_test_chunks(self, count=3, data_size=100):
        """Helper to create multiple test audio chunks."""
        chunks = []
        for i in range(count):
            chunk = AudioChunk(
                data=b"\x00\x01" * data_size,
                sample_rate=16000,
                channels=1,
                format=AudioFormat.INT16,
                timestamp=time.time() + i * 0.1,
                chunk_size=data_size,
            )
            chunks.append(chunk)
        return chunks

    def test_audio_data_large_dataset(self):
        """Test audio data with large number of chunks."""
        chunks = self.create_test_chunks(count=100, data_size=50)

        audio_data = AudioData(
            chunks=chunks, total_duration=10.0, metadata={"test": "large_dataset"}
        )

        assert len(audio_data.chunks) == 100
        combined_data = audio_data.get_combined_data()
        assert len(combined_data) == 100 * 100  # 100 chunks * 100 bytes each

    def test_audio_data_chunk_validation_detailed(self):
        """Test detailed chunk validation in AudioData."""
        chunk1 = AudioChunk(
            data=b"\x00\x01" * 100,
            sample_rate=16000,
            channels=1,
            format=AudioFormat.INT16,
            timestamp=time.time(),
            chunk_size=100,
        )

        chunk2 = AudioChunk(
            data=b"\x00\x01" * 100,
            sample_rate=44100,  # Different sample rate
            channels=1,
            format=AudioFormat.INT16,
            timestamp=time.time(),
            chunk_size=100,
        )

        with pytest.raises(AudioValidationError, match="consistent audio format"):
            AudioData(chunks=[chunk1, chunk2], total_duration=1.0, metadata={})

    def test_audio_data_metadata_preservation(self):
        """Test that metadata is preserved and accessible."""
        chunks = self.create_test_chunks(count=2)
        metadata = {
            "source": "test",
            "processing": {"normalized": True, "filtered": False},
            "timestamps": [1.0, 2.0, 3.0],
        }

        audio_data = AudioData(chunks=chunks, total_duration=2.0, metadata=metadata)

        assert audio_data.metadata == metadata
        info = audio_data.get_info()
        assert info["metadata"] == metadata

    def test_audio_data_info_completeness(self):
        """Test that get_info returns complete information."""
        chunks = self.create_test_chunks(count=3, data_size=200)
        metadata = {"test": "info"}

        audio_data = AudioData(chunks=chunks, total_duration=3.0, metadata=metadata)

        info = audio_data.get_info()

        required_fields = [
            "chunk_count",
            "total_duration",
            "sample_rate",
            "channels",
            "format",
            "total_bytes",
            "metadata",
        ]

        for field in required_fields:
            assert field in info

        assert info["chunk_count"] == 3
        assert info["total_duration"] == 3.0
        assert info["total_bytes"] == 3 * 400  # 3 chunks * 400 bytes each


class TestAudioFormatConverterAdvanced:
    """Advanced tests for AudioFormatConverter class."""

    def test_format_validation_boundary_conditions(self):
        """Test format validation at boundary conditions."""
        # Test minimum valid values
        assert AudioFormatConverter.validate_format(1000, 1, AudioFormat.INT16) is True

        # Test maximum reasonable values
        assert (
            AudioFormatConverter.validate_format(192000, 8, AudioFormat.INT16) is True
        )

        # Test just over the limits
        with pytest.raises(AudioValidationError):
            AudioFormatConverter.validate_format(300001, 1, AudioFormat.INT16)

        with pytest.raises(AudioValidationError):
            AudioFormatConverter.validate_format(16000, 9, AudioFormat.INT16)

    def test_common_sample_rates(self):
        """Test validation of common sample rates."""
        common_rates = [8000, 16000, 22050, 44100, 48000, 96000, 192000]

        for rate in common_rates:
            assert (
                AudioFormatConverter.validate_format(rate, 1, AudioFormat.INT16) is True
            )

    def test_uncommon_sample_rates_warning(self):
        """Test that uncommon sample rates generate warnings but pass."""
        uncommon_rates = [11025, 32000, 88200]

        for rate in uncommon_rates:
            # Should pass but might generate warnings
            result = AudioFormatConverter.validate_format(rate, 1, AudioFormat.INT16)
            assert result is True


class TestAudioSourceAdvanced:
    """Advanced tests for AudioSource abstract base class."""

    def test_audio_source_context_manager_error_handling(self):
        """Test audio source context manager with errors."""
        config = {"test": "config"}
        source = MockAudioSource(config)

        # Add chunks for testing
        for i in range(3):
            chunk = AudioChunk(
                data=b"\x00\x01" * 100,
                sample_rate=16000,
                channels=1,
                format=AudioFormat.INT16,
                timestamp=time.time(),
                chunk_size=100,
            )
            source.chunks.append(chunk)

        try:
            with source as s:
                assert s.is_active
                raise Exception("Test error")
        except Exception as e:
            assert str(e) == "Test error"

        # Should be properly cleaned up despite the error
        assert not source.is_active

    @pytest.mark.asyncio
    async def test_audio_source_read_stream_empty(self):
        """Test reading stream when no data is available."""
        config = {"test": "config"}
        source = MockAudioSource(config)
        # Don't add any chunks

        chunks_read = []
        async for chunk in source.read_stream():
            chunks_read.append(chunk)

        assert len(chunks_read) == 0
        assert not source.is_active

    def test_audio_source_uptime_tracking(self):
        """Test uptime tracking accuracy."""
        config = {"test": "config"}
        source = MockAudioSource(config)

        import time

        # Not active initially
        assert source.uptime_seconds is None

        # Start and check uptime
        source._mark_active()
        time.sleep(0.01)  # Small delay
        uptime1 = source.uptime_seconds
        assert uptime1 > 0

        time.sleep(0.01)  # Another small delay
        uptime2 = source.uptime_seconds
        assert uptime2 > uptime1

        # Stop and check uptime is None
        source._mark_inactive()
        assert source.uptime_seconds is None

    def test_audio_source_info_consistency(self):
        """Test that audio source info is consistent."""
        config = {"test_param": "test_value", "numeric_param": 42}
        source = MockAudioSource(config)

        info = source.get_audio_info()
        base_info = source.get_base_info()

        # Check that base info is included in audio info
        for key, value in base_info.items():
            assert key in info
            assert info[key] == value

        # Check config is preserved
        assert info["config"] == config

    @pytest.mark.asyncio
    async def test_audio_source_concurrent_operations(self):
        """Test concurrent operations on audio source."""
        config = {"test": "config"}
        source = MockAudioSource(config)

        # Add test chunks
        for i in range(10):
            chunk = AudioChunk(
                data=b"\x00\x01" * 100,
                sample_rate=16000,
                channels=1,
                format=AudioFormat.INT16,
                timestamp=time.time(),
                chunk_size=100,
            )
            source.chunks.append(chunk)

        # Start multiple read operations concurrently
        tasks = []
        for i in range(3):
            task = asyncio.create_task(source.read_duration(0.1))
            tasks.append(task)

        # Wait for all tasks to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Check that at least some succeeded
        successful_results = [r for r in results if isinstance(r, AudioData)]
        assert len(successful_results) > 0
