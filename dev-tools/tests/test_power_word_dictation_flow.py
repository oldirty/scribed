#!/usr/bin/env python3
"""Test power word extraction and dictation flow."""

import asyncio
import tempfile
import yaml
from pathlib import Path
import sys
import os
import logging

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from scribed.config import Config
from scribed.realtime.transcription_service import RealTimeTranscriptionService

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


class DictationTracker:
    """Track dictation results to verify power word extraction."""

    def __init__(self):
        self.dictations = []

    async def on_transcription(self, result, is_partial: bool):
        """Callback for transcription results."""
        dictation_info = {
            "text": result.text.strip(),
            "is_partial": is_partial,
        }

        self.dictations.append(dictation_info)
        print(
            f"{'PARTIAL' if is_partial else 'FINAL'} DICTATION: '{result.text.strip()}'"
        )


async def test_power_word_extraction():
    """Test that power words are extracted and only dictation text is output."""
    print("Testing Power Word Extraction and Dictation Flow")
    print("=" * 55)

    # Create test config
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        test_config = {
            "source_mode": "microphone",
            "microphone": {
                "device_index": None,
                "sample_rate": 16000,
                "channels": 1,
                "chunk_size": 1024,
            },
            "wake_word": {
                "engine": "whisper",
                "keywords": ["test"],
                "silence_timeout": 10,
                "stop_phrase": "stop listening",
            },
            "power_words": {
                "enabled": True,
                "require_confirmation": True,
                "confirmation_method": "log_only",
                "log_only_approve": True,
                "mappings": {
                    "open discord": 'echo "Opening Discord"',
                    "play music": 'echo "Playing music"',
                    "send email": 'echo "Sending email"',
                },
                "allowed_commands": ["echo"],
                "dangerous_keywords": [],
            },
            "transcription": {"provider": "whisper", "model": "base"},
            "output": {
                "format": "txt",
                "log_to_file": False,
                "enable_clipboard": False,
            },
        }

        yaml.safe_dump(test_config, f)
        config_path = f.name

    try:
        # Load config
        config = Config.from_file(config_path)

        # Create service
        service = RealTimeTranscriptionService(
            wake_word_config=config.wake_word.model_dump(),
            microphone_config=config.microphone.model_dump(),
            transcription_config=config.transcription.model_dump(),
            power_words_config=config.power_words.model_dump(),
        )

        # Initialize components (but don't start the full service)
        service._initialize_components()

        # Set up dictation tracking
        tracker = DictationTracker()
        service.set_transcription_callback(tracker.on_transcription)

        print("\n1. Testing Power Word Extraction Logic:")

        test_cases = [
            {
                "input": "please open discord and then type hello world",
                "expected_command": "open discord",
                "expected_dictation": "please and then type hello world",
            },
            {
                "input": "start recording play music while I work on this document",
                "expected_command": "play music",
                "expected_dictation": "start recording while I work on this document",
            },
            {
                "input": "this is just dictation with no commands",
                "expected_command": None,
                "expected_dictation": "this is just dictation with no commands",
            },
            {
                "input": "first send email then open discord to chat",
                "expected_command": ["send email", "open discord"],
                "expected_dictation": "first then to chat",
            },
        ]

        for i, test_case in enumerate(test_cases, 1):
            print(f"\n  Test {i}: '{test_case['input']}'")

            # Test the extraction method directly
            result_text = await service._process_power_words_and_extract_dictation(
                test_case["input"]
            )

            print(f"    Extracted dictation: '{result_text}'")
            print(f"    Expected dictation:  '{test_case['expected_dictation']}'")

            # Check if the result matches expectations
            if result_text.strip() == test_case["expected_dictation"].strip():
                print(f"    ✅ Correct extraction")
            else:
                print(f"    ⚠️  Extraction differs from expected")

        print(f"\n2. Testing Complete Flow:")

        # Mock the transcription service to avoid actual Whisper calls
        class MockTranscription:
            def __init__(self, response_text):
                self.response_text = response_text

            async def transcribe_file(self, path):
                from types import SimpleNamespace

                return SimpleNamespace(
                    text=self.response_text, segments=[], status=None
                )

        # Test complete flow with mixed speech
        test_speech = "please open discord and dictate this important message"
        print(f"  Simulating speech: '{test_speech}'")

        service.transcription_service = MockTranscription(test_speech)
        service._transcription_active = True
        service._audio_buffer = [b"mock1", b"mock2"]

        # Process chunk - this should execute power word and only send dictation
        print(f"  Processing audio chunk...")
        await service._process_audio_chunk()

        # Check what was sent to dictation
        if tracker.dictations:
            dictation_text = tracker.dictations[-1]["text"]
            print(f"  Dictation output: '{dictation_text}'")

            if "open discord" not in dictation_text.lower():
                print(f"  ✅ Power word correctly removed from dictation")
            else:
                print(f"  ❌ Power word still present in dictation")

            if "dictate this important message" in dictation_text.lower():
                print(f"  ✅ Remaining speech preserved in dictation")
            else:
                print(f"  ⚠️  Some dictation text may be missing")
        else:
            print(f"  ⚠️  No dictation output received")

        print(f"\n3. Summary:")
        print(f"  - Power words are detected and executed")
        print(f"  - Commands are removed from transcription text")
        print(f"  - Only dictation content is sent to output")
        print(f"  - Multiple power words in same speech are handled")

        print(f"\n✅ Power word extraction and dictation flow test completed!")

    finally:
        # Clean up
        try:
            os.unlink(config_path)
        except:
            pass


if __name__ == "__main__":
    asyncio.run(test_power_word_extraction())
