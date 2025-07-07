# Development and Testing Tools - Test Files

This directory contains copilot-generated one-off test files created during the development and debugging of Scribed. These tests were primarily used for:

1. **Regression Testing**: Verifying fixes for specific issues
2. **Integration Testing**: Testing component interactions
3. **Bug Reproduction**: Isolating and reproducing specific problems
4. **Feature Validation**: Validating new features before integration

## Test Categories

### Audio & Microphone Tests
- `test_audio_queue_fix.py` - Fixes for async audio queue issues
- `test_audio_recording.py` - Audio recording functionality tests
- `test_microphone_async_fix.py` - Microphone async handling fixes
- `test_real_time_audio.py` - Real-time audio processing tests

### Wake Word & Speech Recognition
- `test_wake_word.py` - Basic wake word detection tests
- `test_wake_word_async_fix.py` - Async wake word detection fixes
- `test_whisper_wake_word.py` - Whisper-based wake word engine tests
- `test_picovoice_env.py` - Picovoice environment setup tests

### TTS (Text-to-Speech) Tests
- `test_tts_fallback.py` - TTS fallback mechanism tests
- `test_tts_simple.py` - Basic TTS functionality tests
- `test_gtts_standalone.py` - Google TTS standalone tests

### Threading & Performance
- `test_thread_explosion_fix.py` - Thread explosion prevention tests
- `test_transcription_fix.py` - Transcription service fixes

### Feature Tests
- `test_power_words.py` - Power words functionality tests
- `test_clipboard_feature.py` - Clipboard integration tests
- `test_cli.py` - Command-line interface tests

### Integration Tests
- `test_integration.py` - General integration testing

## Usage

These tests are primarily for development and debugging purposes. They may have specific dependencies or configurations that differ from the main test suite in the `tests/` directory.

To run any of these tests:
```powershell
cd dev-tools/tests
python test_filename.py
```

## Note

These tests were created as one-off debugging and validation tools. For the main test suite, see the `tests/` directory in the project root.
