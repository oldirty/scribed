# Clipboard Transcription Feature

This document describes the new clipboard transcription functionality in Scribed, which allows you to transcribe speech directly to the system clipboard.

## Overview

The clipboard transcription feature enables seamless integration with your workflow by automatically copying transcribed text to your system clipboard. This works in both CLI mode and daemon mode.

## Features

### 1. CLI Command: `record-to-clipboard`

Record audio and transcribe it directly to the clipboard.

```bash
# Basic usage - record for 10 seconds
scribed record-to-clipboard

# Specify duration
scribed record-to-clipboard --duration 30

# Choose transcription provider
scribed record-to-clipboard --provider openai

# Silent mode (don't print transcription to console)
scribed record-to-clipboard --silent

# Use daemon API (if daemon is running)
scribed record-to-clipboard --use-daemon
```

#### Options

- `--duration, -d`: Recording duration in seconds (default: 10)
- `--provider, -p`: Transcription provider (`whisper` or `openai`)
- `--silent, -s`: Don't print the transcribed text to console
- `--use-daemon`: Use the daemon API instead of direct transcription

### 2. API Endpoint: `/record-to-clipboard`

When the daemon is running, you can use the REST API to trigger clipboard transcription.

**POST** `/record-to-clipboard`

Request body:

```json
{
  "duration": 10,
  "provider": "whisper"
}
```

Response:

```json
{
  "success": true,
  "text": "The transcribed text",
  "processing_time": 2.34
}
```

### 3. Configuration Options

Add these options to your config file to enable automatic clipboard copying:

```yaml
output:
  enable_clipboard: true      # Enable clipboard functionality
  clipboard_on_final: true    # Copy final transcriptions to clipboard
```

When enabled, all final transcriptions from real-time mode will be automatically copied to the clipboard.

## Use Cases

### 1. Quick Voice Notes

```bash
# Record a quick voice note and have it ready to paste
scribed record-to-clipboard --duration 30
# Now paste the transcription anywhere with Ctrl+V
```

### 2. Voice-to-Text Input

```bash
# Replace typing with voice input
scribed record-to-clipboard --silent
# Transcription is silently copied to clipboard for pasting
```

### 3. Meeting Notes

Enable clipboard mode in the daemon configuration, and all wake-word triggered transcriptions will be automatically available in your clipboard.

### 4. API Integration

Use the API endpoint to build custom applications that need voice-to-clipboard functionality.

## Platform Support

### Windows

- Uses `win32clipboard` (if available) or `tkinter` as fallback
- No additional dependencies required

### macOS

- Uses `pbcopy`/`pbpaste` commands or `tkinter` as fallback
- Works out of the box

### Linux

- Requires `xclip` or `xsel` to be installed
- Install with: `sudo apt-get install xclip`
- Falls back to `tkinter` if command-line tools aren't available

## Error Handling

The system gracefully handles various error conditions:

- **Clipboard unavailable**: Provides helpful error messages and installation instructions
- **Audio recording issues**: Reports sounddevice-related errors with installation instructions
- **Transcription failures**: Returns error details while preserving the recorded audio for debugging
- **API connectivity**: Falls back to direct mode if daemon is unavailable

## Backward Compatibility

The original `transcribe-to-clipboard` command is maintained for backward compatibility but shows a deprecation warning. Users should migrate to the new `record-to-clipboard` command.

## Examples

### Basic CLI Usage

```bash
# Simple 10-second recording
scribed record-to-clipboard

# 30-second recording with OpenAI
scribed record-to-clipboard -d 30 -p openai

# Silent mode for seamless workflow
scribed record-to-clipboard -s
```

### API Usage with curl

```bash
# Start recording via API
curl -X POST http://localhost:8080/record-to-clipboard \
  -H "Content-Type: application/json" \
  -d '{"duration": 15, "provider": "whisper"}'
```

### Python API Usage

```python
import requests

response = requests.post(
    "http://localhost:8080/record-to-clipboard",
    json={"duration": 10, "provider": "whisper"}
)

result = response.json()
if result["success"]:
    print(f"Transcription copied to clipboard: {result['text']}")
else:
    print(f"Error: {result['error']}")
```

## Testing

Use the provided test script to verify functionality:

```bash
python test_clipboard_feature.py
```

This script tests:

- Clipboard availability and basic functionality
- Configuration loading
- API endpoint functionality (requires daemon to be running)

## Troubleshooting

### Clipboard not working on Linux

```bash
# Install required clipboard tools
sudo apt-get install xclip
# or
sudo apt-get install xsel
```

### API endpoint not responding

```bash
# Check if daemon is running
scribed status

# Start daemon if not running
scribed start
```

### Audio recording issues

```bash
# Install sounddevice if missing
pip install sounddevice
```
