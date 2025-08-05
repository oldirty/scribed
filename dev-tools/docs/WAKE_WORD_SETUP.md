# Wake Word Setup Guide

This guide walks you through setting up wake word functionality for Scribed, enabling hands-free voice activation for transcription.

## Prerequisites

### 1. Install Dependencies

The wake word functionality requires additional dependencies:

```bash
pip install ".[wake_word]"
```

Or install manually:
```bash
pip install pvporcupine pyaudio
```

### 2. Get Picovoice Access Key

Wake word detection uses Picovoice Porcupine, which requires a free access key:

1. Go to [Picovoice Console](https://console.picovoice.ai/)
2. Sign up for a free account
3. Create a new project or use the default
4. Copy your Access Key from the project dashboard

## Configuration

### 1. Update Config File

Copy `config.yaml.example` to `config.yaml` and update:

```yaml
# Set source mode to microphone for real-time transcription
source_mode: microphone

# Wake word settings
wake_word:
  engine: picovoice
  access_key: "YOUR_PICOVOICE_ACCESS_KEY_HERE"
  keywords: ["porcupine"]  # Built-in wake words
  sensitivities: [0.5]     # Detection sensitivity (0.0-1.0)
  silence_timeout: 15      # Seconds of silence before stopping
  stop_phrase: "stop listening"

# Microphone settings
microphone:
  device_index: null  # null for default microphone
  sample_rate: 16000
  channels: 1
  chunk_size: 1024
```

### 2. Available Built-in Keywords

Porcupine includes these built-in wake words:
- `porcupine` (default)
- `alexa`
- `hey google`
- `hey siri`
- `jarvis`
- `computer`
- `americano`
- `blueberry`
- `bumblebee`
- `grapefruit`
- `grasshopper`
- `picovoice`
- `pineapple`
- `terminator`

### 3. Multiple Wake Words

You can configure multiple wake words with different sensitivities:

```yaml
wake_word:
  keywords: ["porcupine", "computer", "jarvis"]
  sensitivities: [0.5, 0.6, 0.4]  # One per keyword
```

## Usage

### 1. Start the Daemon

```bash
# Using the CLI
scribed daemon --config config.yaml

# Or using Python
python -m scribed daemon
```

### 2. Activate with Wake Word

1. Say your configured wake word (e.g., "Porcupine")
2. The system will start recording and transcribing
3. Speak your content
4. Say "stop listening" or wait for silence timeout
5. The transcription will be saved to your configured output directory

### 3. Monitor Status

Check the daemon status via the API:

```bash
curl http://localhost:8080/status
```

## Testing

Run the wake word test to verify everything is working:

```bash
python test_wake_word.py
```

This will test:
- ✅ Dependencies availability
- ✅ Wake word engine (requires access key)
- ✅ Microphone input
- ✅ Real-time service integration

## Troubleshooting

### "Picovoice access key is required"

- Make sure you've added your access key to the config file
- Verify the access key is correct (copy-paste from Picovoice Console)
- Check that the config file is being loaded correctly

### "Audio dependencies not available"

Install the audio dependencies:
```bash
pip install pyaudio
```

On Linux, you may need:
```bash
sudo apt-get install python3-pyaudio
# or
sudo apt-get install portaudio19-dev python3-dev
pip install pyaudio
```

On macOS:
```bash
brew install portaudio
pip install pyaudio
```

### Wake word not detected

- Check microphone permissions in your OS
- Verify the microphone is working with other applications
- Try adjusting the sensitivity (higher = more sensitive, but more false positives)
- Speak clearly and at a normal volume
- Make sure you're using the exact keyword

### Transcription not starting

- Check the logs for error messages
- Verify the transcription service is configured correctly
- Make sure the Whisper model is downloaded and available

## Custom Wake Words

For custom wake words, you'll need to train a model using Picovoice Console:

1. Go to [Picovoice Console](https://console.picovoice.ai/)
2. Navigate to "Porcupine"
3. Create a custom wake word
4. Download the `.ppn` model file
5. Update your config:

```yaml
wake_word:
  model_path: "/path/to/custom_wake_word.ppn"
  keywords: ["custom_word"]
```

## Performance Tips

- Use a good quality microphone for better detection
- Keep background noise to a minimum
- Position the microphone appropriately (not too close/far)
- Start with default sensitivity and adjust if needed
- Use shorter wake words for better detection

## Security Considerations

- Wake word detection runs locally - no audio is sent to external services
- The Picovoice access key is only used for model initialization
- Transcription can use local Whisper models for complete privacy
- Consider the security implications of voice-activated systems in your environment
