#!/usr/bin/env python3
"""Test script to verify PICOVOICE_ACCESS_KEY environment variable support."""

import os
import sys
from scribed.config import Config, WakeWordConfig


def test_env_var_support():
    """Test that PICOVOICE_ACCESS_KEY environment variable is properly read."""

    # Test 1: Without environment variable
    if "PICOVOICE_ACCESS_KEY" in os.environ:
        del os.environ["PICOVOICE_ACCESS_KEY"]

    config = WakeWordConfig()
    assert config.access_key is None, f"Expected None, got {config.access_key}"
    print("✅ Test 1 passed: No env var = None")

    # Test 2: With environment variable
    test_key = "test_key_from_env_123"
    os.environ["PICOVOICE_ACCESS_KEY"] = test_key

    config = WakeWordConfig()
    assert (
        config.access_key == test_key
    ), f"Expected {test_key}, got {config.access_key}"
    print("✅ Test 2 passed: Env var is read correctly")

    # Test 3: Explicit config overrides env var
    explicit_key = "explicit_override_key"
    config = WakeWordConfig(access_key=explicit_key)
    assert (
        config.access_key == explicit_key
    ), f"Expected {explicit_key}, got {config.access_key}"
    print("✅ Test 3 passed: Explicit config overrides env var")

    # Test 4: Full Config class works
    config = Config()
    assert (
        config.wake_word.access_key == test_key
    ), f"Expected {test_key}, got {config.wake_word.access_key}"
    print("✅ Test 4 passed: Full Config class reads env var")

    print(
        "\n🎉 All tests passed! PICOVOICE_ACCESS_KEY environment variable support is working correctly."
    )


if __name__ == "__main__":
    try:
        test_env_var_support()
        sys.exit(0)
    except Exception as e:
        print(f"❌ Test failed: {e}")
        sys.exit(1)
