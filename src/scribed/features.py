"""Feature flags for optional Scribed functionality."""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class FeatureFlags:
    """Centralized feature flag management for optional features.

    This class provides a unified way to check if optional features are enabled
    and available, with proper dependency checking and graceful degradation.
    """

    def __init__(self, config: Dict[str, Any]):
        """Initialize feature flags from configuration.

        Args:
            config: Full configuration dictionary
        """
        self.config = config
        self._availability_cache: Dict[str, bool] = {}

    def is_wake_word_enabled(self) -> bool:
        """Check if wake word detection is enabled and available.

        Returns:
            True if wake word detection is enabled in config AND dependencies are available
        """
        # Feature must be explicitly enabled in config (defaults to False)
        if not self.config.get("wake_word", {}).get("enabled", False):
            return False

        return self._check_wake_word_availability()

    def is_power_words_enabled(self) -> bool:
        """Check if power words (voice commands) are enabled.

        Returns:
            True if power words are enabled in config (defaults to False for security)
        """
        # Feature must be explicitly enabled in config (defaults to False for security)
        return self.config.get("power_words", {}).get("enabled", False)

    def _check_wake_word_availability(self) -> bool:
        """Check if wake word detection dependencies are available.

        Returns:
            True if all required dependencies are installed and configured
        """
        if "wake_word" in self._availability_cache:
            return self._availability_cache["wake_word"]

        try:
            # Check for required dependencies
            import pvporcupine
            import pyaudio

            # Check if access key is available
            wake_word_config = self.config.get("wake_word", {})
            access_key = wake_word_config.get("access_key")

            if not access_key:
                import os

                access_key = os.getenv("PICOVOICE_ACCESS_KEY")

            available = access_key is not None
            self._availability_cache["wake_word"] = available

            if not available:
                logger.warning(
                    "Wake word detection enabled but no access key found. "
                    "Set PICOVOICE_ACCESS_KEY environment variable or add access_key to config."
                )

            return available

        except ImportError as e:
            logger.info(f"Wake word detection dependencies not available: {e}")
            logger.info(
                "To enable wake word detection, install: pip install pvporcupine pyaudio"
            )
            self._availability_cache["wake_word"] = False
            return False

    def _check_power_words_availability(self) -> bool:
        """Check if power words have valid configuration.

        Returns:
            True if power words are properly configured
        """
        if not self.is_power_words_enabled():
            return False

        mappings = self.config.get("power_words", {}).get("mappings", {})
        return len(mappings) > 0

    def get_enabled_features(self) -> Dict[str, bool]:
        """Get status of all optional features.

        Returns:
            Dictionary mapping feature names to their enabled/available status
        """
        return {
            "wake_word": self.is_wake_word_enabled(),
            "power_words": self.is_power_words_enabled()
            and self._check_power_words_availability(),
        }

    def get_feature_status(self) -> Dict[str, Dict[str, Any]]:
        """Get detailed status information for all optional features.

        Returns:
            Dictionary with detailed status for each feature
        """
        status = {}

        # Wake word status
        wake_word_config = self.config.get("wake_word", {})
        status["wake_word"] = {
            "enabled_in_config": wake_word_config.get("enabled", False),
            "dependencies_available": (
                self._check_wake_word_availability()
                if wake_word_config.get("enabled", False)
                else None
            ),
            "fully_available": self.is_wake_word_enabled(),
            "description": "Voice activation using wake words (requires Picovoice access key)",
        }

        # Power words status
        power_words_config = self.config.get("power_words", {})
        status["power_words"] = {
            "enabled_in_config": power_words_config.get("enabled", False),
            "has_mappings": len(power_words_config.get("mappings", {})) > 0,
            "fully_available": self.is_power_words_enabled()
            and self._check_power_words_availability(),
            "description": "Voice commands that execute system commands (use with caution)",
        }

        return status

    def validate_feature_requirements(self) -> Dict[str, Optional[str]]:
        """Validate that enabled features have their requirements met.

        Returns:
            Dictionary mapping feature names to error messages (None if valid)
        """
        validation_results = {}

        # Validate wake word requirements
        wake_word_config = self.config.get("wake_word", {})
        if wake_word_config.get("enabled", False):
            if not self._check_wake_word_availability():
                validation_results["wake_word"] = (
                    "Wake word detection enabled but requirements not met. "
                    "Install dependencies: pip install pvporcupine pyaudio "
                    "and set PICOVOICE_ACCESS_KEY environment variable"
                )
            else:
                validation_results["wake_word"] = None
        else:
            validation_results["wake_word"] = None

        # Validate power words requirements
        power_words_config = self.config.get("power_words", {})
        if power_words_config.get("enabled", False):
            mappings = power_words_config.get("mappings", {})
            if not mappings:
                validation_results["power_words"] = (
                    "Power words enabled but no command mappings configured. "
                    "Add command mappings to power_words.mappings in your config."
                )
            else:
                validation_results["power_words"] = None
        else:
            validation_results["power_words"] = None

        return validation_results

    def log_feature_status(self) -> None:
        """Log the current status of all optional features."""
        logger.info("Optional feature status:")

        status = self.get_feature_status()
        for feature_name, feature_status in status.items():
            if feature_status["fully_available"]:
                logger.info(f"  ✓ {feature_name}: enabled and available")
            elif feature_status["enabled_in_config"]:
                logger.warning(
                    f"  ⚠ {feature_name}: enabled but not available (check requirements)"
                )
            else:
                logger.info(f"  - {feature_name}: disabled")


def create_feature_flags(config: Dict[str, Any]) -> FeatureFlags:
    """Factory function to create feature flags from configuration.

    Args:
        config: Configuration dictionary

    Returns:
        FeatureFlags instance
    """
    return FeatureFlags(config)
