#!/usr/bin/env python3
"""Test script for wake word functionality."""

import asyncio
import logging
import sys
from pathlib import Path

# Add the src directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from scribed.config import Config
from scribed.realtime.transcription_service import RealTimeTranscriptionService


async def test_wake_word_dependencies():
    """Test that all wake word dependencies are available."""
    print("Testing wake word dependencies...")

    try:
        from scribed.wake_word import AsyncWakeWordEngine, WakeWordEngine
        from scribed.audio.microphone_input import AsyncMicrophoneInput
        from scribed.transcription.service import TranscriptionService

        print("✓ All imports successful")

        # Check dependency availability
        deps = RealTimeTranscriptionService.check_dependencies()
        print(f"Dependency check: {deps}")

        if all(deps.values()):
            print("✓ All dependencies available")
            return True
        else:
            print("✗ Some dependencies missing")
            return False

    except Exception as e:
        print(f"✗ Import error: {e}")
        return False


async def test_wake_word_engine():
    """Test wake word engine initialization."""
    print("\nTesting wake word engine...")

    try:
        from scribed.wake_word import AsyncWakeWordEngine, WakeWordEngine

        config = {
            "engine": "picovoice",
            "model_path": None  # Use built-in keywords
        }

        engine = AsyncWakeWordEngine(config)
        print("✓ Wake word engine created")

        if WakeWordEngine.is_available():
            print("✓ Wake word engine available")
            info = engine.get_info()
            print(f"Engine info: {info}")
            return True
        else:
            print("✗ Wake word engine not available")
            return False

    except Exception as e:
        print(f"✗ Wake word engine error: {e}")
        return False


async def test_microphone_input():
    """Test microphone input initialization."""
    print("\nTesting microphone input...")

    try:
        from scribed.audio.microphone_input import AsyncMicrophoneInput, MicrophoneInput

        config = {
            "device_index": None,
            "sample_rate": 16000,
            "channels": 1,
            "chunk_size": 1024
        }

        mic = AsyncMicrophoneInput(config)
        print("✓ Microphone input created")

        if MicrophoneInput.is_available():
            print("✓ Microphone input available")
            info = mic.get_info()
            print(f"Microphone info: {info}")
            return True
        else:
            print("✗ Microphone input not available")
            return False

    except Exception as e:
        print(f"✗ Microphone input error: {e}")
        return False


async def test_real_time_service():
    """Test real-time transcription service."""
    print("\nTesting real-time transcription service...")

    try:
        # Load test config
        config = Config.from_file("test_config.yaml")

        service = RealTimeTranscriptionService(
            wake_word_config=config.wake_word.dict(),
            microphone_config=config.microphone.dict(),
            transcription_config=config.transcription.dict()
        )

        print("✓ Real-time service created")

        # Get initial status
        status = service.get_status()
        print(f"Service status: {status}")

        return True

    except Exception as e:
        print(f"✗ Real-time service error: {e}")
        return False


async def main():
    """Run all tests."""
    print("Wake Word Functionality Test")
    print("=" * 40)

    logging.basicConfig(level=logging.INFO)

    tests = [
        test_wake_word_dependencies,
        test_wake_word_engine,
        test_microphone_input,
        test_real_time_service
    ]

    results = []
    for test in tests:
        try:
            result = await test()
            results.append(result)
        except Exception as e:
            print(f"Test failed with exception: {e}")
            results.append(False)

    print("\n" + "=" * 40)
    print("Test Results:")
    for i, (test, result) in enumerate(zip(tests, results)):
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{i+1}. {test.__name__}: {status}")

    if all(results):
        print("\n🎉 All tests passed! Wake word functionality is ready.")
        return 0
    else:
        print(f"\n❌ {len([r for r in results if not r])} test(s) failed.")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
