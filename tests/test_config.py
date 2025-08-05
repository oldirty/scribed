"""Test configuration management."""

import pytest
import tempfile
import yaml
from pathlib import Path

from scribed.config import (
    Config,
    AudioConfig,
    APIConfig,
    TranscriptionConfig,
    OutputConfig,
    PowerWordsConfig,
    WakeWordConfig,
)


class TestAudioConfig:
    """Test AudioConfig class (simplified - combines microphone and file settings)."""

    def test_default_values(self):
        """Test default configuration values."""
        config = AudioConfig()
        assert config.source == "microphone"
        assert config.device_index is None
        assert config.sample_rate == 16000
        assert config.channels == 1

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

            config = AudioConfig(
                source="file",
                device_index=1,
                sample_rate=44100,
                channels=2,
                watch_directory=str(custom_input),
                output_directory=str(custom_output),
                supported_formats=[".wav", ".mp3"],
            )

            assert config.source == "file"
            assert config.device_index == 1
            assert config.sample_rate == 44100
            assert config.channels == 2

            # Normalize paths for comparison
            expected_watch = custom_input.resolve()
            expected_output = custom_output.resolve()
            actual_watch = Path(config.watch_directory).resolve()
            actual_output = Path(config.output_directory).resolve()

            assert actual_watch == expected_watch
            assert actual_output == expected_output
            assert config.supported_formats == [".wav", ".mp3"]


class TestAPIConfig:
    """Test APIConfig class."""

    def test_default_values(self):
        """Test default configuration values."""
        config = APIConfig()
        assert config.host == "127.0.0.1"
        assert config.port == 8080
        assert config.debug is False


class TestTranscriptionConfig:
    """Test TranscriptionConfig class (simplified - removed SpeechLM2)."""

    def test_default_values(self):
        """Test default configuration values."""
        config = TranscriptionConfig()
        assert config.provider == "whisper"
        assert config.language == "en"
        assert config.model == "base"
        assert config.api_key is None

    def test_valid_providers(self):
        """Test valid provider values (simplified)."""
        # Test whisper provider (no API key required)
        config = TranscriptionConfig(provider="whisper")
        assert config.provider == "whisper"

        # Test openai provider with API key
        config = TranscriptionConfig(provider="openai", api_key="test-key")
        assert config.provider == "openai"

    def test_openai_api_key_validation(self):
        """Test OpenAI API key validation."""
        # Should not raise error when api_key is provided
        config = TranscriptionConfig(provider="openai", api_key="test-key")
        assert config.api_key == "test-key"


class TestOutputConfig:
    """Test OutputConfig class (simplified)."""

    def test_default_values(self):
        """Test default configuration values."""
        config = OutputConfig()
        assert config.format == "txt"
        assert config.save_to_file is True
        assert config.copy_to_clipboard is False

        # Normalize paths for comparison
        expected_log_path = Path("./logs/transcription.log").resolve()
        actual_log_path = Path(config.log_file_path).resolve()
        assert actual_log_path == expected_log_path

    def test_valid_formats(self):
        """Test valid format values (simplified)."""
        for fmt in ["txt", "json"]:
            config = OutputConfig(format=fmt)
            assert config.format == fmt


class TestPowerWordsConfig:
    """Test PowerWordsConfig class (simplified)."""

    def test_default_values(self):
        """Test default configuration values."""
        config = PowerWordsConfig()
        assert config.enabled is False
        assert config.mappings == {}
        assert config.max_command_length == 100

    def test_custom_mappings(self):
        """Test custom power word mappings."""
        mappings = {"open browser": "firefox", "open notepad": "notepad.exe"}
        config = PowerWordsConfig(enabled=True, mappings=mappings)
        assert config.enabled is True
        assert config.mappings == mappings

    def test_security_validation(self):
        """Test security validation of dangerous commands."""
        # Dangerous commands should be filtered out
        dangerous_mappings = {
            "safe command": "notepad.exe",
            "dangerous command": "rm -rf /",
            "another safe": "calc.exe",
        }
        config = PowerWordsConfig(enabled=True, mappings=dangerous_mappings)
        # Should only keep safe commands
        assert "safe command" in config.mappings
        assert "another safe" in config.mappings
        assert "dangerous command" not in config.mappings


