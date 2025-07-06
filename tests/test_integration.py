
import pytest
import subprocess
import tempfile
import time
import os
from pathlib import Path

import subprocess

def generate_wav(text, path):
    """Generates a WAV file from text using Windows PowerShell."""
    command = [
        "powershell",
        "-Command",
        f"Add-Type -AssemblyName System.Speech; "
        f"$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        f"$synth.SetOutputToWaveFile('{path}'); "
        f"$synth.Speak('{text}');"
    ]
    subprocess.run(command, check=True, shell=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE)

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
    """Tests that a file placed in the watch directory is transcribed."""
    watch_dir, output_dir = scribed_daemon

    # Generate a test wav file
    wav_text = "Hello world."
    wav_path = Path(watch_dir) / "test.wav"
    generate_wav(wav_text, wav_path)

    # Wait for the transcript to be created
    transcript_path = Path(output_dir) / "test.txt"
    for _ in range(20):  # Increased timeout
        if transcript_path.exists():
            break
        time.sleep(1)
    
    assert transcript_path.exists()

    transcript_content = transcript_path.read_text()
    assert wav_text in transcript_content
