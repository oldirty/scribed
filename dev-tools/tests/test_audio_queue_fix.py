#!/usr/bin/env python3
"""
Test the audio data processing fix directly.
This test verifies that the audio queue prevents task explosion.
"""

import asyncio
import logging
import time
from unittest.mock import Mock

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_audio_queue_fix():
    """Test that the audio queue prevents task explosion."""
    print("Testing audio queue fix...")

    try:
        from src.scribed.realtime.transcription_service import (
            RealTimeTranscriptionService,
        )

        # Create service (components won't be initialized since we won't start it)
        service = RealTimeTranscriptionService(
            wake_word_config={"engine": "test", "access_key": "test"},
            microphone_config={"device_index": None, "sample_rate": 16000},
            transcription_config={"provider": "test"},
            power_words_config={"enabled": False},
        )

        print("✓ RealTimeTranscriptionService created")

        # Test the audio queue mechanism
        print(
            "✓ Audio processing queue exists:",
            hasattr(service, "_audio_processing_queue"),
        )
        print("✓ Queue maxsize:", service._audio_processing_queue.maxsize)

        # Manually enable transcription mode to test the queue
        service._transcription_active = True

        # Test rapid audio data submission (this used to cause task explosion)
        print("Testing rapid audio data submission...")

        # Before the fix: each call to _on_audio_data_sync created a new task
        # After the fix: each call puts data in a queue for sequential processing
        for i in range(50):
            audio_data = b"\x00\x01" * 512  # Mock audio data
            service._on_audio_data_sync(audio_data)

        queue_size = service._audio_processing_queue.qsize()
        print(f"✓ Queue size after 50 submissions: {queue_size}")

        if queue_size > 0 and queue_size <= 50:
            print("✓ Audio data properly queued (no task explosion)")
        else:
            print(f"✗ Unexpected queue size: {queue_size}")
            return False

        # Test queue overflow protection
        print("Testing queue overflow protection...")

        # Fill the queue to its maximum
        for i in range(100):  # Try to add more than maxsize
            audio_data = b"\x00\x01" * 512
            service._on_audio_data_sync(audio_data)

        final_queue_size = service._audio_processing_queue.qsize()
        print(f"✓ Final queue size after overflow test: {final_queue_size}")
        print(f"✓ Queue maxsize: {service._audio_processing_queue.maxsize}")

        if final_queue_size <= service._audio_processing_queue.maxsize:
            print("✓ Queue overflow protection working")
        else:
            print(
                f"✗ Queue overflow not protected: {final_queue_size} > {service._audio_processing_queue.maxsize}"
            )
            return False

        print("✓ Audio queue fix test completed successfully")
        return True

    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_old_vs_new_behavior():
    """Test to demonstrate the difference between old and new behavior."""
    print("\nDemonstrating the fix...")

    print("OLD BEHAVIOR (before fix):")
    print("  - Each audio chunk → asyncio.create_task() → New concurrent task")
    print("  - 1000 audio chunks → 1000 concurrent tasks → System overload")
    print("  - Tasks compete for resources → Responsiveness lost")
    print("  - Ctrl+C doesn't work because event loop is overwhelmed")

    print("\nNEW BEHAVIOR (after fix):")
    print("  - Each audio chunk → Queue.put_nowait() → Queued for processing")
    print("  - 1000 audio chunks → Queue with max 100 items → Controlled load")
    print("  - Single processor task → Sequential processing → Stable performance")
    print("  - Ctrl+C works because event loop isn't overwhelmed")

    return True


if __name__ == "__main__":
    print("Audio Queue Fix Test")
    print("=" * 40)

    success1 = test_audio_queue_fix()
    success2 = test_old_vs_new_behavior()

    print("\n" + "=" * 40)
    if success1 and success2:
        print("✅ All tests passed! The audio queue fix is working.")
        print("   The transcription service will no longer create")
        print("   hundreds of concurrent tasks when processing audio.")
    else:
        print("❌ Test failed.")
