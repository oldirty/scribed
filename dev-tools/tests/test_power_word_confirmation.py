#!/usr/bin/env python3
"""Test enhanced power word confirmation functionality."""

import asyncio
import tempfile
import yaml
from pathlib import Path
import sys
import os

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from scribed.config import PowerWordsConfig
from scribed.power_words import AsyncPowerWordsEngine


async def test_confirmation_callbacks():
    """Test different confirmation scenarios."""
    print("Testing Enhanced Power Word Confirmation")
    print("=" * 50)

    # Create test config
    config_data = {
        "enabled": True,
        "require_confirmation": True,
        "confirmation_method": "voice",
        "confirmation_timeout": 5.0,
        "confirmation_retries": 1,
        "auto_approve_safe": False,
        "log_only_approve": True,
        "mappings": {
            "open notepad": "notepad.exe",
            "dangerous command": "rm -rf /",
            "safe shortcut": "explorer.exe",
        },
        "dangerous_keywords": ["rm", "delete", "format", "sudo"],
        "allowed_commands": ["notepad.exe", "explorer.exe", "rm"],  # Allow for testing
    }

    config = PowerWordsConfig(**config_data)
    engine = AsyncPowerWordsEngine(config)

    # Test command type assessment
    print("\n1. Testing Command Type Assessment:")
    test_commands = ["notepad.exe", "rm -rf /", "explorer.exe", "unknown_command.exe"]

    for cmd in test_commands:
        cmd_type = engine._assess_command_type(cmd)
        print(f"  '{cmd}' -> {cmd_type}")

    # Test confirmation with mock callback
    print("\n2. Testing Confirmation Callbacks:")

    confirmation_responses = {}

    async def mock_confirmation_callback(command: str, command_type: str) -> bool:
        """Mock confirmation that responds based on command type."""
        print(f"  Confirmation requested for {command_type} command: '{command}'")

        # Simulate different responses
        if command_type == "safe":
            result = True
            print(f"    -> Auto-approving safe command")
        elif command_type == "dangerous":
            result = False
            print(f"    -> Auto-denying dangerous command")
        else:
            result = True  # For testing
            print(f"    -> Allowing unknown command for test")

        confirmation_responses[command] = result
        return result

    engine.set_confirmation_callback(mock_confirmation_callback)

    # Test different commands
    test_commands = [
        "notepad.exe",  # safe
        "rm -rf /",  # dangerous but allowed for testing
        "explorer.exe",  # safe
    ]

    for cmd in test_commands:
        print(f"\n  Testing command: '{cmd}'")
        try:
            result = await engine.execute_command_async(cmd)
            print(f"    Execution result: {result}")
        except Exception as e:
            print(f"    Error: {e}")

    print(f"\n3. Confirmation Results Summary:")
    for cmd, response in confirmation_responses.items():
        print(f"  '{cmd}' -> {'Approved' if response else 'Denied'}")


if __name__ == "__main__":
    asyncio.run(test_confirmation_callbacks())
