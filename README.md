# Scribed - Audio Transcription Service

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: GPLv3](https://img.shields.io/badge/License-GPLv3-yellow.svg)](https://opensource.org/license/gpl-3-0)

A focused audio transcription service that provides real-time microphone input and file batch processing with multiple transcription engines (Whisper, OpenAI). Built with a clean, maintainable architecture after extensive refactoring to remove complexity and focus on core functionality.

## Features

### ✅ Core Features

- **Real-time Microphone Transcription**: Live audio capture and transcription from microphone input
- **File Batch Processing**: Monitor directories for new audio files and automatically transcribe them
- **Multiple Transcription Engines**: Support for local Whisper and OpenAI API transcription
- **Multiple Audio Formats**: Support for .wav, .mp3, .flac, and other common audio formats
- **Clean Architecture**: Modular design with separate audio sources, transcription engines, and output handlers
- **Configuration Management**: YAML-based configuration with validation and environment variable support
- **REST API**: FastAPI-based API for programmatic control and integration
- **CLI Interface**: Complete command-line interface for all operations

### ✅ Optional Features (Disabled by Default)

- **Wake Word Detection**: Voice activation using Picovoice Porcupine (requires access key)
- **Power Words**: Voice commands for system automation (security-focused, requires explicit configuration)

### ⚠️ Removed Features (From Previous Versions)

- **SpeechLM2 Integration**: Removed due to complexity - use Whisper or OpenAI instead
- **Multiple TTS Engines**: Simplified to focus on transcription
- **Complex Audio Preprocessing**: Kept essential functionality only
- **GUI Components**: CLI and API only

### ✅ Output Options

- **File Output**: Save transcriptions to text files with customizable naming
- **Clipboard Integration**: Copy transcriptions directly to system clipboard
- **Console Output**: Display transcriptions in terminal
- **Structured Logging**: Detailed logging with configurable levels

## Quick Start

### Installation

#### Development Installation (Current)

```bash
# Clone the repository
git clone https://github.com/oldirty/scribed.git
cd scribed

# Install core dependencies
pip install -e .

# Install with optional features
pip install -e ".[whisper]"        # Local Whisper transcription
pip install -e ".[openai]"         # OpenAI API transcription  
pip install -e ".[wake_word]"      # Wake word detection
pip install -e ".[dev]"            # Development tools
```

#### Windows Installation

Windows users can use the provided installation scripts:

```powershell
# PowerShell - Simple installer
.\install-windows-simple.ps1

# Or create virtual environment manually
python -m venv venv
venv\Scripts\Activate.ps1
pip install -e .
```

#### Optional Dependencies

- **Whisper**: `pip install -e ".[whisper]"` - Local transcription with OpenAI Whisper
- **OpenAI**: `pip install -e ".[openai]"` - Cloud transcription via OpenAI API
- **Wake Word**: `pip install -e ".[wake_word]"` - Voice activation (requires Picovoice key)
- **Audio Processing**: `pip install -e ".[audio_processing]"` - Enhanced audio preprocessing

### Basic Usage

```bash
# Start the transcription service
scribed start

# Start with custom configuration
scribed --config config.yaml start

# Check service status
scribed status

# Stop the service (use Ctrl+C or API)
scribed stop

# Direct file transcription
scribed transcribe audio_file.wav
scribed transcribe audio_file.mp3 --provider whisper
scribed transcribe audio_file.wav --output transcript.txt --provider openai

# Record audio and transcribe to clipboard
scribed record-to-clipboard --duration 30
scribed record-to-clipboard --provider openai --silent

# View service logs
scribed logs --lines 100

# Check optional feature status
scribed features

# Show current configuration
scribed config

# Migrate old configuration files
scribed migrate-config old-config.yaml
```

### Configuration

Create a `config.yaml` file (see `config.yaml.example` for full reference):

```yaml
# Core audio settings
audio:
  source: microphone  # microphone or file
  
  # Microphone settings
  device_index: null  # null for default device
  sample_rate: 16000
  channels: 1
  
  # File watcher settings
  watch_directory: ./audio_input
  output_directory: ./transcripts
  supported_formats: [".wav", ".mp3", ".flac"]

# Transcription engine settings
transcription:
  provider: whisper  # whisper (local) or openai (API)
  model: base        # whisper: base/small/medium/large, openai: whisper-1
  language: en       # Language code (en, es, fr, etc.)
  api_key: null      # Required for OpenAI (can use OPENAI_API_KEY env var)

# Output settings
output:
  format: txt              # txt or json
  save_to_file: true       # Save transcriptions to files
  copy_to_clipboard: false # Copy to clipboard
  log_file_path: ./logs/transcription.log

# API server settings
api:
  host: "127.0.0.1"
  port: 8080
  debug: false

# Optional features (disabled by default for security)

# Wake word detection (requires Picovoice access key)
wake_word:
  enabled: false           # Must be explicitly enabled
  keywords: ["porcupine"]  # Built-in Picovoice keywords
  access_key: null         # Get free key from https://console.picovoice.ai/

# Voice commands (SECURITY WARNING: Executes system commands!)
power_words:
  enabled: false           # Must be explicitly enabled
  max_command_length: 100  # Maximum command length for security
  mappings:
    # Example safe mappings:
    # "open notepad": "notepad.exe"
    # "open calculator": "calc.exe"
```

## Optional Features

### Wake Word Detection

Enable hands-free voice activation using Picovoice Porcupine:

1. **Install dependencies:**
   ```bash
   pip install -e ".[wake_word]"
   ```

2. **Get a free Picovoice access key** at [console.picovoice.ai](https://console.picovoice.ai/)

3. **Configure wake word detection:**
   ```yaml
   audio:
     source: microphone
   
   wake_word:
     enabled: true  # Must be explicitly enabled
     keywords: ["porcupine"]
     access_key: "your_access_key_here"  # Or set PICOVOICE_ACCESS_KEY env var
   ```

4. **Start the service:**
   ```bash
   scribed start --config config.yaml
   ```

### Power Words (Voice Commands)

Execute system commands via voice (use with caution):

```yaml
power_words:
  enabled: true  # SECURITY WARNING: Executes system commands!
  max_command_length: 100
  mappings:
    "open notepad": "notepad.exe"
    "open calculator": "calc.exe"
```

**Security Note**: Power words are disabled by default and should only be enabled in trusted environments.

## Platform Support

### Windows
- Full support for all core features
- Audio processing with sounddevice
- Whisper and OpenAI transcription engines
- Wake word detection with Picovoice Porcupine
- Use provided installation scripts for easy setup

### Linux/macOS
- Full support for all core features
- Standard Python package installation
- All optional features supported

### Development Tools
- Use `make.bat` on Windows or `make` on Linux/macOS
- Pre-commit hooks and code formatting
- Comprehensive test suite

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
│   ├── daemon.py         # Legacy daemon (being phased out)
│   ├── api/              # REST API server
│   ├── audio/            # Audio input sources
│   │   ├── base.py       # AudioSource interface
│   │   ├── microphone.py # Microphone input
│   │   └── file_source.py # File-based input
│   ├── core/             # Core engine architecture
│   │   ├── engine.py     # Main ScribedEngine
│   │   └── session.py    # TranscriptionSession
│   ├── transcription/    # Transcription engines
│   │   ├── base.py       # TranscriptionEngine interface
│   │   ├── whisper_engine.py      # Local Whisper
│   │   ├── enhanced_whisper_engine.py # Enhanced Whisper
│   │   └── openai_engine.py       # OpenAI API
│   ├── output/           # Output handlers
│   │   ├── handler.py    # OutputHandler
│   │   ├── file.py       # File output
│   │   └── clipboard.py  # Clipboard output
│   ├── wake_word/        # Wake word detection (optional)
│   └── power_words/      # Voice commands (optional)
├── tests/                # Comprehensive test suite
├── config.yaml.example   # Example configuration
├── MIGRATION_GUIDE.md    # Migration from older versions
└── pyproject.toml        # Project configuration
```

## API Reference

The Scribed service provides a REST API for programmatic control:

### Key Endpoints

- `GET /health` - Health check
- `GET /status` - Get engine status and configuration
- `POST /sessions` - Create transcription session
- `POST /transcribe/file` - Transcribe uploaded audio file
- `POST /record-to-clipboard` - Record audio and transcribe to clipboard

### CLI Commands

- `scribed start` - Start the transcription service
- `scribed stop` - Stop the service (currently requires Ctrl+C)
- `scribed status` - Check service status and health
- `scribed transcribe <file>` - Transcribe audio file directly
- `scribed record-to-clipboard` - Record audio and transcribe to clipboard
- `scribed config` - Show or save current configuration
- `scribed features` - Show optional feature status and availability
- `scribed logs` - View service logs (with --lines option)
- `scribed migrate-config` - Migrate old configuration files (with --dry-run option)

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

## Getting Started Examples

### Example 1: Basic File Transcription
```bash
# Install with Whisper support
pip install -e ".[whisper]"

# Transcribe a single file
scribed transcribe recording.wav

# Transcribe with specific output location
scribed transcribe recording.wav --output transcript.txt
```

### Example 2: Real-time Microphone Transcription
```bash
# Create configuration for microphone input
cat > config.yaml << EOF
audio:
  source: microphone
  sample_rate: 16000

transcription:
  provider: whisper
  model: base

output:
  save_to_file: true
  copy_to_clipboard: true
EOF

# Start the service
scribed --config config.yaml start
```

### Example 3: File Batch Processing
```bash
# Create configuration for file watching
cat > config.yaml << EOF
audio:
  source: file
  watch_directory: ./audio_input
  output_directory: ./transcripts

transcription:
  provider: whisper
  model: base
EOF

# Start the service to monitor directory
scribed --config config.yaml start
```

## Security

Voice command execution is disabled by default and requires explicit configuration. See our [Security Guidelines](docs/security.md) for best practices.

## License

This project is licensed under the GPLv3 License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Built entirely with VSCode + Copilot + Claude Sonnet 4
- Built with integration for [Whisper](https://github.com/openai/whisper) transcription
  - But you should be able to drop in any GGML Automatic Speech Recognition model ? Maybe?
- Wake word detection powered by [Picovoice Porcupine](https://picovoice.ai/platform/porcupine/)
- Audio processing with [sounddevice](https://python-sounddevice.readthedocs.io/)

[Buy me a beer!](https://patreon.com/oldirty?utm_medium=unknown&utm_source=join_link&utm_campaign=creatorshare_creator&utm_content=copyLink)