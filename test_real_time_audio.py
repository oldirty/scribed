#!/usr/bin/env python3
"""Audio device discovery and real-time audio demo for Scribed."""

import sys
from pathlib import Path

# Add the src directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def list_audio_devices():
    """List available audio input devices."""
    print("🎤 Available Audio Input Devices:")
    print("=" * 40)

    try:
        from scribed.audio.microphone_input import MicrophoneInput

        if not MicrophoneInput.is_available():
            print("❌ Audio input not available. Install dependencies:")
            print("   pip install pyaudio")
            return

        devices = MicrophoneInput.list_devices()

        if not devices:
            print("No audio input devices found.")
            return

        for i, device in enumerate(devices):
            default_marker = " (DEFAULT)" if device.get('is_default', False) else ""
            print(f"{i}: {device['name']}{default_marker}")
            print(f"   Channels: {device['channels']}")
            print(f"   Sample Rate: {device['sample_rate']} Hz")
            print()

        return devices

    except Exception as e:
        print(f"❌ Error listing devices: {e}")
        return None


def test_microphone_input():
    """Test basic microphone input functionality."""
    print("\n🔊 Testing Microphone Input:")
    print("=" * 40)

    try:
        from scribed.audio.microphone_input import MicrophoneInput

        config = {
            "device_index": None,  # Default device
            "sample_rate": 16000,
            "channels": 1,
            "chunk_size": 1024
        }

        mic = MicrophoneInput(config)
        print("✓ Microphone input created successfully")

        info = mic.get_info()
        print(f"✓ Device: {info['device_index'] or 'Default'}")
        print(f"✓ Sample Rate: {info['sample_rate']} Hz")
        print(f"✓ Channels: {info['channels']}")
        print(f"✓ Chunk Size: {info['chunk_size']} frames")

        return True

    except Exception as e:
        print(f"❌ Microphone test failed: {e}")
        return False


def test_transcription_service():
    """Test transcription service availability."""
    print("\n📝 Testing Transcription Service:")
    print("=" * 40)

    try:
        from scribed.transcription.service import TranscriptionService
        from scribed.config import Config

        config = Config()
        service = TranscriptionService(config.transcription.model_dump())

        if service.is_available():
            print("✓ Transcription service available")
            engine_info = service.get_engine_info()
            print(f"✓ Provider: {engine_info['provider']}")
            print(f"✓ Model: {engine_info.get('model', 'default')}")
            print(f"✓ Language: {engine_info.get('language', 'auto-detect')}")
            return True
        else:
            print("❌ Transcription service not available")
            return False

    except Exception as e:
        print(f"❌ Transcription test failed: {e}")
        return False


def test_real_time_integration():
    """Test real-time transcription service integration."""
    print("\n🎯 Testing Real-time Integration:")
    print("=" * 40)

    try:
        from scribed.realtime.transcription_service import RealTimeTranscriptionService
        from scribed.config import Config

        config = Config()

        # Check dependencies
        deps = RealTimeTranscriptionService.check_dependencies()
        print("Dependency Check:")
        for dep, available in deps.items():
            status = "✓" if available else "❌"
            print(f"  {status} {dep}: {available}")

        if not all(deps.values()):
            print("\n⚠️  Some dependencies missing, but basic functionality available")

        # Create service
        service = RealTimeTranscriptionService(
            wake_word_config=config.wake_word.model_dump(),
            microphone_config=config.microphone.model_dump(),
            transcription_config=config.transcription.model_dump()
        )

        print("✓ Real-time transcription service created")

        status = service.get_status()
        print(f"✓ Service state: {status['state']}")
        print(f"✓ Audio buffer size: {status['audio_buffer_size']}")

        return True

    except Exception as e:
        print(f"❌ Real-time integration test failed: {e}")
        return False


def show_configuration_example():
    """Show example configuration for real-time mode."""
    print("\n⚙️  Configuration for Real-time Mode:")
    print("=" * 40)

    example_config = '''# config.yaml - Real-time transcription setup
source_mode: microphone

microphone:
  device_index: null  # null for default microphone
  sample_rate: 16000
  channels: 1
  chunk_size: 1024

wake_word:
  engine: picovoice
  access_key: "YOUR_PICOVOICE_ACCESS_KEY"  # Get free key at console.picovoice.ai
  keywords: ["porcupine"]  # Built-in wake words available
  sensitivities: [0.5]     # 0.0-1.0, higher = more sensitive
  silence_timeout: 15      # Seconds before stopping transcription
  stop_phrase: "stop listening"

transcription:
  provider: whisper
  language: en-US
  model: base  # tiny, base, small, medium, large

api:
  host: "127.0.0.1"
  port: 8080

output:
  format: txt
  log_to_file: true
  log_file_path: ./logs/transcription.log'''

    print(example_config)


def main():
    """Run the audio system demo."""
    print("🎵 Scribed Real-time Audio System Demo")
    print("=" * 50)

    # Test each component
    devices = list_audio_devices()

    mic_ok = test_microphone_input()
    transcription_ok = test_transcription_service()
    realtime_ok = test_real_time_integration()

    print("\n" + "=" * 50)
    print("📋 Summary:")
    print("=" * 50)

    print(f"🎤 Audio Devices: {'✓' if devices else '❌'} Available")
    print(f"🔊 Microphone Input: {'✓' if mic_ok else '❌'} Working")
    print(f"📝 Transcription: {'✓' if transcription_ok else '❌'} Ready")
    print(f"🎯 Real-time Integration: {'✓' if realtime_ok else '❌'} Functional")

    if all([devices, mic_ok, transcription_ok, realtime_ok]):
        print("\n🎉 Real-time audio system is READY!")
        print("\n📖 Next steps:")
        print("1. Get a free Picovoice access key at https://console.picovoice.ai/")
        print("2. Configure your config.yaml file (see example below)")
        print("3. Run: python demo_wake_word.py")
        print("4. Or run: scribed daemon --config config.yaml")

        show_configuration_example()

    else:
        print("\n❌ Some components need attention.")
        print("💡 Install missing dependencies:")
        print("   pip install \".[wake_word]\"")


if __name__ == "__main__":
    main()
