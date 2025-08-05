# Scribed MVP Demo

This demo shows the current MVP functionality of the Scribed audio transcription daemon.

## What's Working ✅

### 1. Configuration Management
- YAML-based configuration with Pydantic validation
- Environment variable support
- Default values with validation

### 2. CLI Interface
- Help system and subcommands
- Configuration display
- Daemon control (start/stop/status)
- **Direct file transcription with Whisper and OpenAI support**

### 3. Core Architecture
- Async daemon with proper state management
- Modular design with separate packages for API, audio, etc.
- Signal handling for graceful shutdown

### 4. Audio Processing & Transcription ✨ NEW!
- **Enhanced Whisper engine with multiple backend support**
- **Supports both openai-whisper and faster-whisper backends**
- **Automatic language code normalization (en-US → en)**
- **Multiple audio format support (.wav, .mp3, .flac, .mp4, .ogg, etc.)**
- **Real-time transcription with microphone input** ✅ **COMPLETED**

### 8. Wake Word Detection & Real-time Audio ✨ NEWEST!
- **Hands-free voice activation using Picovoice Porcupine**
- **Real-time microphone input and audio streaming**
- **Built-in wake words: porcupine, alexa, hey google, jarvis, computer, etc.**
- **Configurable sensitivity and silence timeout**
- **Async audio processing with live transcription**

### 9. Power Words (Voice Commands) ✨ JUST ADDED!
- **Secure voice-activated command execution**
- **Configurable phrase-to-command mappings**
- **Multi-layered security controls (whitelist, blacklist, validation)**
- **Commands disabled by default for security**
- **Safe execution with timeouts and sandboxing**

### 5. File Watcher
- Monitors directory for new audio files
- Supports multiple audio formats (.wav, .mp3, .flac)
- **Integrated with transcription service for real audio processing**

### 6. REST API Framework
- FastAPI-based API with automatic documentation
- Health checks and status endpoints
- Job tracking architecture (ready for implementation)

### 7. Testing & CI
- Comprehensive unit tests with pytest
- GitHub Actions CI/CD pipeline
- Development tools (black, mypy, pre-commit)

## Demo Commands

```bash
# Show help
scribed --help

# Show current configuration
scribed config

# Check daemon status (when running)
scribed status

# 🆕 NEW: Direct file transcription with Whisper
scribed transcribe audio_file.wav
scribed transcribe audio_file.mp3 --provider whisper
scribed transcribe audio_file.wav --output transcript.txt

# 🆕 NEW: Test Whisper engine availability
python -c "
from src.scribed.transcription.service import TranscriptionService
from src.scribed.config import Config
config = Config.from_env()
service = TranscriptionService(config.transcription.model_dump())
print('Whisper Available:', service.is_available())
print('Engine Info:', service.get_engine_info())
"

# 🆕 NEWEST: Wake word detection and real-time transcription
# First, install wake word dependencies:
pip install ".[wake_word]"

# Test complete audio system (shows 19+ detected audio devices):
python test_real_time_audio.py

# Test live audio recording with volume visualization:
python test_audio_recording.py

# Test wake word functionality:
python test_wake_word.py

# Test power words functionality:
python test_power_words.py

# Run interactive wake word demo (requires Picovoice access key):
python demo_wake_word.py

# Run interactive power words demo:
python demo_power_words.py

# Start daemon in real-time mode with wake word detection:
# (Configure config.yaml with source_mode: microphone and add your Picovoice access key)
scribed daemon --config config.yaml

# Start daemon with power words enabled (uses test_config.yaml):
scribed daemon --config test_config.yaml

# Start daemon (batch mode - file watcher with real transcription)
scribed start

# In another terminal, add an audio file to test:
# cp /path/to/audio.wav audio_input/
# The daemon detects it and creates a real transcript using Whisper
```

## Next Steps 🚧

The MVP now includes **working Whisper integration, real-time wake word functionality, AND secure power words (voice commands)**! Next development priorities:

1. ~~**Audio Processing**: Integrate actual transcription engines (Whisper, cloud APIs)~~ ✅ **COMPLETED**
2. ~~**Wake Word Detection**: Add Picovoice Porcupine integration~~ ✅ **COMPLETED**
3. ~~**Real-time Audio**: Implement microphone input and streaming~~ ✅ **COMPLETED**
4. ~~**Security**: Power words command execution with safety controls~~ ✅ **COMPLETED**
5. **GUI**: System tray integration for desktop users
6. **Enhanced Transcription**:
   - Add segment timing information display
   - Improve streaming transcription support
   - Add confidence scores and quality metrics

## Architecture Highlights

- **Modular Design**: Clean separation between configuration, daemon, API, and audio processing
- **Type Safety**: Full type hints with mypy validation
- **Async-First**: Built for real-time audio processing requirements
- **Configurable**: Everything is configurable via YAML
- **Secure**: Voice commands disabled by default, explicit whitelisting required
- **Testable**: High test coverage with both unit and integration tests

The codebase is ready for the next phase of development!