class TestWakeWordConfig:
    """Test WakeWordConfig class (simplified)."""

    def test_default_values(self):
        """Test default configuration values."""
        # Temporarily clear environment variable for this test
        import os

        original_key = os.environ.get("PICOVOICE_ACCESS_KEY")
        if "PICOVOICE_ACCESS_KEY" in os.environ:
            del os.environ["PICOVOICE_ACCESS_KEY"]

        try:
            config = WakeWordConfig()
            assert config.enabled is False
            assert config.engine == "picovoice"
            assert config.keywords == ["porcupine"]
            assert config.access_key is None
        finally:
            # Restore original environment variable
            if original_key is not None:
                os.environ["PICOVOICE_ACCESS_KEY"] = original_key

    def test_custom_values(self):
        """Test custom configuration values."""
        config = WakeWordConfig(
            enabled=True,
            engine="whisper",
            keywords=["hey scribed", "wake up"],
            access_key="test-key",
        )
        assert config.enabled is True
        assert config.engine == "whisper"
        assert config.keywords == ["hey scribed", "wake up"]
        assert config.access_key == "test-key"


class TestConfig:
    """Test main Config class (simplified structure)."""

    def test_default_values(self):
        """Test default configuration values."""
        config = Config()
        assert config.audio.source == "microphone"
        assert isinstance(config.audio, AudioConfig)
        assert isinstance(config.wake_word, WakeWordConfig)
        assert isinstance(config.power_words, PowerWordsConfig)
        assert isinstance(config.api, APIConfig)
        assert isinstance(config.transcription, TranscriptionConfig)
        assert isinstance(config.output, OutputConfig)

    def test_from_env_with_no_file(self):
        """Test loading configuration from environment when no file exists."""
        config = Config.from_env()
        assert isinstance(config, Config)
        assert config.audio.source == "microphone"  # Default value

    def test_from_file_not_found(self):
        """Test loading configuration from non-existent file."""
        with pytest.raises(FileNotFoundError):
            Config.from_file("non_existent_file.yaml")

    def test_from_file_valid(self):
        """Test loading configuration from valid YAML file."""
        config_data = {
            "audio": {"source": "file", "sample_rate": 44100},
            "api": {"host": "0.0.0.0", "port": 9000},
            "transcription": {
                "provider": "whisper",
                "language": "fr",
                "model": "small",
            },
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_data, f)
            temp_path = f.name

        try:
            config = Config.from_file(temp_path)
            assert config.audio.source == "file"
            assert config.audio.sample_rate == 44100
            assert config.api.host == "0.0.0.0"
            assert config.api.port == 9000
            assert config.transcription.provider == "whisper"
            assert config.transcription.language == "fr"
            assert config.transcription.model == "small"
        finally:
            Path(temp_path).unlink()

    def test_to_file(self):
        """Test saving configuration to file."""
        config = Config(
            audio=AudioConfig(source="file", sample_rate=44100),
            api=APIConfig(host="0.0.0.0", port=9000),
        )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            temp_path = f.name

        try:
            config.to_file(temp_path)

            # Verify file was created and has correct content
            assert Path(temp_path).exists()

            with open(temp_path, "r") as f:
                saved_data = yaml.safe_load(f)

            assert saved_data["audio"]["source"] == "file"
            assert saved_data["audio"]["sample_rate"] == 44100
            assert saved_data["api"]["host"] == "0.0.0.0"
            assert saved_data["api"]["port"] == 9000

        finally:
            Path(temp_path).unlink()

    def test_dict_conversion(self):
        """Test converting configuration to dictionary."""
        config = Config(audio=AudioConfig(source="file"))
        config_dict = config.model_dump()

        assert isinstance(config_dict, dict)
        assert config_dict["audio"]["source"] == "file"
        assert "audio" in config_dict
        assert "api" in config_dict
        assert "transcription" in config_dict

    def test_backward_compatibility_properties(self):
        """Test backward compatibility properties."""
        config = Config(audio=AudioConfig(source="microphone", device_index=1))

        # Test legacy properties
        assert config.source_mode == "microphone"
        assert config.microphone["device_index"] == 1
        assert config.microphone["sample_rate"] == 16000


# Configuration migration tests removed - functionality simplified
