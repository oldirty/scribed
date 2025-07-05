#!/usr/bin/env python3
"""
Demo script for power words functionality.

This script demonstrates voice-activated command execution
with security controls.
"""

import sys
import asyncio
import logging
from pathlib import Path

# Add the src directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.scribed.config import Config
from src.scribed.power_words import PowerWordsEngine, AsyncPowerWordsEngine


def setup_logging():
    """Set up logging for the demo."""
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )


def demonstrate_power_words_detection():
    """Demonstrate power word detection."""
    print("🔍 Power Words Detection Demo")
    print("=" * 50)

    # Load configuration
    try:
        config = Config.from_file("test_config.yaml")
        power_config = config.power_words
    except FileNotFoundError:
        print("❌ test_config.yaml not found. Using default configuration.")
        from src.scribed.config import PowerWordsConfig

        power_config = PowerWordsConfig(
            enabled=True,
            require_confirmation=False,
            mappings={
                "hello world": "echo 'Hello from power words!'",
                "what time": "date",
                "show files": "ls -la",
                "where am i": "pwd",
            },
        )

    if not power_config.enabled:
        print("❌ Power words are disabled in configuration.")
        print("   Enable them in test_config.yaml to run this demo.")
        return

    engine = PowerWordsEngine(power_config)

    # Test phrases
    test_phrases = [
        "Hello world, how are you?",
        "Can you tell me what time it is?",
        "Please show files in this directory",
        "I'd like to know where am i located",
        "Random text with no commands",
        "hello world and what time is it please?",  # Multiple commands
    ]

    print(f"📋 Available power words: {list(power_config.mappings.keys())}")
    print()

    for phrase in test_phrases:
        print(f'📝 Testing: "{phrase}"')
        detected = engine.detect_power_words(phrase)

        if detected:
            for power_phrase, command in detected:
                print(f"   ✅ Detected: '{power_phrase}' → '{command}'")
        else:
            print("   ❌ No power words detected")
        print()


async def demonstrate_power_words_execution():
    """Demonstrate actual power word execution."""
    print("⚡ Power Words Execution Demo")
    print("=" * 50)

    # Load configuration
    try:
        config = Config.from_file("test_config.yaml")
        power_config = config.power_words
    except FileNotFoundError:
        print("❌ test_config.yaml not found. Skipping execution demo.")
        return

    if not power_config.enabled:
        print("❌ Power words are disabled in configuration.")
        return

    async_engine = AsyncPowerWordsEngine(power_config)

    # Test transcriptions that contain power words
    test_transcriptions = [
        "what time is it right now?",
        "hello world from the demo",
        "can you show me the calendar please?",
        "where am i currently located?",
    ]

    print("🎯 Executing power words from transcribed speech...")
    print()

    for transcription in test_transcriptions:
        print(f'🎤 Transcription: "{transcription}"')

        try:
            executed_count = await async_engine.process_transcription_async(
                transcription
            )
            if executed_count > 0:
                print(f"   ✅ Executed {executed_count} command(s)")
            else:
                print("   ❌ No commands executed")
        except Exception as e:
            print(f"   ❌ Error: {e}")

        print()


def demonstrate_security_features():
    """Demonstrate security features."""
    print("🔒 Security Features Demo")
    print("=" * 50)

    from src.scribed.config import PowerWordsConfig
    from src.scribed.power_words import PowerWordsSecurityError

    # Create a security-focused configuration
    secure_config = PowerWordsConfig(
        enabled=True,
        require_confirmation=True,
        max_command_length=30,
        allowed_commands=["echo", "date", "cal"],  # Whitelist
        blocked_commands=["rm", "delete", "sudo"],  # Blacklist
        dangerous_keywords=["format", "reboot"],
        mappings={
            "safe command": "echo 'This is safe'",
            "dangerous command": "rm important_file.txt",
            "blocked command": "sudo reboot now",
            "too long": "echo " + "a" * 50,
        },
    )

    engine = PowerWordsEngine(secure_config)

    test_commands = [
        ("echo 'safe command'", "Safe command"),
        ("rm file.txt", "Blocked command (rm)"),
        ("sudo reboot", "Blocked command (sudo)"),
        ("echo " + "a" * 50, "Command too long"),
        ("ls -la", "Not in allowed commands"),
        ("echo format disk", "Contains dangerous keyword"),
    ]

    print("🛡️  Testing security validation:")
    print()

    for command, description in test_commands:
        print(f"📝 Testing: {description}")
        print(f"   Command: {command[:50]}{'...' if len(command) > 50 else ''}")

        try:
            if engine.validate_command(command):
                print("   ✅ Command approved")
            else:
                print("   ❌ Command rejected")
        except PowerWordsSecurityError as e:
            print(f"   🚫 Security block: {e}")

        print()


def print_configuration_guide():
    """Print configuration guide."""
    print("📋 Power Words Configuration Guide")
    print("=" * 50)

    print(
        """
To use power words, configure them in your config.yaml:

power_words:
  enabled: true                    # Enable/disable power words
  require_confirmation: true       # Require confirmation before execution
  max_command_length: 100         # Maximum command length
  allowed_commands:               # Whitelist (empty = allow all)
    - "echo"
    - "date"
    - "cal"
  blocked_commands:               # Blacklist dangerous commands
    - "rm"
    - "delete"
    - "sudo"
  dangerous_keywords:             # Keywords that trigger warnings
    - "format"
    - "reboot"
  mappings:                       # Voice phrase → command mappings
    "what time is it": "date"
    "hello world": "echo 'Hello!'"
    "show calendar": "cal"

Security Notes:
• Power words are DISABLED by default for security
• Use allowed_commands whitelist for maximum security
• All commands are validated before execution
• Dangerous keywords log warnings but don't block
• Commands run in user's home directory with 30s timeout
"""
    )


async def main():
    """Run the power words demo."""
    setup_logging()

    print("🚀 Scribed Power Words Demo")
    print("=" * 50)
    print()

    # Show configuration guide
    print_configuration_guide()
    print()

    # Demonstrate detection
    demonstrate_power_words_detection()
    print()

    # Demonstrate execution
    await demonstrate_power_words_execution()
    print()

    # Demonstrate security
    demonstrate_security_features()
    print()

    print("🎉 Demo completed!")
    print()
    print("💡 Next steps:")
    print("   1. Configure your power words in config.yaml")
    print("   2. Start the daemon: scribed daemon --config test_config.yaml")
    print("   3. Say a wake word to activate transcription")
    print("   4. Say a power word phrase to execute commands")


if __name__ == "__main__":
    asyncio.run(main())
