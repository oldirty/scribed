"""Pytest configuration and fixtures for Scribed tests."""

import pytest
from unittest.mock import patch, MagicMock

from .mocks import MockMicrophoneInput, MockAsyncMicrophoneInput, MockWakeWordEngine


@pytest.fixture(autouse=True)
def mock_microphone_input():
    """Automatically mock microphone input for all tests."""
    with patch(
        "scribed.audio.microphone_input.MicrophoneInput", MockMicrophoneInput
    ), patch(
        "scribed.audio.microphone_input.AsyncMicrophoneInput", MockAsyncMicrophoneInput
    ):
        yield


@pytest.fixture
def mock_wake_word_engine():
    """Mock wake word engine for tests."""
    with patch("scribed.wake_word.WakeWordEngine", MockWakeWordEngine):
        yield


@pytest.fixture(autouse=True)
def mock_audio_dependencies():
    """Mock pyaudio and numpy to avoid hardware dependencies."""
    # Mock pyaudio
    mock_pyaudio = MagicMock()
    mock_pyaudio.PyAudio.return_value.get_device_count.return_value = 1
    mock_pyaudio.PyAudio.return_value.get_device_info_by_index.return_value = {
        "name": "Mock Audio Device",
        "maxInputChannels": 1,
        "defaultSampleRate": 16000.0,
        "hostApi": 0,
    }
    mock_pyaudio.paInt16 = 8  # Mock constant

    # Mock numpy
    mock_numpy = MagicMock()

    with patch.dict(
        "sys.modules",
        {
            "pyaudio": mock_pyaudio,
            "numpy": mock_numpy,
        },
    ):
        yield


@pytest.fixture
def mock_picovoice():
    """Mock Picovoice/Porcupine for wake word tests."""
    mock_porcupine = MagicMock()
    mock_porcupine_class = MagicMock()
    mock_porcupine_class.return_value = mock_porcupine
    mock_porcupine.process.return_value = -1  # No wake word detected

    with patch.dict(
        "sys.modules",
        {
            "pvporcupine": MagicMock(Porcupine=mock_porcupine_class),
        },
    ):
        yield mock_porcupine


@pytest.fixture
def sample_config():
    """Provide a sample configuration for tests."""
    from scribed.config import Config, OutputConfig, APIConfig

    return Config(
        source_mode="microphone",
        output=OutputConfig(log_to_file=False),  # Disable file logging for tests
        api=APIConfig(host="127.0.0.1", port=8081),  # Use different port for tests
    )


@pytest.fixture
def sample_audio_data():
    """Provide sample audio data for tests."""
    # 1 second of 16kHz mono audio (silence)
    sample_rate = 16000
    duration = 1.0
    samples = int(sample_rate * duration)
    return b"\x00\x00" * samples  # 16-bit silence


@pytest.fixture
def temp_audio_file(tmp_path, sample_audio_data):
    """Create a temporary audio file for tests."""
    import wave

    audio_file = tmp_path / "test_audio.wav"

    with wave.open(str(audio_file), "wb") as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(16000)  # 16kHz
        wav_file.writeframes(sample_audio_data)

    return audio_file
