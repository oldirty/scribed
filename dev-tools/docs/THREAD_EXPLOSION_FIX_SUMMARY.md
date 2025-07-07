# Thread Explosion Fix Summary

## Issues Identified and Fixed

### ✅ **Issue 1: Unlimited Thread Creation in Transcription**

**Problem**: Each transcription call created a new thread via `run_in_executor(None, ...)` with no limit.

**Fix**: Implemented a shared thread pool with a maximum of 4 workers:

```python
# Before (unlimited threads)
await loop.run_in_executor(None, func, *args, **kwargs)

# After (limited to 4 threads)
_TRANSCRIPTION_THREAD_POOL = ThreadPoolExecutor(max_workers=4, thread_name_prefix="transcription")
await loop.run_in_executor(_TRANSCRIPTION_THREAD_POOL, func, *args, **kwargs)
```

**File**: `src/scribed/transcription/base.py`

### ✅ **Issue 2: Duplicate Microphone Recording Sessions**

**Problem**: Each wake word detection could start a new microphone recording session without checking if one was already running.

**Fix**: Added duplicate recording prevention:

```python
async def start_recording(self, callback):
    if self._running:
        self.logger.warning("Microphone already recording")
        return  # Prevent duplicate sessions
    
    self._running = True
    # ... rest of recording logic
```

**File**: `src/scribed/audio/microphone_input.py`

### ✅ **Issue 3: Multiple Audio Processing Tasks**

**Problem**: Each transcription start could create duplicate audio processing and silence timeout tasks.

**Fix**: Added task tracking to prevent duplicates:

```python
# Start silence timeout task
if self._silence_task is None or self._silence_task.done():
    self._silence_task = asyncio.create_task(self._silence_timeout_task())

# Start audio processing task  
if self._audio_processor_task is None or self._audio_processor_task.done():
    self._audio_processor_task = asyncio.create_task(self._audio_processor())
```

**File**: `src/scribed/realtime/transcription_service.py`

### ✅ **Issue 4: Audio Task Explosion (Previously Fixed)**

**Problem**: Each audio chunk created a new async task (already fixed in previous iteration).

**Fix**: Replaced with sequential queue processing (already implemented).

## Summary of Thread Control Improvements

| Component | Before | After |
|-----------|--------|-------|
| **Transcription Threads** | Unlimited | Max 4 workers |
| **Microphone Sessions** | Multiple possible | Single session only |
| **Audio Processing Tasks** | Could duplicate | Tracked & prevented |
| **Silence Timeout Tasks** | Could duplicate | Tracked & prevented |

## Expected Results

After these fixes, the system should:

1. ✅ **Limited Thread Growth**: Maximum ~6-8 new threads total (4 transcription + microphone + system)
2. ✅ **No Duplicate Sessions**: Wake word detection won't start multiple overlapping transcription sessions
3. ✅ **Controlled Resource Usage**: Thread pool prevents runaway thread creation
4. ✅ **Proper Cleanup**: Tasks are properly cancelled when transcription stops

## Root Cause Analysis

The thread explosion was caused by:

1. **Frequent Audio Processing**: Audio chunks every 2 seconds
2. **No Thread Limits**: Each transcription created unlimited threads
3. **Duplicate Sessions**: Multiple wake word detections could overlap
4. **No Task Management**: Tasks weren't tracked or prevented from duplicating

## Testing

To verify the fixes work:
1. Monitor thread count before/after wake word detection
2. Check that multiple wake word detections don't multiply threads
3. Verify transcription thread pool limits are enforced
4. Confirm proper cleanup when stopping transcription

The fixes should eliminate the massive thread creation that was causing system unresponsiveness and Ctrl+C failures.
