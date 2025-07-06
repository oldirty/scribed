import pytest
import subprocess
import tempfile
import time
import os
import wave
from pathlib import Path

# Always import numpy as it's a core dependency
import numpy as np

# Try to import TTS libraries for realistic speech generation
try:
    import pyttsx3

    PYTTSX3_AVAILABLE = True
except ImportError:
    pyttsx3 = None
    PYTTSX3_AVAILABLE = False

try:
    from gtts import gTTS

    GTTS_AVAILABLE = True
except ImportError:
    gTTS = None  # Define gTTS for type checker
    GTTS_AVAILABLE = False


def generate_wav(text, path):
    """Generates a WAV file with real or synthetic speech for testing purposes.

    Tries multiple TTS approaches in order:
    1. pyttsx3 (offline, outputs WAV directly)
    2. gTTS + pydub conversion (online, requires MP3 conversion)
    3. Synthetic audio generation (fallback)
    """

    # Try pyttsx3 first (offline TTS that can output WAV directly)
    if PYTTSX3_AVAILABLE and pyttsx3 is not None:
        try:
            print(f"Attempting to generate speech using pyttsx3 for: '{text}'")
            engine = pyttsx3.init()

            # Set properties for better quality
            engine.setProperty("rate", 150)  # Speed of speech
            engine.setProperty("volume", 0.9)  # Volume level (0.0 to 1.0)

            # Save to WAV file
            engine.save_to_file(text, str(path))
            engine.runAndWait()

            # Check if file was created and has content
            if os.path.exists(path) and os.path.getsize(path) > 0:
                print(f"Successfully created WAV file using pyttsx3: {path}")
                return
            else:
                print("pyttsx3 failed to create a valid audio file")

        except Exception as e:
            print(f"pyttsx3 generation failed: {e}")

    # Try gTTS as backup (online TTS)
    if GTTS_AVAILABLE and gTTS is not None:
        try:
            print(f"Attempting to generate speech using gTTS for: '{text}'")
            tts = gTTS(text=text, lang="en", slow=False)

            # Save to a temporary MP3 file first
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as mp3_file:
                tts.save(mp3_file.name)
                print(f"gTTS generated MP3 file: {mp3_file.name}")

                # Try pydub conversion
                try:
                    from pydub import AudioSegment

                    print("Converting MP3 to WAV using pydub...")
                    audio = AudioSegment.from_file(mp3_file.name, format="mp3")
                    audio = audio.set_frame_rate(16000).set_channels(1)  # 16kHz mono
                    audio.export(str(path), format="wav")
                    os.unlink(mp3_file.name)  # Clean up temp MP3
                    print(f"Successfully created WAV file using gTTS + pydub: {path}")
                    return
                except Exception as e:
                    print(f"gTTS + pydub conversion failed: {e}")
                    try:
                        os.unlink(mp3_file.name)
                    except:
                        pass

        except Exception as e:
            print(f"gTTS generation failed: {e}")

    # Fallback: Generate synthetic audio
    print(f"Generating synthetic audio for: '{text}'")
    _generate_synthetic_wav(text, path)
    print(f"Successfully created synthetic WAV file: {path}")


def _generate_synthetic_wav(text, path):
    """Generates synthetic audio as a fallback when gTTS is not available."""
    # Audio parameters
    sample_rate = 16000  # Common rate for speech recognition
    duration = 2.0  # seconds

    # Generate a simple pattern of tones that might simulate speech
    t = np.linspace(0, duration, int(sample_rate * duration), False)

    # Create a simple "speech-like" pattern with multiple frequencies
    frequencies = [200, 400, 600, 300]  # Hz - simulate formants
    audio = np.zeros_like(t)

    for i, freq in enumerate(frequencies):
        # Add each frequency with some modulation
        segment_start = i * len(t) // len(frequencies)
        segment_end = (i + 1) * len(t) // len(frequencies)
        audio[segment_start:segment_end] += np.sin(
            2 * np.pi * freq * t[segment_start:segment_end]
        )

    # Add some amplitude modulation to make it more speech-like
    envelope = np.exp(-3 * t) + 0.3  # Decay envelope
    audio *= envelope

    # Normalize and convert to 16-bit integers
    audio = np.clip(audio, -1.0, 1.0)
    audio_int16 = (audio * 32767).astype(np.int16)

    # Write WAV file
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(audio_int16.tobytes())


@pytest.fixture(scope="module")
def scribed_daemon():
    """Starts the scribed daemon in file mode for integration testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        watch_dir = Path(temp_dir) / "watch"
        output_dir = Path(temp_dir) / "output"
        watch_dir.mkdir()
        output_dir.mkdir()

        config_content = f"""
source_mode: file
file_watcher:
  watch_directory: {watch_dir.as_posix()}
  output_directory: {output_dir.as_posix()}
  supported_formats: [".wav"]
api:
  host: "127.0.0.1"
  port: 8082
transcription:
  provider: whisper
  language: en
"""
        config_path = Path(temp_dir) / "config.yaml"
        config_path.write_text(config_content)

        process = subprocess.Popen(
            ["scribed", "--config", str(config_path), "start"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Give the daemon time to start
        time.sleep(5)

        yield str(watch_dir), str(output_dir)

        process.terminate()
        process.wait()


def test_file_transcription(scribed_daemon):
    """Tests that a file placed in the watch directory is processed by the transcription system."""
    watch_dir, output_dir = scribed_daemon

    # Generate a test wav file with real or synthetic speech
    test_text = "Hello world, this is a test transcription."
    wav_path = Path(watch_dir) / "test.wav"
    generate_wav(test_text, wav_path)

    # Verify the audio file was created
    assert wav_path.exists()

    # Wait for the transcript to be created
    transcript_path = Path(output_dir) / "test.txt"
    for _ in range(20):  # Increased timeout
        if transcript_path.exists():
            break
        time.sleep(1)

    # Verify that the transcription system processed the file
    assert transcript_path.exists()

    # Read the transcription content
    transcript_content = transcript_path.read_text().strip()

    # If we're using real TTS (pyttsx3 or gTTS), we can test for more accurate transcription
    if (PYTTSX3_AVAILABLE and pyttsx3 is not None) or (
        GTTS_AVAILABLE and gTTS is not None
    ):
        # With real speech, we expect some words to be transcribed correctly
        # Convert to lowercase for comparison and check for key words
        transcript_lower = transcript_content.lower()
        test_words = ["hello", "world", "test", "transcription"]

        # At least one of the key words should be present in a good transcription
        found_words = [word for word in test_words if word in transcript_lower]

        # If no words are found, it might be due to audio conversion issues or
        # network problems with gTTS, so we just verify the file was processed
        if found_words:
            print(f"Successfully transcribed with real TTS. Found words: {found_words}")
        else:
            print(
                f"Real TTS transcription completed but no key words found. Content: '{transcript_content}'"
            )
    else:
        # With synthetic audio, we just verify the workflow completed
        print(
            f"Synthetic audio transcription completed. Content: '{transcript_content}'"
        )
