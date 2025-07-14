# Audio Preprocessing Guide

## Overview

Scribed now includes advanced audio preprocessing capabilities that can significantly improve transcription quality by reducing background noise, normalizing volume levels, and applying spectral filtering. This feature is especially useful in noisy environments or when dealing with inconsistent audio levels.

## Features

### 🎯 Core Capabilities

- **Volume Normalization**: Automatically adjusts audio levels to optimal range for transcription
- **Background Noise Reduction**: Uses spectral gating to reduce constant background noise
- **Noise Gate**: Silences audio below a specified threshold to eliminate low-level noise
- **High-Pass Filtering**: Removes low-frequency rumble and handling noise
- **Low-Pass Filtering**: Optional removal of high-frequency noise
- **Spectral Gating**: Advanced frequency-domain noise reduction

### 🔧 Technical Implementation

- **Real-time Processing**: All preprocessing happens in real-time during audio capture
- **Configurable Pipeline**: Each processing step can be enabled/disabled independently
- **Adaptive Noise Profiling**: Learns background noise characteristics automatically
- **Minimal Latency**: Optimized for real-time transcription workflows
- **Fallback Handling**: Gracefully handles missing dependencies

## Installation

### Prerequisites

Audio preprocessing requires additional dependencies for signal processing:

```bash
# Install audio preprocessing dependencies
pip install "scribed[audio_processing]"

# Or install specific dependencies manually
pip install scipy>=1.10.0 librosa>=0.10.0 noisereduce>=2.0.0
```

### Verify Installation

```bash
# Test if preprocessing is available
python -c "from scribed.audio.preprocessing import AudioPreprocessor; print('Available:', AudioPreprocessor.is_available())"

# Run comprehensive test suite
python test_audio_preprocessing.py
```

## Configuration

### Basic Configuration

Add preprocessing configuration to your `config.yaml`:

```yaml
microphone:
  device_index: null
  sample_rate: 16000
  channels: 1
  chunk_size: 1024
  
  # Audio preprocessing settings
  preprocessing:
    enabled: true                    # Enable preprocessing
    volume_normalization: true       # Auto-adjust volume levels
    noise_reduction: true            # Reduce background noise
    target_db: -20.0                # Target volume level (dB)
    noise_gate_threshold: -40.0      # Silence threshold (dB)
    spectral_gating: true           # Advanced noise reduction
    high_pass_cutoff: 85            # Remove low frequencies (Hz)
    low_pass_cutoff: null           # Remove high frequencies (Hz, null=disabled)
```

### Advanced Configuration

#### Volume Normalization

```yaml
preprocessing:
  volume_normalization: true
  target_db: -20.0                  # Target RMS level in dB
                                   # -20 dB is optimal for speech
                                   # -12 dB for louder output
                                   # -30 dB for quieter output
```

#### Noise Reduction

```yaml
preprocessing:
  noise_reduction: true
  noise_gate_threshold: -40.0       # Sounds below this level are reduced
                                   # -40 dB: Standard setting
                                   # -50 dB: More aggressive gating
                                   # -30 dB: Less aggressive gating
  spectral_gating: true            # Enable frequency-domain noise reduction
```

#### Frequency Filtering

```yaml
preprocessing:
  high_pass_cutoff: 85             # Remove frequencies below 85Hz
                                   # 85 Hz: Remove low rumble
                                   # 120 Hz: More aggressive low-cut
                                   # 60 Hz: Minimal filtering
  
  low_pass_cutoff: 8000            # Remove frequencies above 8kHz
                                   # null: No high-frequency filtering
                                   # 8000: Remove high-frequency noise
                                   # 4000: Telephone-quality bandwidth
```

## Usage Examples

### 1. Basic Real-time Transcription with Preprocessing

```python
from scribed.audio.microphone_input import MicrophoneInput

# Configure microphone with preprocessing
config = {
    "device_index": None,
    "sample_rate": 16000,
    "channels": 1,
    "chunk_size": 1024,
    "preprocessing": {
        "enabled": True,
        "volume_normalization": True,
        "noise_reduction": True,
        "target_db": -20.0,
    }
}

# Audio callback function
def process_audio(audio_data: bytes):
    # Audio data is already preprocessed
    print(f"Received {len(audio_data)} bytes of clean audio")

# Start recording with preprocessing
mic = MicrophoneInput(config)
mic.start_recording(process_audio)

# Recording will continue until stopped
# mic.stop_recording()
```

