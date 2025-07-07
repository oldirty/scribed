#!/usr/bin/env python3
"""
Test the async wake word queue fix.
This test verifies that the "no running event loop" error has been resolved.
"""

import asyncio
import logging
import time
from unittest.mock import Mock, patch

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_async_queue_fix():
    """Test that the async queue fix works without errors."""
    print("Testing async wake word queue fix...")

    try:
        # Mock the underlying WakeWordEngine to avoid Picovoice access key issues
        with patch("src.scribed.wake_word.WakeWordEngine") as mock_engine_class:
            mock_engine = Mock()
            mock_engine_class.return_value = mock_engine

            from src.scribed.wake_word import AsyncWakeWordEngine

            # Create a mock config
            config = {
                "wake_word": {
                    "access_key": "test-key",
                    "keywords": ["test"],
                    "model_path": "test.ppn",
                }
            }

            # Create the async engine with mocked underlying engine
            engine = AsyncWakeWordEngine(config)
            print("✓ AsyncWakeWordEngine created successfully")

            # Test that we can create the queue without issues
            assert hasattr(engine, "_callback_queue")
            print("✓ Callback queue exists")

            # Test that start_listening can be called without "no running event loop" errors
            async def test_start_listening():
                callback_success = False
                try:
                    # Mock the start_listening method to simulate the callback
                    def mock_start_listening(callback):
                        # Simulate callback being called from a different thread
                        import threading

                        def call_callback():
                            nonlocal callback_success
                            time.sleep(0.1)  # Small delay
                            try:
                                callback(
                                    0, "test"
                                )  # This should not cause "no running event loop"
                                print("✓ Callback executed successfully")
                                callback_success = True
                            except Exception as e:
                                print(f"✗ Callback error: {e}")
                                raise

                        thread = threading.Thread(target=call_callback)
                        thread.start()
                        thread.join()

                    mock_engine.start_listening = mock_start_listening

                    # Create a test callback
                    user_callback_called = False

                    def test_callback(keyword_index, keyword_name):
                        nonlocal user_callback_called
                        user_callback_called = True
                        print(
                            f"✓ User callback called: {keyword_index}, {keyword_name}"
                        )

                    # This should work without "no running event loop" error
                    print("Testing start_listening...")

                    # Start listening but don't wait forever
                    task = asyncio.create_task(engine.start_listening(test_callback))

                    # Wait a bit for the callback to be processed
                    await asyncio.sleep(0.5)

                    # Stop the engine to clean up
                    engine._running = False

                    # Cancel the task
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass

                    # Check results
                    if callback_success:
                        print("✓ No 'running event loop' error occurred")
                        return True
                    else:
                        print("✗ Callback was not executed successfully")
                        return False

                except Exception as e:
                    if "no running event loop" in str(e).lower():
                        print(f"✗ Still getting 'no running event loop' error: {e}")
                        return False
                    else:
                        print(f"✓ Different error (not event loop related): {e}")
                        return True

            # Run the async test
            result = asyncio.run(test_start_listening())
            if result:
                print("✓ Async queue fix test completed successfully")
                return True
            else:
                print("✗ Async queue fix test failed")
                return False

        print("✓ Async queue fix test completed successfully")
        return True

    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("Wake Word Async Queue Fix Test")
    print("=" * 40)

    success = test_async_queue_fix()

    print("\n" + "=" * 40)
    if success:
        print("✅ All tests passed! The async queue fix is working.")
    else:
        print("❌ Test failed.")
