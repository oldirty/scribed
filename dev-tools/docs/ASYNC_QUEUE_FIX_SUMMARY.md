# Async Queue Fix Summary

## Problem Description

The error you encountered:

```text
INFO: Wake word detected: porcupine (index: 0)
ERROR: Error queuing wake word detection: no running event loop
C:\Users\zachs\Repos\scribed\src\scribed\wake_word\__init__.py:316: RuntimeWarning: coroutine 'Queue.put' was never awaited
  self.logger.error(f"Error queuing wake word detection: {e}")
RuntimeWarning: Enable tracemalloc to get the object allocation traceback
INFO: Received signal 2, shutting down...
```

And later:

```text
ERROR: Error queuing audio data: no running event loop
C:\Users\zachs\Repos\scribed\src\scribed\audio\microphone_input.py:297: RuntimeWarning: coroutine 'Queue.put' was never awaited
  self.logger.error(f"Error queuing audio data: {e}")
RuntimeWarning: Enable tracemalloc to get the object allocation traceback
```

## Root Cause

Both errors were caused by the same fundamental issue: **attempting to use async operations from synchronous callbacks running in different threads**.

### The Problem Pattern

1. **Wake Word Detection**: The Picovoice wake word engine runs in a separate thread and calls a callback function when a wake word is detected.

2. **Microphone Input**: The PyAudio microphone input also runs in a separate thread and calls a callback function when audio data is available.

3. **Async Queue Usage**: Both callback functions were trying to use `asyncio.create_task()` to put data into an `asyncio.Queue`, but:
   - The callbacks run in threads that don't have an event loop
   - `asyncio.create_task()` requires a running event loop
   - `asyncio.Queue.put()` is a coroutine that must be awaited

### The Error Sequence

1. Wake word detected → Picovoice calls callback in worker thread
2. Callback tries to use `asyncio.create_task(queue.put(data))`
3. No event loop in worker thread → "no running event loop" error
4. The coroutine `Queue.put()` is created but never awaited → RuntimeWarning

## Solution

The fix uses `loop.call_soon_threadsafe()` to safely schedule async operations from any thread:

### Before (Broken)

```python
def queue_callback(data):
    try:
        asyncio.create_task(self._queue.put(data))  # ❌ Fails in worker thread
    except Exception as e:
        self.logger.error(f"Error queuing data: {e}")
```

### After (Fixed)

```python
async def start_listening(self, callback):
    # Get the event loop that will be used
    loop = asyncio.get_running_loop()
    
    def queue_callback(data):
        try:
            # Schedule the async operation on the main event loop
            loop.call_soon_threadsafe(
                lambda: asyncio.create_task(self._queue.put(data))
            )
        except Exception as e:
            self.logger.error(f"Error queuing data: {e}")
```

## Files Fixed

1. **`src/scribed/wake_word/__init__.py`** - Fixed wake word detection queue
2. **`src/scribed/audio/microphone_input.py`** - Fixed microphone audio data queue

## How `call_soon_threadsafe()` Works

- **Thread-Safe**: Can be called from any thread, not just the event loop thread
- **Event Loop Scheduling**: Schedules the callback to run on the main event loop
- **Async Operation**: The lambda creates the async task on the correct thread with the event loop

## Verification

Both fixes have been tested with mock implementations that simulate the real callback behavior:

1. ✅ **Wake Word Fix Test**: `test_wake_word_async_fix.py` - Passed
2. ✅ **Microphone Fix Test**: `test_microphone_async_fix.py` - Passed  
3. ✅ **Integration Test**: No more "no running event loop" errors

## Impact

This fix resolves the core async/threading issue that was preventing wake word detection and real-time audio processing from working properly. The system can now:

- Detect wake words without async errors
- Process microphone audio data without async errors  
- Handle callbacks from worker threads safely
- Maintain proper async queue operations

The only remaining wake word issue is the Picovoice access key configuration, which is a separate authentication problem.