### 2. Custom Preprocessing Pipeline

```python
from scribed.audio.preprocessing import AudioPreprocessor
import numpy as np

# Create custom preprocessor
config = {
    "enabled": True,
    "volume_normalization": False,     # Disable auto-volume
    "noise_reduction": True,
    "noise_gate_threshold": -35.0,     # Custom threshold
    "high_pass_cutoff": 120,          # More aggressive low-cut
    "spectral_gating": True,
}

preprocessor = AudioPreprocessor(config)

# Process raw audio data
raw_audio = np.random.randn(1024).astype(np.float32)
clean_audio = preprocessor.process_audio(raw_audio, 16000)
```

### 3. Environment-Specific Configurations

#### Office Environment (Keyboard/HVAC Noise)
```yaml
preprocessing:
  enabled: true
  noise_reduction: true
  noise_gate_threshold: -45.0      # Higher threshold for office noise
  high_pass_cutoff: 120           # Remove HVAC rumble
  spectral_gating: true
```

#### Home Environment (General Use)
```yaml
preprocessing:
  enabled: true
  volume_normalization: true
  noise_reduction: true
  target_db: -20.0
  noise_gate_threshold: -40.0
  high_pass_cutoff: 85
```

#### Car/Mobile Environment (Road Noise)
```yaml
preprocessing:
  enabled: true
  noise_reduction: true
  noise_gate_threshold: -35.0     # Road noise is louder
  high_pass_cutoff: 150          # Aggressive low-frequency removal
  spectral_gating: true
  volume_normalization: true
  target_db: -18.0              # Slightly louder for car audio
```

## Performance Considerations

### CPU Usage

Audio preprocessing adds computational overhead:

- **Volume Normalization**: ~1-2% CPU increase
- **Noise Gate**: ~1% CPU increase  
- **High/Low-pass Filtering**: ~2-3% CPU increase
- **Spectral Gating**: ~5-10% CPU increase
- **Total with all features**: ~10-15% CPU increase

### Memory Usage

- **Noise Profile**: ~1-2 MB for learned background noise characteristics
- **Processing Buffers**: ~1-5 MB depending on chunk size and sample rate
- **FFT Buffers**: ~2-4 MB for spectral processing

### Latency Impact

- **Basic Preprocessing**: <10ms additional latency
- **Spectral Processing**: ~20-50ms additional latency
- **Total Pipeline**: Typically <100ms for complete preprocessing

## Troubleshooting

### Common Issues

#### 1. Dependencies Not Available

```
ImportError: Audio preprocessing dependencies not available
```

**Solution:**
```bash
pip install "scribed[audio_processing]"
```

#### 2. Poor Noise Reduction Performance

**Symptoms:** Background noise not being reduced effectively

**Solutions:**
- Lower the `noise_gate_threshold` (e.g., from -40 to -45 dB)
- Ensure `spectral_gating` is enabled
- Allow time for noise profile learning (first 30-60 seconds)
- Check microphone positioning and quality

#### 3. Audio Distortion

**Symptoms:** Processed audio sounds distorted or robotic

**Solutions:**
- Increase `noise_gate_threshold` (less aggressive gating)
- Disable `spectral_gating` temporarily
- Adjust `target_db` for volume normalization
- Reduce `high_pass_cutoff` frequency

#### 4. High CPU Usage

**Symptoms:** System becomes slow during audio processing

**Solutions:**
- Disable `spectral_gating` (most CPU-intensive feature)
- Increase `chunk_size` (process larger blocks less frequently)
- Disable unnecessary preprocessing features
- Consider using a lower sample rate (e.g., 8000 Hz for voice-only)

### Debug Configuration

For troubleshooting, use this minimal configuration:

```yaml
preprocessing:
  enabled: true
  volume_normalization: false     # Disable to isolate issues
  noise_reduction: false          # Disable to isolate issues
  spectral_gating: false         # Disable to isolate issues
  high_pass_cutoff: 85           # Keep basic filtering
```

