"""Scribed - Audio Transcription Daemon.

A powerful audio transcription daemon that provides wake word detection,
voice commands, and both real-time and batch transcription capabilities.
"""

__version__ = "0.1.0"
__author__ = "Scribed Team"
__email__ = "team@scribed.dev"

from .daemon import ScribedDaemon
from .config import Config

__all__ = ["ScribedDaemon", "Config"]
