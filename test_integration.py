#!/usr/bin/env python3
"""Quick integration test for power words with configuration."""

import sys
from pathlib import Path

# Add the src directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from scribed.config import Config
from scribed.power_words import PowerWordsEngine

def main():
    """Run integration test."""
    print("🔧 Testing power words integration...")

    # Test configuration loading
    try:
        config = Config.from_file('test_config.yaml')
        print("✅ Configuration loaded successfully")
        print(f"   Power words enabled: {config.power_words.enabled}")
        print(f"   Number of mappings: {len(config.power_words.mappings)}")
    except Exception as e:
        print(f"❌ Configuration loading failed: {e}")
        return False

    # Test power words engine
    try:
        engine = PowerWordsEngine(config.power_words)
        print("✅ Power words engine initialized")
    except Exception as e:
        print(f"❌ Power words engine initialization failed: {e}")
        return False

    # Test detection
    try:
        test_text = 'hello world, what time is it?'
        detected = engine.detect_power_words(test_text)
        print(f"✅ Detected {len(detected)} power words in test text")
        for phrase, command in detected:
            print(f"   - '{phrase}' → '{command}'")
    except Exception as e:
        print(f"❌ Power words detection failed: {e}")
        return False

    print("🎉 Integration test passed!")
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
