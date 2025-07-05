"""Configuration management for Scribed."""

import os
import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, validator


class FileWatcherConfig(BaseModel):
    """Configuration for file watcher batch processing."""

    watch_directory: str = Field(default="./audio_input")
    output_directory: str = Field(default="./transcripts")
    supported_formats: List[str] = Field(default=[".wav", ".mp3", ".flac"])

    @validator("watch_directory", "output_directory")
    def validate_directories(cls, v: str) -> str:
        """Ensure directories exist or can be created."""
        path = Path(v)
        path.mkdir(parents=True, exist_ok=True)
        return str(path.absolute())


class MicrophoneConfig(BaseModel):
    """Configuration for microphone input."""

    device_index: Optional[int] = None
    sample_rate: int = Field(default=16000)
    channels: int = Field(default=1)
    chunk_size: int = Field(default=1024)


class WakeWordConfig(BaseModel):
    """Configuration for wake word detection."""

    engine: str = Field(default="picovoice")
    access_key: Optional[str] = Field(default=None)
    keywords: List[str] = Field(default=["porcupine"])
    sensitivities: List[float] = Field(default=[0.5])
    model_path: Optional[str] = None
    silence_timeout: int = Field(default=15)
    stop_phrase: str = Field(default="stop listening")


class PowerWordsConfig(BaseModel):
    """Configuration for voice commands."""

    enabled: bool = Field(default=False)
    mappings: Dict[str, str] = Field(default_factory=dict)
    require_confirmation: bool = Field(default=True)
    allowed_commands: List[str] = Field(default_factory=list)
    blocked_commands: List[str] = Field(default_factory=list)
    max_command_length: int = Field(default=100)
    dangerous_keywords: List[str] = Field(
        default_factory=lambda: [
            "rm",
            "delete",
            "format",
            "sudo",
            "admin",
            "reboot",
            "shutdown",
        ]
    )

    @validator("mappings")
    def validate_mappings(cls, v: Dict[str, str]) -> Dict[str, str]:
        """Validate power word mappings for security."""
        validated = {}
        for phrase, command in v.items():
            # Convert phrase to lowercase for consistency
            phrase = phrase.lower().strip()
            command = command.strip()

            # Basic security checks
            if len(command) > 100:
                raise ValueError(f"Command too long: {command[:50]}...")

            validated[phrase] = command

        return validated


class APIConfig(BaseModel):
    """Configuration for REST API."""

    host: str = Field(default="127.0.0.1")
    port: int = Field(default=8080)
    debug: bool = Field(default=False)


class TranscriptionConfig(BaseModel):
    """Configuration for transcription engines."""

    provider: str = Field(default="whisper")
    language: str = Field(default="en-US")
    model: str = Field(default="base")
    api_key: Optional[str] = None

    @validator("provider")
    def validate_provider(cls, v: str) -> str:
        """Validate transcription provider."""
        allowed_providers = ["whisper", "google_speech", "aws_transcribe"]
        if v not in allowed_providers:
            raise ValueError(f"Provider must be one of: {allowed_providers}")
        return v


class OutputConfig(BaseModel):
    """Configuration for output formatting."""

    format: str = Field(default="txt")
    log_to_file: bool = Field(default=True)
    log_file_path: str = Field(default="./logs/transcription.log")

    @validator("format")
    def validate_format(cls, v: str) -> str:
        """Validate output format."""
        allowed_formats = ["txt", "json", "srt"]
        if v not in allowed_formats:
            raise ValueError(f"Format must be one of: {allowed_formats}")
        return v

    @validator("log_file_path")
    def validate_log_path(cls, v: str) -> str:
        """Ensure log directory exists."""
        path = Path(v)
        path.parent.mkdir(parents=True, exist_ok=True)
        return str(path.absolute())


class Config(BaseModel):
    """Main configuration class for Scribed."""

    source_mode: str = Field(default="file")
    file_watcher: FileWatcherConfig = Field(default_factory=FileWatcherConfig)
    microphone: MicrophoneConfig = Field(default_factory=MicrophoneConfig)
    wake_word: WakeWordConfig = Field(default_factory=WakeWordConfig)
    power_words: PowerWordsConfig = Field(default_factory=PowerWordsConfig)
    api: APIConfig = Field(default_factory=APIConfig)
    transcription: TranscriptionConfig = Field(default_factory=TranscriptionConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)

    @validator("source_mode")
    def validate_source_mode(cls, v: str) -> str:
        """Validate source mode."""
        allowed_modes = ["file", "microphone"]
        if v not in allowed_modes:
            raise ValueError(f"Source mode must be one of: {allowed_modes}")
        return v

    @classmethod
    def from_file(cls, config_path: str) -> "Config":
        """Load configuration from YAML file."""
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        with open(path, "r", encoding="utf-8") as f:
            config_data = yaml.safe_load(f)

        return cls(**config_data)

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables."""
        config_path = os.getenv("SCRIBED_CONFIG", "config.yaml")
        if Path(config_path).exists():
            return cls.from_file(config_path)
        return cls()

    def to_file(self, config_path: str) -> None:
        """Save configuration to YAML file."""
        path = Path(config_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(self.dict(), f, default_flow_style=False, sort_keys=False)

    def dict(self, **kwargs: Any) -> Dict[str, Any]:
        """Convert to dictionary with nested models."""
        return super().dict(by_alias=True, exclude_none=False, **kwargs)
