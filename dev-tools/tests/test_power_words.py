#!/usr/bin/env python3
"""
Test script for power words functionality.

This script tests the power words detection and execution engine
with various security scenarios.
"""

import sys
import asyncio
import logging
from pathlib import Path

# Add the src directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.scribed.config import Config, PowerWordsConfig
from src.scribed.power_words import (
    PowerWordsEngine,
    AsyncPowerWordsEngine,
    PowerWordsSecurityError,
)


def setup_logging():
    """Set up logging for testing."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


def test_power_words_config():
    """Test power words configuration."""
    print("🔧 Testing Power Words Configuration...")

    # Test basic config
    config = PowerWordsConfig(
        enabled=True,
        mappings={
            "hello world": "echo 'Hello from power words!'",
            "what time": "date",
            "show files": "ls -la",
        },
    )

    assert config.enabled is True
    assert len(config.mappings) == 3
    assert "hello world" in config.mappings
    print("✅ Basic configuration works")

    # Test security validation
    try:
        PowerWordsConfig(mappings={"test": "a" * 150})  # Too long
        assert False, "Should have raised validation error"
    except ValueError:
        print("✅ Command length validation works")

    print("✅ Configuration tests passed\n")


def test_power_words_detection():
    """Test power word detection in text."""
    print("🔍 Testing Power Words Detection...")

    config = PowerWordsConfig(
        enabled=True,
        mappings={
            "hello world": "echo 'Hello!'",
            "what time": "date",
            "show files": "ls -la",
            "open browser": "firefox",
        },
    )

    engine = PowerWordsEngine(config)

    # Test exact matches
    detected = engine.detect_power_words("hello world")
    assert len(detected) == 1
    assert detected[0] == ("hello world", "echo 'Hello!'")
    print("✅ Exact match detection works")

    # Test partial matches within sentences
    detected = engine.detect_power_words("Can you show files please?")
    assert len(detected) == 1
    assert detected[0] == ("show files", "ls -la")
    print("✅ Partial match detection works")

    # Test case insensitivity
    detected = engine.detect_power_words("WHAT TIME is it?")
    assert len(detected) == 1
    assert detected[0] == ("what time", "date")
    print("✅ Case insensitive detection works")

    # Test multiple detections
    detected = engine.detect_power_words("hello world and what time is it?")
    assert len(detected) == 2
    print("✅ Multiple detection works")

    # Test no matches
    detected = engine.detect_power_words("random text with no commands")
    assert len(detected) == 0
    print("✅ No false positives")

    print("✅ Detection tests passed\n")


def test_security_validation():
    """Test security validation."""
    print("🔒 Testing Security Validation...")

    config = PowerWordsConfig(
        enabled=True,
        max_command_length=20,
        allowed_commands=["echo", "date"],
        blocked_commands=["rm", "delete"],
        dangerous_keywords=["sudo", "reboot"],
        mappings={
            "safe command": "echo test",
            "blocked command": "rm file.txt",
            "dangerous command": "sudo reboot",
            "too long command": "a" * 25,
            "allowed command": "date",
        },
    )

    engine = PowerWordsEngine(config)

    # Test safe command
    try:
        assert engine.validate_command("echo test") is True
        print("✅ Safe command validation works")
    except PowerWordsSecurityError:
        assert False, "Safe command should pass"

    # Test command too long
    try:
        engine.validate_command("a" * 25)
        assert False, "Should have raised security error"
    except PowerWordsSecurityError:
        print("✅ Command length validation works")

    # Test blocked command
    try:
        engine.validate_command("rm file.txt")
        assert False, "Should have raised security error"
    except PowerWordsSecurityError:
        print("✅ Blocked command validation works")

    # Test allowed commands whitelist
    try:
        engine.validate_command("ls -la")  # Not in allowed list
        assert False, "Should have raised security error"
    except PowerWordsSecurityError:
        print("✅ Allowed commands whitelist works")

    # Test dangerous keyword warning (should pass but log warning)
    try:
        assert engine.validate_command("echo sudo test") is True
        print("✅ Dangerous keyword warning works")
    except PowerWordsSecurityError:
        assert False, "Should only warn, not block"

    print("✅ Security validation tests passed\n")


async def test_async_power_words():
    """Test async power words functionality."""
    print("⚡ Testing Async Power Words...")

    config = PowerWordsConfig(
        enabled=True,
        require_confirmation=False,  # Disable for testing
        allowed_commands=["echo", "pwd", "where"],  # Windows-compatible commands
        mappings={
            "hello": "echo Hello from async power words!",
            "location": "pwd",  # Use pwd which should work cross-platform
        },
    )

    async_engine = AsyncPowerWordsEngine(config)

    # Test successful execution
    success = await async_engine.execute_command_async("echo Test successful")
    assert success is True
    print("✅ Async command execution works")

    # Test transcription processing with single command
    executed_count = await async_engine.process_transcription_async("hello there")
    assert executed_count == 1  # Should execute "hello"
    print("✅ Async transcription processing works")

    print("✅ Async tests passed\n")


def test_power_words_disabled():
    """Test that disabled power words don't execute."""
    print("🚫 Testing Disabled Power Words...")

    config = PowerWordsConfig(
        enabled=False, mappings={"test": "echo 'Should not execute'"}  # Disabled
    )

    engine = PowerWordsEngine(config)

    # Should return no detections when disabled
    detected = engine.detect_power_words("test command")
    assert len(detected) == 0
    print("✅ Disabled power words don't detect")

    executed = engine.process_transcription("test command")
    assert executed == 0
    print("✅ Disabled power words don't execute")

    print("✅ Disabled tests passed\n")


async def main():
    """Run all power words tests."""
    setup_logging()

    print("🚀 Starting Power Words Tests\n")

    try:
        # Test configuration
        test_power_words_config()

        # Test detection
        test_power_words_detection()

        # Test security
        test_security_validation()

        # Test async functionality
        await test_async_power_words()

        # Test disabled functionality
        test_power_words_disabled()

        print("🎉 All Power Words Tests Passed!")

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
