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
    """Engine for detecting and executing voice commands with security controls."""

    def __init__(self, config: PowerWordsConfig):
        """Initialize power words engine.

        Args:
            config: Power words configuration
        """
        self.config = config
        self.enabled = config.enabled
        self.mappings = {phrase.lower(): cmd for phrase, cmd in config.mappings.items()}
        self.require_confirmation = config.require_confirmation
        self.allowed_commands = [cmd.lower() for cmd in config.allowed_commands]
        self.blocked_commands = [cmd.lower() for cmd in config.blocked_commands]
        self.dangerous_keywords = [kw.lower() for kw in config.dangerous_keywords]
        self.max_command_length = config.max_command_length

        # Compile regex patterns for efficient matching
        self._compile_patterns()

        logger.info(f"PowerWordsEngine initialized with {len(self.mappings)} mappings")

    def _compile_patterns(self) -> None:
        """Compile regex patterns for power word detection."""
        self.patterns = {}
        for phrase in self.mappings.keys():
            # Create flexible pattern that allows for some variation
            # e.g., "open browser" matches "please open browser now"
            words = phrase.split()
            pattern = r"\b" + r"\s+".join(re.escape(word) for word in words) + r"\b"
            self.patterns[phrase] = re.compile(pattern, re.IGNORECASE)

    def detect_power_words(self, text: str) -> List[tuple]:
        """Detect power words in transcribed text.

        Args:
            text: Transcribed text to analyze

        Returns:
            List of tuples (phrase, command) for detected power words
        """
        if not self.enabled:
            return []

        detected = []
        text_lower = text.lower()

        for phrase, pattern in self.patterns.items():
            if pattern.search(text_lower):
                command = self.mappings[phrase]
                detected.append((phrase, command))
                logger.info(f"Detected power word: '{phrase}' -> '{command}'")

        return detected

    def validate_command(self, command: str) -> bool:
        """Validate command for security.

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

        # Check blocked commands
        if self.blocked_commands:
            for blocked in self.blocked_commands:
                if blocked in command_lower:
                    raise PowerWordsSecurityError(
                        f"Command contains blocked term: {blocked}"
                    )

        # Check allowed commands (if whitelist is configured)
        if self.allowed_commands:
            command_parts = command_lower.split()
            if command_parts and command_parts[0] not in self.allowed_commands:
                raise PowerWordsSecurityError(
                    f"Command not in allowed list: {command_parts[0]}"
                )

        # Check for dangerous keywords
        for dangerous in self.dangerous_keywords:
            if dangerous in command_lower:
                logger.warning(f"Command contains dangerous keyword: {dangerous}")
                # Don't raise error, but log warning

        return True

    def execute_command(
        self, command: str, confirm_callback: Optional[Callable[[], bool]] = None
    ) -> bool:
        """Execute a power word command.

        Args:
            command: Command to execute
            confirm_callback: Optional callback for user confirmation

        Returns:
            True if command was executed successfully
        """
        try:
            # Validate command security
            self.validate_command(command)

            # Request confirmation if required
            if self.require_confirmation and confirm_callback:
                if not confirm_callback():
                    logger.info(f"Command execution cancelled by user: {command}")
                    return False

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
    """Async version of PowerWordsEngine for integration with real-time transcription."""

    def __init__(self, config: PowerWordsConfig):
        """Initialize async power words engine.

        Args:
            config: Power words configuration
        """
        self.engine = PowerWordsEngine(config)
        self.confirmation_callback: Optional[Callable[[str, str], Awaitable[bool]]] = (
            None
        )

    def set_confirmation_callback(
        self, callback: Callable[[str, str], Awaitable[bool]]
    ) -> None:
        """Set async confirmation callback.

        Args:
            callback: Async function that takes (command, command_type) and returns True if user confirms execution
        """
        self.confirmation_callback = callback

    def _assess_command_type(self, command: str) -> str:
        """Assess the type/safety level of a command.

        Args:
            command: Command to assess

        Returns:
            "safe", "dangerous", or "unknown"
        """
        command_lower = command.lower()

        # Check for dangerous keywords from config
        if any(
            keyword.lower() in command_lower
            for keyword in self.engine.dangerous_keywords
        ):
            return "dangerous"

        # Check for safe patterns (applications, websites, simple shortcuts)
        import re

        safe_patterns = [
            r"\.lnk$",  # Windows shortcuts
            r"^https?://",  # URLs
            r"explorer\.exe",  # File explorer
            r"notepad",  # Simple applications
            r"chrome\.exe",  # Browser
            r"start menu",  # Start menu navigation
        ]

        for pattern in safe_patterns:
            if re.search(pattern, command_lower):
                return "safe"

        # Check allowed commands list
        if any(
            allowed.lower() in command_lower for allowed in self.engine.allowed_commands
        ):
            return "safe"

        return "unknown"

    async def execute_command_async(self, command: str) -> bool:
        """Execute command asynchronously.

        Args:
            command: Command to execute

        Returns:
            True if command was executed successfully
        """
        try:
            # Validate command security
            self.engine.validate_command(command)

            # Request confirmation if required
            if self.engine.require_confirmation and self.confirmation_callback:
                # Assess command type for confirmation
                command_type = self._assess_command_type(command)
                if not await self.confirmation_callback(command, command_type):
                    logger.info(f"Command execution cancelled by user: {command}")
                    return False

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
        """Process transcribed text for power words and execute commands asynchronously.

        Args:
            text: Transcribed text to process

        Returns:
            Number of commands executed
        """
        detected = self.engine.detect_power_words(text)
        executed_count = 0

        # Execute commands concurrently
        tasks = []
        for phrase, command in detected:
            logger.info(f"Processing power word: '{phrase}' -> '{command}'")
            task = self.execute_command_async(command)
            tasks.append(task)

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            executed_count = sum(1 for result in results if result is True)

        return executed_count


__all__ = ["PowerWordsEngine", "AsyncPowerWordsEngine", "PowerWordsSecurityError"]
