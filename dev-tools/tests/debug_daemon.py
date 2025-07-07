#!/usr/bin/env python3
"""
Simple test to debug the scribed daemon startup
"""

import subprocess
import tempfile
import time
from pathlib import Path

# Create a minimal config
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

    print(f"Config file: {config_path}")
    print(f"Config content:\n{config_content}")

    # Try to start the daemon
    print("Starting daemon...")

    try:
        process = subprocess.Popen(
            ["scribed", "--config", str(config_path), "start"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        # Wait a bit and check status
        time.sleep(3)

        if process.poll() is None:
            print("✅ Daemon appears to be running")

            # Try to get status
            try:
                status_result = subprocess.run(
                    ["scribed", "--config", str(config_path), "status"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                print(f"Status command result: {status_result.returncode}")
                print(f"Status stdout: {status_result.stdout}")
                print(f"Status stderr: {status_result.stderr}")
            except subprocess.TimeoutExpired:
                print("Status command timed out")

        else:
            stdout, stderr = process.communicate()
            print(f"❌ Daemon exited with code: {process.returncode}")
            print(f"STDOUT: {stdout}")
            print(f"STDERR: {stderr}")

        # Clean up
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()

    except Exception as e:
        print(f"Error starting daemon: {e}")
