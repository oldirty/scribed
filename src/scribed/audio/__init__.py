"""Audio processing package for Scribed."""

from .base import (
    AudioSource,
    AudioChunk,
    AudioData,
    AudioFormat,
    AudioError,
    AudioValidationError,
    AudioDeviceError,
    AudioFormatConverter,
)
from .file_watcher import FileWatcher, FileWatcherSource
from .file_source import FileSource
from .microphone import MicrophoneSource

__all__ = [
    "AudioSource",
    "AudioChunk",
    "AudioData",
    "AudioFormat",
    "AudioError",
    "AudioValidationError",
    "AudioDeviceError",
    "AudioFormatConverter",
    "FileWatcher",
    "FileWatcherSource",
    "FileSource",
    "MicrophoneSource",
]
