# Transcription Thread Explosion Fix

## Problem Description

When running Scribed in daemon mode with wake word detection enabled, users experienced:

1. **Massive thread/task creation**: Speaking the wake word caused hundreds or thousands of transcription threads to spawn
2. **System unresponsiveness**: The script became completely unresponsive 
3. **Ctrl+C failure**: Unable to stop the daemon with keyboard interrupt
4. **Resource exhaustion**: High CPU and memory usage

## Root Cause Analysis

The issue was in the real-time transcription service's audio processing logic:

### The Problematic Code (Before Fix)

```python
def _on_audio_data_sync(self, audio_data: bytes) -> None:
    """Synchronous wrapper for audio data callback."""
    # Create a task to handle the async audio processing
    try:
        asyncio.create_task(self._on_audio_data(audio_data))  # ❌ PROBLEM!
    except RuntimeError:
        # If no event loop is running, we can't process async
        self.logger.warning("No event loop available for audio processing")
```

### What Went Wrong

1. **High-frequency audio callbacks**: Microphone audio data arrives very frequently (every ~10-100ms depending on chunk size)
2. **Task explosion**: Each audio chunk created a new `asyncio.Task` with `create_task()`
3. **Concurrent execution**: All tasks ran concurrently instead of sequentially
4. **Resource overload**: Hundreds of tasks processing audio simultaneously
5. **Event loop overwhelm**: The event loop couldn't keep up with task creation
6. **Signal handling failure**: Ctrl+C couldn't interrupt the overwhelmed event loop

### Example of the Problem

If audio chunks arrive every 50ms:
- After 5 seconds: 100 concurrent tasks
- After 10 seconds: 200 concurrent tasks  
- After 30 seconds: 600+ concurrent tasks
- Each task potentially triggers transcription API calls
- System becomes completely unresponsive

## Solution: Sequential Audio Queue Processing

The fix implements a **controlled, sequential audio processing system**:

### New Architecture

```python
# Initialize with bounded queue
self._audio_processing_queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=100)
self._audio_processor_task: Optional[asyncio.Task] = None

def _on_audio_data_sync(self, audio_data: bytes) -> None:
    """Synchronous wrapper for audio data callback."""
    if not self._transcription_active:
        return
        
    # Put audio data in queue for sequential processing
    try:
        # Non-blocking put - if queue is full, drop the data to prevent overflow
        try:
            self._audio_processing_queue.put_nowait(audio_data)
        except asyncio.QueueFull:
            # Queue is full, drop this audio chunk to prevent memory issues
            self.logger.warning("Audio processing queue full, dropping audio chunk")
    except Exception as e:
        self.logger.warning(f"Error queuing audio data: {e}")

async def _audio_processor(self) -> None:
    """Process audio data from queue sequentially to prevent task explosion."""
    while self._transcription_active:
        try:
            # Wait for audio data with timeout
            audio_data = await asyncio.wait_for(
                self._audio_processing_queue.get(), timeout=1.0
            )
            
            # Process the audio data
            await self._on_audio_data(audio_data)
            
        except asyncio.TimeoutError:
            # No audio data received, continue loop
            continue
        except Exception as e:
            self.logger.error(f"Error in audio processor: {e}")
            # Continue processing other audio data
            continue
```

### Key Improvements

1. **Bounded Queue**: Maximum 100 audio chunks queued at once
2. **Sequential Processing**: Single processor task handles audio chunks one by one
3. **Overflow Protection**: Excess audio chunks are dropped to prevent memory issues
4. **Graceful Degradation**: System remains responsive even under high load
5. **Proper Cleanup**: Audio processor task is cancelled when transcription stops

## Implementation Details

### Files Modified

- **`src/scribed/realtime/transcription_service.py`**: Main fix implementation

### Key Changes

1. **Added audio processing queue**:
   ```python
   self._audio_processing_queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=100)
   self._audio_processor_task: Optional[asyncio.Task] = None
   ```

2. **Replaced task creation with queue submission**:
   ```python
   # OLD: asyncio.create_task(self._on_audio_data(audio_data))
   # NEW: self._audio_processing_queue.put_nowait(audio_data)
   ```

3. **Added sequential processor task**:
   ```python
   self._audio_processor_task = asyncio.create_task(self._audio_processor())
   ```

4. **Enhanced cleanup logic**:
   ```python
   # Cancel audio processor task
   if self._audio_processor_task and not self._audio_processor_task.done():
       self._audio_processor_task.cancel()
   ```

## Before vs After Comparison

| Aspect | Before (Broken) | After (Fixed) |
|--------|----------------|---------------|
| **Task Creation** | 1 task per audio chunk | 1 processor task total |
| **Processing** | Hundreds of concurrent tasks | Sequential processing |
| **Memory Usage** | Unbounded growth | Bounded queue (100 items) |
| **CPU Usage** | Very high (task switching) | Normal |
| **Responsiveness** | System freezes | Stays responsive |
| **Ctrl+C** | Doesn't work | Works normally |
| **Resource Control** | None | Overflow protection |

## Verification

The fix has been tested with:

1. ✅ **Audio Queue Test**: Verifies queue behavior and overflow protection
2. ✅ **Rapid Data Test**: Confirms no task explosion with high-frequency audio
3. ✅ **Integration Test**: Ensures compatibility with existing functionality

## Results

After the fix:
- ✅ Wake word detection works without system overload
- ✅ Audio processing remains responsive
- ✅ Ctrl+C interrupts work properly
- ✅ Memory usage stays bounded
- ✅ CPU usage returns to normal levels
- ✅ Transcription quality is maintained

This fix resolves the transcription thread explosion issue and makes Scribed's real-time audio processing stable and responsive.
