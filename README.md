# Scribed - Audio Transcription Daemon

[![CI](https://github.com/oldirty/scribed/actions/workflows/ci.yml/badge.svg)](https://github.com/scribed/scribed/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/oldirty/scribed/branch/main/graph/badge.svg)](https://codecov.io/gh/scribed/scribed)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: GPLv3](https://img.shields.io/badge/License-GPLv3-yellow.svg)](https://opensource.org/license/gpl-3-0)

## This is all generated code, that I have yet to fully review. Run at your own risk...

A powerful audio transcription daemon that provides wake word detection, voice commands, and both real-time and batch transcription capabilities.

## Features

### ✅ Current Features

- [x] **Project Structure**: Complete Python package with proper setup.py, dependencies, and entry points
- [x] **Configuration Management**: YAML-based configuration with Pydantic validation and environment variable support
- [x] **Core Daemon Architecture**: Async daemon with proper state management, signal handling, and graceful shutdown
- [x] **File Watcher**: Monitors directory for new audio files with real transcription functionality
- [x] **REST API Framework**: FastAPI-based API with health checks, status endpoints, and job tracking architecture
- [x] **CLI Interface**: Complete Click-based CLI with help system, configuration management, and daemon control
- [x] **Audio Processing**: Enhanced Whisper integration with multiple backend support (openai-whisper, faster-whisper)
- [x] **Transcription Engines**: Support for local Whisper and OpenAI API transcription
- [x] **Multiple Audio Formats**: Support for .wav, .mp3, .flac, .mp4, .ogg, and more
- [x] **Wake Word Detection**: Real-time wake word activation using Picovoice Porcupine
- [x] **Real-time Transcription**: Microphone input with live transcription and wake word activation
- [x] **Voice Commands**: Secure power words for voice-activated command execution with safety controls
- [x] **Testing & CI**: Comprehensive unit tests with pytest and GitHub Actions CI/CD pipeline
- [x] **Development Tools**: Pre-commit hooks, black formatting, mypy type checking, and development Makefile
- [x] **Documentation**: Example configuration, API documentation, and development setup guides

### 🚧 Planned Features

- [x] **Multiple transcription engine support** (Whisper ✅, OpenAI API ✅, Google Speech-to-Text 🚧)
- [x] **Wake word detection with Picovoice Porcupine** ✅
- [x] **Real-time transcription with low latency** ✅
- [x] **Voice command execution with security controls** ✅
- [ ] Desktop GUI with system tray indicator
- [ ] Performance monitoring and resource management

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/scribed/scribed.git
cd scribed

# Install in development mode
pip install -e ".[dev]"

# For wake word support
pip install -e ".[wake_word]"

# For Whisper support
pip install -e ".[whisper]"
```

**Windows Users:** Use `.\make.bat` instead of `make` for development commands:

```cmd
# Windows equivalent of make commands
.\make.bat install-dev
.\make.bat test
.\make.bat format
```

### Basic Usage

```bash
# Start the daemon
scribed start

# Check daemon status
scribed status

# Stop the daemon
scribed stop

# 🆕 NEW: Direct file transcription
scribed transcribe audio_file.wav
scribed transcribe audio_file.mp3 --provider whisper
scribed transcribe audio_file.wav --output transcript.txt --provider openai

# Start with custom config
scribed start --config /path/to/config.yaml
```

### Configuration

Create a `config.yaml` file:

```yaml
# Source mode: 'file' for batch processing, 'microphone' for real-time
source_mode: file

# File watcher settings for batch mode
file_watcher:
  watch_directory: ./audio_input
  output_directory: ./transcripts
  supported_formats: [".wav", ".mp3", ".flac"]

# API settings
api:
  host: "127.0.0.1"
  port: 8080

# Transcription settings
transcription:
  provider: whisper  # or google_speech, aws_transcribe
  language: en-US

# Output settings
output:
  format: txt  # txt, json, srt
  log_to_file: true
  log_file_path: ./logs/transcription.log

# Security settings for voice commands (disabled by default)
power_words:
  enabled: false
  mappings: {}
```

## Wake Word Detection (New! 🎉)

Scribed now supports hands-free voice activation using wake words! Simply say your configured wake word and start dictating.

### Quick Setup

1. **Install wake word dependencies:**
   ```bash
   pip install ".[wake_word]"
   ```

2. **Get a free Picovoice access key** at [console.picovoice.ai](https://console.picovoice.ai/)

3. **Set your access key** (choose one method):

   **Option A: Environment Variable (Recommended)**

   ```bash
   export PICOVOICE_ACCESS_KEY="your_picovoice_access_key_here"
   ```

   **Option B: Configuration File**

   ```yaml
   wake_word:
     access_key: "your_picovoice_access_key_here"
   ```

4. **Configure for real-time mode:**

   ```yaml
   source_mode: microphone

   wake_word:
     access_key: "your_picovoice_access_key_here"
     keywords: ["porcupine"]  # Built-in wake words available
     sensitivities: [0.5]

   microphone:
     device_index: null  # Default microphone
     sample_rate: 16000
   ```

5. **Start the daemon:**

   ```bash
   scribed daemon --config config.yaml
   ```

6. **Say "Porcupine"** to activate, then speak your content!

### Built-in Wake Words

Choose from: `porcupine`, `alexa`, `hey google`, `hey siri`, `jarvis`, `computer`, `americano`, `blueberry`, `bumblebee`, `grapefruit`, `grasshopper`, `picovoice`, `pineapple`, `terminator`

📖 **For detailed setup instructions, see [WAKE_WORD_SETUP.md](WAKE_WORD_SETUP.md)**

## Windows Compatibility 🪟

Scribed runs well on Windows with the following considerations:

### ✅ Fully Supported
- All Python components and dependencies
- Audio processing (PyAudio, sounddevice)
- Whisper transcription engines
- Picovoice Porcupine wake word detection
- Configuration and CLI commands

### 🔧 Windows-Specific Setup
- Use `make.bat` instead of `make` for development commands
- Power words use Windows commands (`dir`, `echo`, `cd`) by default
- Install Microsoft C++ Build Tools if needed for some dependencies

### 💡 Tips for Windows Users

```cmd
# Use PowerShell or Command Prompt
pip install -e ".[dev,wake_word]"

# Development commands
.\make.bat install-dev
.\make.bat test
.\make.bat format

# Run the daemon
scribed daemon --config config.yaml
```

## Development

### Setup Development Environment

```bash
# Install with development dependencies
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install

# Run tests
pytest

# Run tests with coverage
pytest --cov=scribed

# Format code
black src tests

# Type checking
mypy src
```

### Project Structure

```
scribed/
├── src/scribed/           # Main package
│   ├── __init__.py
│   ├── cli.py            # Command-line interface
│   ├── config.py         # Configuration management
│   ├── daemon.py         # Main daemon logic
│   ├── api/              # REST API
│   ├── audio/            # Audio processing
│   ├── transcription/    # Transcription engines
│   └── gui/              # GUI components
├── tests/                # Unit tests
├── docs/                 # Documentation
├── .github/workflows/    # CI/CD
└── config.yaml.example   # Example configuration
```

## API Reference

### REST API Endpoints

- `GET /status` - Get daemon status
- `POST /start` - Start transcription service
- `POST /stop` - Stop transcription service
- `POST /transcribe` - Submit audio for transcription
- `GET /jobs/{job_id}` - Get transcription job status

### CLI Commands

- `scribed start` - Start the daemon
- `scribed stop` - Stop the daemon
- `scribed status` - Check daemon status
- `scribed config` - Manage configuration
- `scribed logs` - View daemon logs

## Testing

The project includes comprehensive unit tests with CI/CD integration:

```bash
# Run all tests
pytest

# Run with coverage report
pytest --cov=scribed --cov-report=html

# Run specific test file
pytest tests/test_config.py

# Run tests in watch mode
pytest-watch
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Add tests for your changes
5. Ensure all tests pass (`pytest`)
6. Format your code (`black src tests`)
7. Commit your changes (`git commit -m 'Add amazing feature'`)
8. Push to the branch (`git push origin feature/amazing-feature`)
9. Open a Pull Request

## Security

Voice command execution is disabled by default and requires explicit configuration. See our [Security Guidelines](docs/security.md) for best practices.

## License

This project is licensed under the GPLv3 License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Built with integration for [Whisper](https://github.com/openai/whisper) transcription
- Wake word detection powered by [Picovoice Porcupine](https://picovoice.ai/platform/porcupine/)
- Audio processing with [sounddevice](https://python-sounddevice.readthedocs.io/)
