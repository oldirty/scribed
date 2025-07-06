#!/usr/bin/env python3
"""
Standalone test for gTTS functionality
"""

import tempfile
import os
from pathlib import Path


def test_gtts_standalone():
    """Test gTTS generation standalone"""
    try:
        from gtts import gTTS

        print("✓ gTTS import successful")

        # Generate speech
        text = "Hello world, this is a test."
        tts = gTTS(text=text, lang="en", slow=False)

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as mp3_file:
            tts.save(mp3_file.name)
            print(f"✓ MP3 generated: {mp3_file.name}")

            # Check file size
            file_size = os.path.getsize(mp3_file.name)
            print(f"✓ MP3 file size: {file_size} bytes")

            # Try pydub conversion
            try:
                from pydub import AudioSegment

                print("✓ pydub import successful")

                # Create output path
                wav_path = mp3_file.name.replace(".mp3", ".wav")

                # Convert
                audio = AudioSegment.from_mp3(mp3_file.name)
                print(f"✓ MP3 loaded successfully. Duration: {len(audio)} ms")

                audio = audio.set_frame_rate(16000).set_channels(1)
                audio.export(wav_path, format="wav")
                print(f"✓ WAV exported successfully: {wav_path}")

                # Check WAV file
                wav_size = os.path.getsize(wav_path)
                print(f"✓ WAV file size: {wav_size} bytes")

                # Cleanup
                os.unlink(mp3_file.name)
                os.unlink(wav_path)
                print("✓ Files cleaned up")

                return True

            except Exception as e:
                print(f"✗ pydub conversion failed: {e}")
                os.unlink(mp3_file.name)
                return False

    except Exception as e:
        print(f"✗ gTTS failed: {e}")
        return False


if __name__ == "__main__":
    success = test_gtts_standalone()
    print(f"\nResult: {'SUCCESS' if success else 'FAILED'}")
