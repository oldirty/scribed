#!/usr/bin/env python3
"""
Test script to simulate pyttsx3 initialization failure
This helps test the fallback behavior when eSpeak is not available
"""

import sys
import os
import tempfile
from pathlib import Path

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# Remove pyttsx3 from available modules to simulate it not being installed
if "pyttsx3" in sys.modules:
    del sys.modules["pyttsx3"]

# Block pyttsx3 import by setting it to None
sys.modules["pyttsx3"] = None

# Now import the test functions
from tests.test_integration import generate_wav

# Import the availability flags by forcing a reload
import importlib

test_integration = importlib.import_module("tests.test_integration")
print(f"TTS availability after blocking pyttsx3:")
print(f"  pyttsx3: {test_integration.PYTTSX3_AVAILABLE}")
print(f"  gTTS: {test_integration.GTTS_AVAILABLE}")

# Test fallback behavior
with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
    test_path = temp_file.name

try:
    print(f"\nTesting audio generation without pyttsx3...")
    generate_wav("Hello world test", test_path)

    if os.path.exists(test_path) and os.path.getsize(test_path) > 0:
        print(f"✅ Successfully generated audio file: {test_path}")
        print(f"   File size: {os.path.getsize(test_path)} bytes")
    else:
        print(f"❌ Failed to generate audio file")

finally:
    # Clean up
    if os.path.exists(test_path):
        os.unlink(test_path)
        print(f"Cleaned up test file: {test_path}")
