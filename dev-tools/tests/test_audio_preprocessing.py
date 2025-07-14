#!/usr/bin/env python3
"""Test script for audio preprocessing functionality."""

import logging
import time
import sys
from pathlib import Path

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent / "src"))

try:
    from scribed.audio.microphone_input import MicrophoneInput, AUDIO_AVAILABLE, PREPROCESSING_AVAILABLE
    from scribed.audio.preprocessing import AudioPreprocessor
except ImportError as e:
    print(f"Import error: {e}")
    print("Make sure to install dependencies: pip install -e '.[audio_processing]'")
    sys.exit(1)


def test_preprocessing_availability():
    """Test if preprocessing dependencies are available."""
    print("=== Audio Preprocessing Availability Test ===")
    print(f"Audio available: {AUDIO_AVAILABLE}")
    print(f"Preprocessing available: {PREPROCESSING_AVAILABLE}")
    
    if not AUDIO_AVAILABLE:
        print("❌ Audio dependencies missing. Install with: pip install pyaudio numpy")
        return False
        
    if not PREPROCESSING_AVAILABLE:
        print("❌ Preprocessing dependencies missing. Install with: pip install 'scribed[audio_processing]'")
        return False
    
    print("✅ All dependencies available")
    return True


def test_preprocessor_config():
    """Test preprocessor configuration."""
    print("\n=== Audio Preprocessor Configuration Test ===")
    
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
    
    try:
        preprocessor = AudioPreprocessor(config)
        print("✅ Preprocessor created successfully")
        
        # Check configuration
        actual_config = preprocessor.get_config()
        print(f"Configuration: {actual_config}")
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to create preprocessor: {e}")
        return False


def test_microphone_with_preprocessing():
    """Test microphone input with preprocessing."""
    print("\n=== Microphone Input with Preprocessing Test ===")
    
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
            "noise_gate_threshold": -40.0,
        }
    }
    
    try:
        mic = MicrophoneInput(config)
        print("✅ Microphone with preprocessing created successfully")
        
        info = mic.get_info()
        print(f"Microphone info: {info}")
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to create microphone with preprocessing: {e}")
        return False


def test_audio_recording():
    """Test actual audio recording with preprocessing (optional - requires microphone)."""
    print("\n=== Live Audio Recording Test (5 seconds) ===")
    print("This test will record 5 seconds of audio with preprocessing enabled.")
    
    response = input("Do you want to test live audio recording? (y/n): ").strip().lower()
    if response != 'y':
        print("Skipping live audio test")
        return True
    
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
            "noise_gate_threshold": -40.0,
            "spectral_gating": True,
        }
    }
    
    chunks_received = 0
    
    def audio_callback(audio_data: bytes):
        nonlocal chunks_received
        chunks_received += 1
        if chunks_received % 16 == 0:  # Print every ~1 second
            print(f"Received {chunks_received} audio chunks ({len(audio_data)} bytes each)")
    
    try:
        mic = MicrophoneInput(config)
        print("✅ Starting audio recording with preprocessing...")
        print("Speak into your microphone!")
        
        mic.start_recording(audio_callback)
        time.sleep(5)
        mic.stop_recording()
        
        print(f"✅ Recording completed. Processed {chunks_received} audio chunks")
        return True
        
    except Exception as e:
        print(f"❌ Audio recording test failed: {e}")
        return False


def main():
    """Run all tests."""
    logging.basicConfig(level=logging.INFO)
    
    print("Audio Preprocessing Test Suite")
    print("=" * 50)
    
    tests = [
        ("Availability", test_preprocessing_availability),
        ("Preprocessor Config", test_preprocessor_config),
        ("Microphone Integration", test_microphone_with_preprocessing),
        ("Live Recording", test_audio_recording),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ Test '{test_name}' crashed: {e}")
            results.append((test_name, False))
    
    print("\n" + "=" * 50)
    print("Test Results Summary:")
    
    passed = 0
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status}: {test_name}")
        if result:
            passed += 1
    
    print(f"\nPassed: {passed}/{len(results)} tests")
    
    if passed == len(results):
        print("🎉 All tests passed! Audio preprocessing is ready to use.")
    else:
        print("❌ Some tests failed. Check the error messages above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
