"""Configuration management for Scribed."""

import os
import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional, Literal
from pydantic import BaseModel, Field, field_validator, model_validator


class AudioConfig(BaseModel):
    """Simplified audio configuration combining microphone and file settings."""

    source: Literal["microphone", "file"] = Field(default="microphone")

    # Microphone settings (flattened)
    device_index: Optional[int] = Field(default=None)
    sample_rate: int = Field(default=16000)
    channels: int = Field(default=1)

    # File watcher settings (flattened)
    watch_directory: str = Field(default="./audio_input")
    output_directory: str = Field(default="./transcripts")
    supported_formats: List[str] = Field(default=[".wav", ".mp3", ".flac"])

    @field_validator("watch_directory", "output_directory")
    @classmethod
    def validate_directories(cls, v: str) -> str:
        """Ensure directories exist or can be created."""
        path = Path(v)
        path.mkdir(parents=True, exist_ok=True)
        return str(path.resolve())


class TranscriptionConfig(BaseModel):
    """Simplified transcription configuration - removed complex SpeechLM2 support."""

    provider: Literal["whisper", "openai"] = Field(
        default="whisper",
        description="Transcription provider (whisper=local, openai=API)",
    )
    model: str = Field(
        default="base",
        description="Model name (whisper: base/small/medium/large, openai: whisper-1)",
    )
    language: str = Field(default="en", description="Language code for transcription")
    api_key: Optional[str] = Field(
        default=None, description="API key for OpenAI provider"
    )

    def model_post_init(self, __context: Any) -> None:
        """Set api_key from environment if not provided."""
        if self.api_key is None and self.provider == "openai":
            env_key = os.getenv("OPENAI_API_KEY")
            if env_key:
                object.__setattr__(self, "api_key", env_key)

    @model_validator(mode="after")
    def validate_provider_requirements(self) -> "TranscriptionConfig":
        """Validate provider-specific requirements."""
        if self.provider == "openai" and not self.api_key:
            raise ValueError(
                "OpenAI provider requires an API key. "
                "Set OPENAI_API_KEY environment variable or add api_key to config."
            )
        return self


class OutputConfig(BaseModel):
    """Simplified output configuration."""

    format: Literal["txt", "json"] = Field(default="txt")
    save_to_file: bool = Field(default=True)
    copy_to_clipboard: bool = Field(default=False)
    log_file_path: str = Field(default="./logs/transcription.log")

    @field_validator("log_file_path")
    @classmethod
    def validate_log_path(cls, v: str) -> str:
        """Ensure log directory exists."""
        path = Path(v)
        path.parent.mkdir(parents=True, exist_ok=True)
        return str(path.resolve())


class WakeWordConfig(BaseModel):
    """Optional wake word detection configuration.

    Wake word detection is disabled by default and requires explicit configuration.
    When enabled, it allows voice activation of transcription using keywords.
    """

    enabled: bool = Field(
        default=False,
        description="Enable wake word detection (requires pvporcupine and access key)",
    )
    keywords: List[str] = Field(
        default=["porcupine"],
        description="Wake word keywords to detect (built-in Picovoice keywords)",
    )
    access_key: Optional[str] = Field(
        default=None,
        description="Picovoice access key (get free key at console.picovoice.ai)",
    )
    engine: str = Field(
        default="picovoice",
        description="Wake word engine to use (picovoice or whisper)",
    )

    def model_post_init(self, __context: Any) -> None:
        """Set access_key from environment if not provided."""
        if self.access_key is None:
            env_key = os.getenv("PICOVOICE_ACCESS_KEY")
            if env_key:
                object.__setattr__(self, "access_key", env_key)

    @model_validator(mode="after")
    def validate_wake_word_requirements(self) -> "WakeWordConfig":
        """Validate wake word requirements when enabled (relaxed validation)."""
        if self.enabled:
            # Only warn about missing access key, don't fail validation
            # This allows the feature flag system to handle availability gracefully
            if not self.access_key and self.engine == "picovoice":
                import logging

                logger = logging.getLogger(__name__)
                logger.warning(
                    "Wake word detection enabled but no Picovoice access key found. "
                    "Set PICOVOICE_ACCESS_KEY environment variable or add access_key to config. "
                    "Feature will be disabled until requirements are met."
                )
        return self