Gradually enable features to identify problematic settings.

### Logging

Enable debug logging to monitor preprocessing performance:

```python
import logging
logging.getLogger('scribed.audio.preprocessing').setLevel(logging.DEBUG)
```

## Best Practices

### 1. Microphone Setup

- **Use a quality microphone**: Better input = better output
- **Position correctly**: 6-12 inches from mouth, avoid breathing directly on mic
- **Stable placement**: Reduce handling noise and vibration
- **Test environment**: Run preprocessing tests in your actual usage environment

### 2. Configuration Tuning

- **Start with defaults**: Use recommended settings first
- **Adjust incrementally**: Change one parameter at a time
- **Test with actual content**: Use real speech, not test tones
- **Monitor transcription quality**: The goal is better transcription, not just cleaner audio

### 3. Environment Optimization

- **Reduce noise sources**: Turn off fans, close windows when possible
- **Use consistent environment**: Preprocessing adapts to your specific noise profile
- **Allow adaptation time**: Let the system learn your environment for 1-2 minutes

### 4. Performance Optimization

- **Profile your system**: Monitor CPU usage during processing
- **Adjust chunk size**: Larger chunks = lower CPU, slightly higher latency
- **Selective features**: Only enable preprocessing features you actually need
- **Test with your workflow**: Ensure preprocessing doesn't interfere with other features

## Integration with Other Features

### Wake Word Detection

Preprocessing works seamlessly with wake word detection:

```yaml
wake_word:
  engine: picovoice
  keywords: ["porcupine"]
  
microphone:
  preprocessing:
    enabled: true
    # Preprocessing helps wake word accuracy
    noise_reduction: true
    volume_normalization: true
```

### Real-time Transcription

Preprocessing improves transcription quality:

```yaml
transcription:
  provider: whisper
  model: base
  
microphone:
  preprocessing:
    enabled: true
    # Clean audio = better transcription
    volume_normalization: true
    noise_reduction: true
    high_pass_cutoff: 85
```

### Voice Commands

Preprocessing enhances voice command recognition:

```yaml
power_words:
  enabled: true
  
microphone:
  preprocessing:
    enabled: true
    # Clear audio improves command recognition
    volume_normalization: true
    noise_gate_threshold: -35.0  # Slightly higher for commands
```

## API Reference

### AudioPreprocessor Class

```python
from scribed.audio.preprocessing import AudioPreprocessor

# Initialize preprocessor
config = {
    "enabled": True,
    "volume_normalization": True,
    "noise_reduction": True,
    "target_db": -20.0,
    "noise_gate_threshold": -40.0,
    "spectral_gating": True,
    "high_pass_cutoff": 85,
    "low_pass_cutoff": None,
}
preprocessor = AudioPreprocessor(config)

# Process audio
import numpy as np
audio_data = np.random.randn(1024).astype(np.float32)
processed_audio = preprocessor.process_audio(audio_data, sample_rate=16000)

# Get configuration
current_config = preprocessor.get_config()

# Reset noise profile (if noise environment changes)
preprocessor.reset_noise_profile()

# Check availability
is_available = AudioPreprocessor.is_available()
```

### MicrophoneInput Integration

```python
from scribed.audio.microphone_input import MicrophoneInput

# Configure with preprocessing
config = {
    "sample_rate": 16000,
    "channels": 1,
    "preprocessing": {
        "enabled": True,
        "volume_normalization": True,
        "noise_reduction": True,
    }
}

mic = MicrophoneInput(config)

# Check preprocessing status
info = mic.get_info()
print(f"Preprocessing enabled: {info['preprocessing_enabled']}")
print(f"Preprocessing config: {info.get('preprocessing_config', {})}")
```

---

## Support

For issues, questions, or feature requests related to audio preprocessing:

1. **Check logs**: Enable debug logging for detailed information
2. **Test configuration**: Use `test_audio_preprocessing.py` to verify setup
3. **Review performance**: Monitor CPU and memory usage
4. **File issues**: Report bugs with configuration and system details

Audio preprocessing significantly improves transcription quality in real-world environments. Start with the default configuration and adjust based on your specific needs and environment.
