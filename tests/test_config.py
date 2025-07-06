"""Test configuration management."""

import pytest
import tempfile
import yaml
from pathlib import Path

from scribed.config import (
    Config,
    FileWatcherConfig,
    MicrophoneConfig,
    APIConfig,
    TranscriptionConfig,
    OutputConfig,
    PowerWordsConfig,
    WakeWordConfig,
)


class TestFileWatcherConfig:
    """Test FileWatcherConfig class."""

    def test_default_values(self):
        """Test default configuration values."""
        config = FileWatcherConfig()
        # Normalize paths for comparison
        expected_watch = Path("./audio_input").resolve()
        expected_output = Path("./transcripts").resolve()
        actual_watch = Path(config.watch_directory).resolve()
        actual_output = Path(config.output_directory).resolve()

        assert actual_watch == expected_watch
        assert actual_output == expected_output
        assert config.supported_formats == [".wav", ".mp3", ".flac"]

    def test_custom_values(self):
        """Test custom configuration values."""
        # Use temporary directories instead of hardcoded paths
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            custom_input = temp_path / "input"
            custom_output = temp_path / "output"

            config = FileWatcherConfig(
                watch_directory=str(custom_input),
                output_directory=str(custom_output),
                supported_formats=[".wav", ".mp3"],
            )

            # Normalize paths for comparison
            expected_watch = custom_input.resolve()
            expected_output = custom_output.resolve()
            actual_watch = Path(config.watch_directory).resolve()
            actual_output = Path(config.output_directory).resolve()

            assert actual_watch == expected_watch
            assert actual_output == expected_output
            assert config.supported_formats == [".wav", ".mp3"]


class TestMicrophoneConfig:
    """Test MicrophoneConfig class."""

    def test_default_values(self):
        """Test default configuration values."""
        config = MicrophoneConfig()
        assert config.device_index is None
        assert config.sample_rate == 16000
        assert config.channels == 1
        assert config.chunk_size == 1024


class TestAPIConfig:
    """Test APIConfig class."""

    def test_default_values(self):
        """Test default configuration values."""
        config = APIConfig()
        assert config.host == "127.0.0.1"
        assert config.port == 8080
        assert config.debug is False


class TestTranscriptionConfig:
    """Test TranscriptionConfig class."""

    def test_default_values(self):
        """Test default configuration values."""
        config = TranscriptionConfig()
        assert config.provider == "whisper"
        assert config.language == "en-US"
        assert config.model == "base"
        assert config.api_key is None

    def test_invalid_provider(self):
        """Test invalid provider validation."""
        with pytest.raises(ValueError, match="Provider must be one of"):
            TranscriptionConfig(provider="invalid_provider")

    def test_valid_providers(self):
        """Test valid provider values."""
        for provider in ["whisper", "google_speech", "aws_transcribe", "mock"]:
            config = TranscriptionConfig(provider=provider)
            assert config.provider == provider


class TestOutputConfig:
    """Test OutputConfig class."""

    def test_default_values(self):
        """Test default configuration values."""
        config = OutputConfig()
        assert config.format == "txt"
        assert config.log_to_file is True

        # Normalize paths for comparison
        expected_log_path = Path("./logs/transcription.log").resolve()
        actual_log_path = Path(config.log_file_path).resolve()
        assert actual_log_path == expected_log_path

    def test_invalid_format(self):
        """Test invalid format validation."""
        with pytest.raises(ValueError, match="Format must be one of"):
            OutputConfig(format="invalid_format")

    def test_valid_formats(self):
        """Test valid format values."""
        for fmt in ["txt", "json", "srt"]:
            config = OutputConfig(format=fmt)
            assert config.format == fmt


class TestPowerWordsConfig:
    """Test PowerWordsConfig class."""

    def test_default_values(self):
        """Test default configuration values."""
        config = PowerWordsConfig()
        assert config.enabled is False
        assert config.mappings == {}

    def test_custom_mappings(self):
        """Test custom power word mappings."""
        mappings = {"open browser": "firefox", "list files": "ls -la"}
        config = PowerWordsConfig(enabled=True, mappings=mappings)
        assert config.enabled is True
        assert config.mappings == mappings


class TestWakeWordConfig:
    """Test WakeWordConfig class."""

    def test_default_values(self):
        """Test default configuration values."""
        config = WakeWordConfig()
        assert config.engine == "picovoice"
        assert config.model_path is None
        assert config.silence_timeout == 15
        assert config.stop_phrase == "stop listening"


class TestConfig:
    """Test main Config class."""

    def test_default_values(self):
        """Test default configuration values."""
        config = Config()
        assert config.source_mode == "file"
        assert isinstance(config.file_watcher, FileWatcherConfig)
        assert isinstance(config.microphone, MicrophoneConfig)
        assert isinstance(config.wake_word, WakeWordConfig)
        assert isinstance(config.power_words, PowerWordsConfig)
        assert isinstance(config.api, APIConfig)
        assert isinstance(config.transcription, TranscriptionConfig)
        assert isinstance(config.output, OutputConfig)

    def test_invalid_source_mode(self):
        """Test invalid source mode validation."""
        with pytest.raises(ValueError, match="Source mode must be one of"):
            Config(source_mode="invalid_mode")

    def test_valid_source_modes(self):
        """Test valid source mode values."""
        for mode in ["file", "microphone"]:
            config = Config(source_mode=mode)
            assert config.source_mode == mode

    def test_from_env_with_no_file(self):
        """Test loading configuration from environment when no file exists."""
        config = Config.from_env()
        assert isinstance(config, Config)
        assert config.source_mode == "file"  # Default value

    def test_from_file_not_found(self):
        """Test loading configuration from non-existent file."""
        with pytest.raises(FileNotFoundError):
            Config.from_file("non_existent_file.yaml")

    def test_from_file_valid(self):
        """Test loading configuration from valid YAML file."""
        config_data = {
            "source_mode": "microphone",
            "api": {"host": "0.0.0.0", "port": 9000},
            "transcription": {"provider": "google_speech", "language": "fr-FR"},
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_data, f)
            temp_path = f.name

        try:
            config = Config.from_file(temp_path)
            assert config.source_mode == "microphone"
            assert config.api.host == "0.0.0.0"
            assert config.api.port == 9000
            assert config.transcription.provider == "google_speech"
            assert config.transcription.language == "fr-FR"
        finally:
            Path(temp_path).unlink()

    def test_to_file(self):
        """Test saving configuration to file."""
        config = Config(
            source_mode="microphone", api=APIConfig(host="0.0.0.0", port=9000)
        )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            temp_path = f.name

        try:
            config.to_file(temp_path)

            # Verify file was created and has correct content
            assert Path(temp_path).exists()

            with open(temp_path, "r") as f:
                saved_data = yaml.safe_load(f)

            assert saved_data["source_mode"] == "microphone"
            assert saved_data["api"]["host"] == "0.0.0.0"
            assert saved_data["api"]["port"] == 9000

        finally:
            Path(temp_path).unlink()

    def test_dict_conversion(self):
        """Test converting configuration to dictionary."""
        config = Config(source_mode="microphone")
        config_dict = config.model_dump()

        assert isinstance(config_dict, dict)
        assert config_dict["source_mode"] == "microphone"
        assert "file_watcher" in config_dict
        assert "api" in config_dict
        assert "transcription" in config_dict
