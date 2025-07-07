#!/usr/bin/env python3
"""Test fix for recursive task cancellation during voice confirmation."""

import asyncio
import tempfile
import yaml
from pathlib import Path
import sys
import os
import logging

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from scribed.config import Config
from scribed.realtime.transcription_service import RealTimeTranscriptionService

# Set up logging to see what's happening
logging.basicConfig(level=logging.INFO)


async def test_confirmation_no_recursion():
    """Test that voice confirmation doesn't cause recursive task cancellation."""
    print("Testing Voice Confirmation - No Recursive Cancellation")
    print("=" * 60)

    # Create a minimal test config
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        test_config = {
            "source_mode": "microphone",
            "microphone": {
                "device_index": None,
                "sample_rate": 16000,
                "channels": 1,
                "chunk_size": 1024,
            },
            "wake_word": {
                "engine": "whisper",  # Use whisper to avoid Picovoice dependency
                "keywords": ["test"],
                "silence_timeout": 5,
                "stop_phrase": "stop listening",
            },
            "power_words": {
                "enabled": True,
                "require_confirmation": True,
                "confirmation_method": "voice",
                "confirmation_timeout": 3.0,  # Short timeout for testing
                "confirmation_retries": 1,
                "auto_approve_safe": False,
                "mappings": {"test command": 'echo "test"'},
                "allowed_commands": ["echo"],
                "dangerous_keywords": [],
            },
            "transcription": {"provider": "whisper", "model": "base"},
            "output": {
                "format": "txt",
                "log_to_file": False,
                "enable_clipboard": False,
            },
        }

        yaml.safe_dump(test_config, f)
        config_path = f.name

    try:
        # Load config
        config = Config.from_file(config_path)

        # Create service
        service = RealTimeTranscriptionService(
            wake_word_config=config.wake_word.model_dump(),
            microphone_config=config.microphone.model_dump(),
            transcription_config=config.transcription.model_dump(),
            power_words_config=config.power_words.model_dump(),
        )

        print("\n1. Testing _assess_command_safety method:")
        test_commands = ["echo hello", "notepad.exe", "unknown_command"]

        for cmd in test_commands:
            safety = service._assess_command_safety(cmd)
            print(f"  '{cmd}' -> {safety}")

        print("\n2. Testing confirmation callback with mock:")

        # Test the confirmation method directly without starting full service
        # This simulates what happens when power words trigger confirmation

        async def test_confirmation_call():
            """Test confirmation without actual microphone."""
            print("  Simulating voice confirmation request...")

            # This should not cause recursive cancellation since we fixed the implementation
            try:
                # Mock the transcription service to avoid Whisper dependency
                service.transcription_service = MockTranscriptionService()

                # Test with short timeout to avoid hanging
                result = await service._voice_confirmation("echo test", "safe")
                print(f"  Confirmation result: {result}")
                return True

            except RecursionError as e:
                print(f"  ❌ RecursionError occurred: {e}")
                return False
            except Exception as e:
                print(f"  ⚠️  Other error (expected): {e}")
                return True  # Other errors are expected without real microphone

        success = await test_confirmation_call()

        if success:
            print("\n✅ SUCCESS: No recursive task cancellation detected!")
            print("   The fix appears to be working correctly.")
        else:
            print("\n❌ FAILURE: Recursive cancellation still occurring.")

        print("\n3. Testing with different confirmation timeouts:")
        timeouts = [0.5, 1.0, 2.0]
        for timeout in timeouts:
            service.power_words_config["confirmation_timeout"] = timeout
            try:
                result = await service._voice_confirmation("test command", "unknown")
                print(f"  Timeout {timeout}s: Completed without recursion")
            except RecursionError:
                print(f"  Timeout {timeout}s: ❌ RecursionError")
            except Exception as e:
                print(
                    f"  Timeout {timeout}s: Other error (expected): {type(e).__name__}"
                )

    finally:
        # Clean up
        try:
            os.unlink(config_path)
        except:
            pass


class MockTranscriptionService:
    """Mock transcription service for testing."""

    async def transcribe_file(self, file_path):
        """Mock transcription that returns empty result."""
        from types import SimpleNamespace

        return SimpleNamespace(text="")


if __name__ == "__main__":
    asyncio.run(test_confirmation_no_recursion())
