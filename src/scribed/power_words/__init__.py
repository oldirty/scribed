"""Power words (voice commands) functionality for Scribed."""

import re
import subprocess
import logging
import asyncio
from typing import Dict, List, Optional, Callable, Awaitable
from pathlib import Path

from ..config import PowerWordsConfig

logger = logging.getLogger(__name__)


class PowerWordsSecurityError(Exception):
    """Raised when a power word command fails security checks."""

    pass


class PowerWordsEngine:
    """Simplified engine for basic voice command mapping.

    This is a basic implementation that maps voice phrases to system commands.
    It uses simple string matching for reliability and security.
    """

    def __init__(self, config: PowerWordsConfig):
        """Initialize power words engine.

        Args:
            config: Power words configuration
        """
        self.config = config
        self.enabled = config.enabled
        self.mappings = {
            phrase.lower().strip(): cmd.strip()
            for phrase, cmd in config.mappings.items()
        }
        self.max_command_length = config.max_command_length

        logger.info(f"PowerWordsEngine initialized with {len(self.mappings)} mappings")
        if self.enabled and self.mappings:
            logger.info(f"Available voice commands: {list(self.mappings.keys())}")

    def _normalize_text(self, text: str) -> str:
        """Normalize text for consistent matching."""
        return text.lower().strip()

    def detect_power_words(self, text: str) -> List[tuple]:
        """Detect power words in transcribed text using simple string matching.

        Args:
            text: Transcribed text to analyze

        Returns:
            List of tuples (phrase, command) for detected power words
        """
        if not self.enabled or not self.mappings:
            return []

        detected = []
        normalized_text = self._normalize_text(text)

        # Use simple substring matching for reliability
        for phrase, command in self.mappings.items():
            if phrase in normalized_text:
                detected.append((phrase, command))
                logger.info(f"Detected power word: '{phrase}' -> '{command}'")

        return detected

    def validate_command(self, command: str) -> bool:
        """Basic command validation for security.

        Args:
            command: Command to validate

        Returns:
            True if command is safe to execute

        Raises:
            PowerWordsSecurityError: If command fails security checks
        """
        command_lower = command.lower()

        # Check command length
        if len(command) > self.max_command_length:
            raise PowerWordsSecurityError(
                f"Command too long: {len(command)} > {self.max_command_length}"
            )

        # Basic security check for extremely dangerous patterns
        dangerous_patterns = [
            "rm -rf",
            "del /",
            "format",
            "shutdown /f",
            "reboot",
            "sudo rm",
        ]
        for dangerous in dangerous_patterns:
            if dangerous in command_lower:
                raise PowerWordsSecurityError(
                    f"Command blocked for safety: contains '{dangerous}'"
                )

        return True

    def execute_command(
        self, command: str, confirm_callback: Optional[Callable[[], bool]] = None
    ) -> bool:
        """Execute a power word command (simplified - no confirmation required).

        Args:
            command: Command to execute
            confirm_callback: Optional callback for user confirmation (unused in simplified version)

        Returns:
            True if command was executed successfully
        """
        try:
            # Validate command security
            self.validate_command(command)

            logger.info(f"Executing power word command: {command}")

            # Execute command in a safe shell environment
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30,  # 30 second timeout
                cwd=Path.home(),  # Execute from user's home directory
            )

            if result.returncode == 0:
                logger.info(f"Command executed successfully: {command}")
                if result.stdout:
                    logger.debug(f"Command output: {result.stdout}")
                return True
            else:
                logger.error(f"Command failed with code {result.returncode}: {command}")
                if result.stderr:
                    logger.error(f"Command error: {result.stderr}")
                return False

        except PowerWordsSecurityError as e:
            logger.error(f"Security check failed for command '{command}': {e}")
            return False
        except subprocess.TimeoutExpired:
            logger.error(f"Command timed out: {command}")
            return False
        except Exception as e:
            logger.error(f"Failed to execute command '{command}': {e}")
            return False

    def process_transcription(
        self, text: str, confirm_callback: Optional[Callable[[], bool]] = None
    ) -> int:
        """Process transcribed text for power words and execute commands.

        Args:
            text: Transcribed text to process
            confirm_callback: Optional callback for user confirmation

        Returns:
            Number of commands executed
        """
        detected = self.detect_power_words(text)
        executed_count = 0

        for phrase, command in detected:
            logger.info(f"Processing power word: '{phrase}' -> '{command}'")

            if self.execute_command(command, confirm_callback):
                executed_count += 1
            else:
                logger.warning(f"Failed to execute power word command: {command}")

        return executed_count


class AsyncPowerWordsEngine:
    """Simplified async wrapper for PowerWordsEngine.

    This provides basic async support for power words without complex confirmation
    or concurrent execution features.
    """

    def __init__(self, config: PowerWordsConfig):
        """Initialize async power words engine.

        Args:
            config: Power words configuration
        """
        self.engine = PowerWordsEngine(config)

    async def execute_command_async(self, command: str) -> bool:
        """Execute command asynchronously (simplified).

        Args:
            command: Command to execute

        Returns:
            True if command was executed successfully
        """
        try:
            # Validate command security
            self.engine.validate_command(command)

            logger.info(f"Executing power word command: {command}")

            # Execute command in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=30,
                    cwd=Path.home(),
                ),
            )

            if result.returncode == 0:
                logger.info(f"Command executed successfully: {command}")
                if result.stdout:
                    logger.debug(f"Command output: {result.stdout}")
                return True
            else:
                logger.error(f"Command failed with code {result.returncode}: {command}")
                if result.stderr:
                    logger.error(f"Command error: {result.stderr}")
                return False

        except PowerWordsSecurityError as e:
            logger.error(f"Security check failed for command '{command}': {e}")
            return False
        except asyncio.TimeoutError:
            logger.error(f"Command timed out: {command}")
            return False
        except Exception as e:
            logger.error(f"Failed to execute command '{command}': {e}")
            return False

    async def process_transcription_async(self, text: str) -> int:
        """Process transcribed text for power words and execute commands.

        Args:
            text: Transcribed text to process

        Returns:
            Number of commands executed
        """
        detected = self.engine.detect_power_words(text)
        executed_count = 0

        # Execute commands sequentially for simplicity and safety
        for phrase, command in detected:
            logger.info(f"Processing power word: '{phrase}' -> '{command}'")
            if await self.execute_command_async(command):
                executed_count += 1

        return executed_count


__all__ = ["PowerWordsEngine", "AsyncPowerWordsEngine", "PowerWordsSecurityError"]