class PowerWordsConfig(BaseModel):
    """Simplified voice commands configuration - basic command mapping only.

    Power words allow voice commands to execute system commands. This feature is
    disabled by default for security reasons and should be used with caution.
    """

    enabled: bool = Field(
        default=False,
        description="Enable voice commands (disabled by default for security)",
    )
    mappings: Dict[str, str] = Field(
        default_factory=dict,
        description="Simple phrase-to-command mappings (e.g., 'open notepad': 'notepad.exe')",
    )
    max_command_length: int = Field(
        default=100,
        description="Maximum command length for security (increased from 50 to 100)",
    )

    @model_validator(mode="after")
    def validate_basic_security(self) -> "PowerWordsConfig":
        """Basic security validation - simplified for essential safety only."""
        if not self.enabled:
            return self

        # Only block the most dangerous commands - keep it simple
        dangerous_keywords = [
            "rm -rf",
            "del /",
            "format",
            "shutdown /f",
            "reboot",
            "sudo rm",
        ]
        validated = {}

        for phrase, command in self.mappings.items():
            phrase = phrase.lower().strip()
            command = command.strip()

            # Skip empty mappings
            if not phrase or not command:
                continue

            # Basic length check
            if len(command) > self.max_command_length:
                import logging

                logger = logging.getLogger(__name__)
                logger.warning(
                    f"Skipping command that's too long (>{self.max_command_length} chars): {command[:30]}..."
                )
                continue

            # Check only for extremely dangerous patterns
            command_lower = command.lower()
            is_dangerous = False
            for dangerous in dangerous_keywords:
                if dangerous in command_lower:
                    import logging

                    logger = logging.getLogger(__name__)
                    logger.warning(
                        f"Skipping dangerous command: contains '{dangerous}'"
                    )
                    is_dangerous = True
                    break

            if not is_dangerous:
                validated[phrase] = command

        self.mappings = validated

        # Log final mappings for transparency
        if validated:
            import logging

            logger = logging.getLogger(__name__)
            logger.info(
                f"Power words configured with {len(validated)} safe command mappings"
            )

        return self


class APIConfig(BaseModel):
    """REST API configuration."""

    host: str = Field(default="127.0.0.1")
    port: int = Field(default=8080)
    debug: bool = Field(default=False)


class Config(BaseModel):
    """Main configuration class for Scribed."""

    # Core configuration sections
    audio: AudioConfig = Field(default_factory=AudioConfig)
    transcription: TranscriptionConfig = Field(default_factory=TranscriptionConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)

    # Optional features (disabled by default)
    wake_word: WakeWordConfig = Field(default_factory=WakeWordConfig)
    power_words: PowerWordsConfig = Field(default_factory=PowerWordsConfig)

    # API configuration
    api: APIConfig = Field(default_factory=APIConfig)

    @classmethod
    def from_file(cls, config_path: str) -> "Config":
        """Load configuration from YAML file with improved error messages."""
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(
                f"Configuration file not found: {config_path}\n"
                f"Create one by copying config.yaml.example to config.yaml"
            )

        try:
            with open(path, "r", encoding="utf-8") as f:
                config_data = yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in configuration file {config_path}: {e}")

        try:
            return cls(**config_data)
        except Exception as e:
            raise ValueError(f"Configuration validation failed: {e}")

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables or default file."""
        config_path = os.getenv("SCRIBED_CONFIG", "config.yaml")
        if Path(config_path).exists():
            return cls.from_file(config_path)
        return cls()

    def to_file(self, config_path: str) -> None:
        """Save configuration to YAML file."""
        path = Path(config_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(self.model_dump(), f, default_flow_style=False, sort_keys=False)

    def model_dump(self, **kwargs: Any) -> Dict[str, Any]:
        """Convert to dictionary with nested models."""
        return super().model_dump(by_alias=True, exclude_none=False, **kwargs)

    # Backwards compatibility methods
    def dict(self, **kwargs: Any) -> Dict[str, Any]:
        """Legacy method for backwards compatibility. Use model_dump() instead."""
        return self.model_dump(**kwargs)

    @property
    def source_mode(self) -> str:
        """Legacy property for backwards compatibility."""
        return self.audio.source

    @property
    def microphone(self) -> Dict[str, Any]:
        """Legacy property for backwards compatibility."""
        return {
            "device_index": self.audio.device_index,
            "sample_rate": self.audio.sample_rate,
            "channels": self.audio.channels,
        }

    @property
    def file_watcher(self) -> Dict[str, Any]:
        """Legacy property for backwards compatibility."""
        return {
            "watch_directory": self.audio.watch_directory,
            "output_directory": self.audio.output_directory,
            "supported_formats": self.audio.supported_formats,
        }
