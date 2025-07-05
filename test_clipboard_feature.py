#!/usr/bin/env python3
"""Test script for the new clipboard transcription functionality."""

import asyncio
import requests
import sys
from pathlib import Path

# Add src to path for testing
sys.path.insert(0, str(Path(__file__).parent / "src"))

from scribed.config import Config
from scribed.clipboard import is_clipboard_available, set_clipboard_text, get_clipboard_text


def test_clipboard_availability():
    """Test if clipboard functionality is available."""
    print("Testing clipboard availability...")
    if is_clipboard_available():
        print("✅ Clipboard is available")
        
        # Test setting and getting text
        test_text = "Test clipboard functionality"
        if set_clipboard_text(test_text):
            print("✅ Successfully set clipboard text")
            
            retrieved_text = get_clipboard_text()
            if retrieved_text == test_text:
                print("✅ Successfully retrieved clipboard text")
                return True
            else:
                print(f"❌ Retrieved text doesn't match: '{retrieved_text}' vs '{test_text}'")
                return False
        else:
            print("❌ Failed to set clipboard text")
            return False
    else:
        print("❌ Clipboard is not available")
        return False


def test_api_endpoint():
    """Test the API endpoint (requires daemon to be running)."""
    print("\nTesting API endpoint...")
    config = Config.from_env()
    
    try:
        # First check if daemon is running
        response = requests.get(f"http://{config.api.host}:{config.api.port}/status", timeout=5)
        if response.status_code == 200:
            print("✅ Daemon is running")
            
            # Test the record-to-clipboard endpoint with a short duration
            print("Testing /record-to-clipboard endpoint...")
            test_request = {
                "duration": 2,  # Short duration for testing
                "provider": "whisper"
            }
            
            print("⚠️  This will record audio for 2 seconds - make sure your microphone is working")
            input("Press Enter to continue or Ctrl+C to skip...")
            
            response = requests.post(
                f"http://{config.api.host}:{config.api.port}/record-to-clipboard",
                json=test_request,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                if result["success"]:
                    print("✅ API endpoint working correctly")
                    print(f"Transcription: {result.get('text', 'No text returned')}")
                    print(f"Processing time: {result.get('processing_time', 'N/A')}s")
                    return True
                else:
                    print(f"❌ API returned error: {result.get('error', 'Unknown error')}")
                    return False
            else:
                print(f"❌ API request failed: {response.status_code}")
                print(f"Response: {response.text}")
                return False
        else:
            print("❌ Daemon is not running")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to daemon - make sure it's running")
        return False
    except Exception as e:
        print(f"❌ Error testing API: {e}")
        return False


def test_config():
    """Test the new configuration options."""
    print("\nTesting configuration...")
    config = Config.from_env()
    
    print(f"Clipboard enabled: {config.output.enable_clipboard}")
    print(f"Clipboard on final: {config.output.clipboard_on_final}")
    print("✅ Configuration loaded successfully")
    return True


def main():
    """Run all tests."""
    print("🔬 Testing Scribed Clipboard Transcription Feature\n")
    
    results = {
        "clipboard": test_clipboard_availability(),
        "config": test_config(),
        "api": test_api_endpoint()
    }
    
    print("\n📊 Test Results:")
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {test_name}: {status}")
    
    all_passed = all(results.values())
    print(f"\n🎯 Overall: {'✅ ALL TESTS PASSED' if all_passed else '❌ SOME TESTS FAILED'}")
    
    if not all_passed:
        print("\n💡 Tips:")
        if not results["clipboard"]:
            print("  - On Linux, install xclip or xsel: sudo apt-get install xclip")
        if not results["api"]:
            print("  - Start the daemon first: scribed start")
            print("  - Check if the daemon is running: scribed status")


if __name__ == "__main__":
    main()
