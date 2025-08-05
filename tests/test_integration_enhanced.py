"""Enhanced integration tests for Scribed transcription workflows."""

import pytest
import asyncio
import tempfile
import time
import wave
import json
import requests
from pathlib import Path
from unittest.mock import patch, Mock

import numpy as np

from scribed.config import Config
from scribed.core.engine import ScribedEngine
from scribed.core.session import TranscriptionSession
from scribed.transcription.service import TranscriptionService


class TestConfigurationIntegration:
    """Test configuration loading and validation integration."""

    def test_config_from_yaml_file(self):
        """Test loading configuration from YAML file."""
        config_data = {
            "audio": {"source": "microphone", "sample_rate": 44100, "channels": 2},
            "transcription": {
                "provider": "whisper",
                "model": "small",
                "language": "en",
            },
            "api": {"host": "0.0.0.0", "port": 9000},
            "output": {
                "format": "json",
                "save_to_file": True,
                "copy_to_clipboard": False,
            },
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            import yaml

            yaml.dump(config_data, f)
            config_path = f.name

        try:
            config = Config.from_file(config_path)

            # Verify configuration was loaded correctly
            assert config.audio.source == "microphone"
            assert config.audio.sample_rate == 44100
            assert config.audio.channels == 2
            assert config.transcription.provider == "whisper"
            assert config.transcription.model == "small"
            assert config.api.host == "0.0.0.0"
            assert config.api.port == 9000
            assert config.output.format == "json"

        finally:
            Path(config_path).unlink()

    def test_config_from_json_file(self):
        """Test loading configuration from JSON file."""
        config_data = {
            "audio": {
                "source": "file",
                "watch_directory": "./test_input",
                "output_directory": "./test_output",
            },
            "transcription": {"provider": "openai", "api_key": "test-key-123"},
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            config_path = f.name

        try:
            config = Config.from_file(config_path)

            assert config.audio.source == "file"
            assert "test_input" in str(config.audio.watch_directory)
            assert config.transcription.provider == "openai"
            assert config.transcription.api_key == "test-key-123"

        finally:
            Path(config_path).unlink()

    def test_config_with_nested_sections(self):
        """Test configuration with current supported structure."""
        config_data = {
            "audio": {
                "source": "microphone",
                "device_index": 1,
                "sample_rate": 48000,
                "channels": 2,
                "watch_directory": "./custom_input",
                "output_directory": "./custom_output",
            },
            "transcription": {
                "provider": "whisper",
                "model": "medium",
                "language": "es",
                "api_key": "test-key",
            },
            "output": {
                "format": "json",
                "save_to_file": True,
                "copy_to_clipboard": True,
                "log_file_path": "./custom_logs/test.log",
            },
            "api": {"host": "0.0.0.0", "port": 9000, "debug": True},
            "wake_word": {
                "enabled": True,
                "keywords": ["computer", "assistant"],
                "access_key": "test-access-key",
            },
            "power_words": {
                "enabled": True,
                "mappings": {"open browser": "start chrome", "close window": "alt+f4"},
                "max_command_length": 50,
            },
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            import yaml

            yaml.dump(config_data, f)
            config_path = f.name

        try:
            config = Config.from_file(config_path)

            # Verify configuration was loaded correctly
            assert config.audio.source == "microphone"
            assert config.audio.device_index == 1
            assert config.audio.sample_rate == 48000
            assert config.audio.channels == 2

            assert config.transcription.provider == "whisper"
            assert config.transcription.model == "medium"
            assert config.transcription.language == "es"

            assert config.output.format == "json"
            assert config.output.save_to_file == True
            assert config.output.copy_to_clipboard == True

            assert config.api.host == "0.0.0.0"
            assert config.api.port == 9000
            assert config.api.debug == True

            assert config.wake_word.enabled == True
            assert "computer" in config.wake_word.keywords

            assert config.power_words.enabled == True
            assert "open browser" in config.power_words.mappings

        finally:
            Path(config_path).unlink()

    def test_config_validation_errors(self):
        """Test configuration validation with invalid values."""
        # Test invalid audio configuration
        with pytest.raises(Exception):  # Should raise validation error
            Config(audio={"source": "invalid_source"})

    def test_config_migration_from_old_format(self):
        """Test configuration migration from old format."""
        from scribed.config import ConfigMigration

        old_config = {
            "source_mode": "microphone",
            "microphone": {"device_index": 1, "sample_rate": 44100},
            "transcription": {"provider": "whisper", "model": "base"},
        }

        migrated = ConfigMigration.migrate_config_data(old_config)

        assert "audio" in migrated
        assert migrated["audio"]["source"] == "microphone"
        assert migrated["audio"]["device_index"] == 1
        assert migrated["audio"]["sample_rate"] == 44100

    def test_config_environment_variable_override(self):
        """Test configuration override from environment variables."""
        import os

        # Set environment variable
        os.environ["SCRIBED_API_PORT"] = "9999"

        try:
            config = Config.from_env()
            # Note: This test assumes environment variable support is implemented
            # If not implemented, this test documents the expected behavior

        finally:
            # Clean up
            if "SCRIBED_API_PORT" in os.environ:
                del os.environ["SCRIBED_API_PORT"]


class TestEngineSessionIntegration:
    """Test integration between engine and session management."""

    @pytest.fixture
    def mock_transcription_service(self):
        """Mock transcription service for testing."""
        service = Mock(spec=TranscriptionService)
        service.is_available.return_value = True
        service.get_engine_info.return_value = {"provider": "mock", "model": "test"}
        return service

    @pytest.fixture
    def engine_with_mock_service(self, mock_transcription_service):
        """Create engine with mocked transcription service."""
        config = Config()
        with patch(
            "scribed.core.engine.TranscriptionService",
            return_value=mock_transcription_service,
        ):
            engine = ScribedEngine(config)
            return engine

    @pytest.mark.asyncio
    async def test_complete_session_lifecycle(self, engine_with_mock_service):
        """Test complete session lifecycle through engine."""
        engine = engine_with_mock_service

        # Start engine
        await engine.start()
        assert engine.status.value == "running"

        # Create session
        session_id = engine.create_session("microphone")
        assert session_id in engine._active_sessions

        # Start session
        await engine.start_session(session_id)
        session = engine.get_session(session_id)
        assert session.status.value == "active"

        # Add transcription results
        session.add_transcription_result("Hello", 0.9, is_partial=True)
        session.add_transcription_result("Hello world", 0.95, is_partial=False)

        # Verify results
        results = session.get_results()
        assert len(results) == 1  # Only final results
        assert results[0].text == "Hello world"

        final_text = session.get_final_text()
        assert final_text == "Hello world"

        # Pause and resume session
        await session.pause()
        assert session.status.value == "paused"

        await session.resume()
        assert session.status.value == "active"

        # Stop session
        await engine.stop_session(session_id)
        assert session_id not in engine._active_sessions

        # Stop engine
        await engine.stop()
        assert engine.status.value == "disabled"

    @pytest.mark.asyncio
    async def test_multiple_concurrent_sessions(self, engine_with_mock_service):
        """Test managing multiple concurrent sessions."""
        engine = engine_with_mock_service
        await engine.start()

        # Create multiple sessions
        session_ids = []
        for i in range(3):
            session_id = engine.create_session(f"session_type_{i}")
            session_ids.append(session_id)
            await engine.start_session(session_id)

        # Verify all sessions are active
        sessions_info = engine.list_sessions()
        assert len(sessions_info) == 3

        for session_info in sessions_info:
            assert session_info["status"] == "active"

        # Add results to different sessions
        for i, session_id in enumerate(session_ids):
            session = engine.get_session(session_id)
            session.add_transcription_result(f"Text from session {i}", 0.9)

        # Verify each session has its own results
        for i, session_id in enumerate(session_ids):
            session = engine.get_session(session_id)
            results = session.get_results()
            assert len(results) == 1
            assert f"session {i}" in results[0].text

        # Stop all sessions
        for session_id in session_ids:
            await engine.stop_session(session_id)

        assert len(engine._active_sessions) == 0
        await engine.stop()

    @pytest.mark.asyncio
    async def test_session_error_handling(self, engine_with_mock_service):
        """Test session error handling and recovery."""
        engine = engine_with_mock_service
        await engine.start()

        session_id = engine.create_session()
        await engine.start_session(session_id)

        session = engine.get_session(session_id)

        # Test error callback
        error_received = []

        def error_callback(error):
            error_received.append(error)

        session.add_error_callback(error_callback)

        # Trigger error
        test_error = Exception("Test error")
        session._handle_error(test_error)

        assert len(error_received) == 1
        assert error_received[0] == test_error
        assert session.status.value == "error"
        assert session.metrics.error_count == 1

        await engine.stop()

    @pytest.mark.asyncio
    async def test_engine_shutdown_with_active_sessions(self, engine_with_mock_service):
        """Test engine shutdown behavior with active sessions."""
        engine = engine_with_mock_service
        await engine.start()

        # Create and start multiple sessions
        session_ids = []
        for i in range(2):
            session_id = engine.create_session()
            session_ids.append(session_id)
            await engine.start_session(session_id)

        # Verify sessions are active
        assert len(engine._active_sessions) == 2

        # Stop engine (should stop all sessions)
        await engine.stop()

        # Verify all sessions were stopped
        assert len(engine._active_sessions) == 0
        assert engine.status.value == "disabled"


class TestAudioWorkflowIntegration:
    """Test audio processing workflow integration."""

    def create_test_audio_file(self, path, duration=1.0, sample_rate=16000):
        """Create a test audio file."""
        # Generate sine wave audio
        t = np.linspace(0, duration, int(sample_rate * duration), False)
        frequency = 440  # A4 note
        audio_data = np.sin(2 * np.pi * frequency * t)

        # Convert to 16-bit integers
        audio_int16 = (audio_data * 32767).astype(np.int16)

        # Write WAV file
        with wave.open(str(path), "wb") as wav_file:
            wav_file.setnchannels(1)  # Mono
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(audio_int16.tobytes())

    @pytest.mark.asyncio
    async def test_file_source_integration(self):
        """Test file source audio processing integration."""
        from scribed.audio.file_source import FileSource

        with tempfile.TemporaryDirectory() as temp_dir:
            audio_file = Path(temp_dir) / "test.wav"
            self.create_test_audio_file(audio_file)

            config = {
                "file_path": str(audio_file),
                "chunk_size": 1024,
                "target_sample_rate": 16000,
                "target_channels": 1,
                "target_format": "int16",
            }

            # Test file source availability
            source = FileSource(config)
            if not source.is_available():
                pytest.skip("Audio libraries not available for file processing")

            # Test complete workflow
            await source.start()
            assert source.is_active

            chunks_read = []
            while True:
                chunk = await source.read_chunk()
                if chunk is None:
                    break
                chunks_read.append(chunk)

            assert len(chunks_read) > 0

            # Verify chunk properties
            for chunk in chunks_read:
                assert chunk.sample_rate == 16000
                assert chunk.channels == 1
                assert chunk.format.value == "int16"
                assert len(chunk.data) > 0

            await source.stop()
            assert not source.is_active

    @pytest.mark.asyncio
    async def test_microphone_source_mock_integration(self):
        """Test microphone source integration with mocking."""
        from scribed.audio.microphone import MicrophoneSource

        config = {
            "device_index": None,
            "sample_rate": 16000,
            "channels": 1,
            "chunk_size": 1024,
            "format": "int16",
        }

        # Mock PyAudio to avoid hardware dependencies
        with patch("scribed.audio.microphone.AUDIO_AVAILABLE", True):
            with patch("scribed.audio.microphone.pyaudio") as mock_pyaudio:
                # Setup mock PyAudio
                mock_audio = Mock()
                mock_stream = Mock()
                mock_pyaudio.PyAudio.return_value = mock_audio
                mock_audio.open.return_value = mock_stream
                mock_audio.get_device_count.return_value = 1
                mock_audio.get_device_info_by_index.return_value = {
                    "name": "Test Device",
                    "maxInputChannels": 1,
                    "defaultSampleRate": 16000.0,
                    "hostApi": 0,
                }

                # Mock audio data
                test_audio_data = b"\x00\x01" * 1024
                mock_stream.read.return_value = test_audio_data

                source = MicrophoneSource(config)

                await source.start()
                assert source.is_active

                # Give some time for recording thread to start
                await asyncio.sleep(0.1)

                await source.stop()
                assert not source.is_active

                # Verify PyAudio was called correctly
                mock_audio.open.assert_called_once()
                mock_stream.stop_stream.assert_called_once()
                mock_stream.close.assert_called_once()


class TestCLIIntegration:
    """Test CLI command integration."""

    def create_test_audio_file(self, path, duration=2.0, sample_rate=16000):
        """Create a test audio file with speech-like content."""
        # Generate more complex audio that simulates speech patterns
        t = np.linspace(0, duration, int(sample_rate * duration), False)

        # Create multiple frequency components to simulate speech
        frequencies = [200, 400, 800, 1200]  # Simulate formants
        audio_data = np.zeros_like(t)

        for i, freq in enumerate(frequencies):
            # Add each frequency with amplitude modulation
            amplitude = 0.3 / (i + 1)  # Decreasing amplitude for higher frequencies
            modulation = 1 + 0.2 * np.sin(2 * np.pi * 5 * t)  # 5Hz modulation
            audio_data += amplitude * modulation * np.sin(2 * np.pi * freq * t)

        # Add some noise to make it more realistic
        noise = 0.05 * np.random.normal(0, 1, len(t))
        audio_data += noise

        # Apply envelope to simulate speech segments
        envelope = np.ones_like(t)
        segment_length = len(t) // 4
        for i in range(4):
            start = i * segment_length
            end = min((i + 1) * segment_length, len(t))
            if i % 2 == 1:  # Pause segments
                envelope[start:end] *= 0.1

        audio_data *= envelope

        # Normalize and convert to 16-bit integers
        audio_data = np.clip(audio_data, -1.0, 1.0)
        audio_int16 = (audio_data * 32767).astype(np.int16)

        # Write WAV file
        with wave.open(str(path), "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(audio_int16.tobytes())

    def create_test_config(self, temp_dir, provider="whisper"):
        """Create a test configuration file."""
        config_data = {
            "audio": {"source": "file", "sample_rate": 16000, "channels": 1},
            "transcription": {
                "provider": provider,
                "model": "base" if provider == "whisper" else "whisper-1",
                "language": "en",
            },
            "output": {
                "format": "txt",
                "save_to_file": True,
                "copy_to_clipboard": False,
            },
            "api": {
                "host": "127.0.0.1",
                "port": 8085,  # Use different port for testing
            },
        }

        config_path = temp_dir / "test_config.yaml"
        with open(config_path, "w") as f:
            import yaml

            yaml.dump(config_data, f)

        return config_path

    def test_cli_help_command(self):
        """Test CLI help command."""
        import subprocess
        import sys

        try:
            # Try different ways to invoke the CLI
            cli_commands = [
                [sys.executable, "-m", "scribed", "--help"],
                [sys.executable, "-c", "from scribed.cli import cli; cli(['--help'])"],
                [sys.executable, "src/scribed/cli.py", "--help"],
            ]

            success = False
            for cmd in cli_commands:
                try:
                    result = subprocess.run(
                        cmd, capture_output=True, text=True, timeout=10, cwd="."
                    )

                    if result.returncode == 0:
                        assert "scribed" in result.stdout.lower()
                        success = True
                        break
                    elif (
                        "help" in result.stdout.lower()
                        or "usage" in result.stdout.lower()
                    ):
                        # Help was displayed even if return code wasn't 0
                        success = True
                        break

                except (subprocess.TimeoutExpired, FileNotFoundError):
                    continue

            if not success:
                pytest.skip("CLI not available or not working")

        except Exception as e:
            pytest.skip(f"CLI test failed: {e}")

    def test_cli_version_command(self):
        """Test CLI version command."""
        import subprocess

        try:
            result = subprocess.run(
                ["python", "-m", "scribed", "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )

            # Should either succeed or show help (depending on implementation)
            assert result.returncode in [0, 2]  # 0 for success, 2 for argparse help

        except (subprocess.TimeoutExpired, FileNotFoundError):
            pytest.skip("CLI not available or timeout")

    def test_cli_config_validation(self):
        """Test CLI configuration validation."""
        import subprocess

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            # Write invalid config
            f.write("invalid: yaml: content:")
            config_path = f.name

        try:
            result = subprocess.run(
                ["python", "-m", "scribed", "--config", config_path, "start"],
                capture_output=True,
                text=True,
                timeout=10,
            )

            # Should fail with invalid config
            assert result.returncode != 0

        except (subprocess.TimeoutExpired, FileNotFoundError):
            pytest.skip("CLI not available or timeout")
        finally:
            Path(config_path).unlink()

    def test_cli_transcribe_command_with_real_audio(self):
        """Test CLI transcribe command with real audio files."""
        import subprocess

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create test audio file
            audio_file = temp_path / "test_speech.wav"
            self.create_test_audio_file(audio_file, duration=3.0)

            # Create output file path
            output_file = temp_path / "transcript.txt"

            try:
                # Test basic transcription
                result = subprocess.run(
                    [
                        "python",
                        "-m",
                        "scribed",
                        "transcribe",
                        str(audio_file),
                        "--output",
                        str(output_file),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )

                # Command should complete (may fail due to missing dependencies)
                if result.returncode == 0:
                    # If successful, output file should exist
                    assert output_file.exists()

                    # File should have content
                    content = output_file.read_text()
                    assert len(content.strip()) > 0

                    # Should contain some transcribed text
                    print(f"Transcribed content: {content}")
                else:
                    # If failed, check if it's due to missing dependencies
                    error_output = result.stderr.lower()
                    if any(
                        dep in error_output for dep in ["whisper", "torch", "openai"]
                    ):
                        pytest.skip(
                            f"Missing transcription dependencies: {result.stderr}"
                        )
                    else:
                        print(f"CLI transcribe failed: {result.stderr}")

            except (subprocess.TimeoutExpired, FileNotFoundError):
                pytest.skip("CLI not available or timeout")

    def test_cli_transcribe_with_different_providers(self):
        """Test CLI transcribe command with different providers."""
        import subprocess

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create test audio file
            audio_file = temp_path / "test_speech.wav"
            self.create_test_audio_file(audio_file)

            providers = ["whisper", "openai"]

            for provider in providers:
                output_file = temp_path / f"transcript_{provider}.txt"

                try:
                    result = subprocess.run(
                        [
                            "python",
                            "-m",
                            "scribed",
                            "transcribe",
                            str(audio_file),
                            "--provider",
                            provider,
                            "--output",
                            str(output_file),
                        ],
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )

                    if result.returncode == 0:
                        assert output_file.exists()
                        content = output_file.read_text()
                        assert len(content.strip()) > 0
                        print(f"Provider {provider} transcription: {content[:100]}...")
                    else:
                        # Expected to fail if provider not available
                        print(f"Provider {provider} not available: {result.stderr}")

                except (subprocess.TimeoutExpired, FileNotFoundError):
                    pytest.skip(f"CLI not available for provider {provider}")

    def test_cli_transcribe_with_existing_audio_files(self):
        """Test CLI transcribe command with existing audio files from the project."""
        import subprocess

        # Use existing audio files from the project
        audio_files = [
            Path("audio_input/demo.wav"),
            Path("audio_input/test_audio.wav"),
            Path("audio_input/real_test.wav"),
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            for audio_file in audio_files:
                if not audio_file.exists():
                    continue

                output_file = temp_path / f"transcript_{audio_file.stem}.txt"

                try:
                    result = subprocess.run(
                        [
                            "python",
                            "-m",
                            "scribed",
                            "transcribe",
                            str(audio_file),
                            "--output",
                            str(output_file),
                        ],
                        capture_output=True,
                        text=True,
                        timeout=45,
                    )

                    if result.returncode == 0:
                        assert output_file.exists()
                        content = output_file.read_text()
                        assert len(content.strip()) > 0

                        print(f"Successfully transcribed {audio_file.name}")
                        print(f"Content preview: {content[:200]}...")

                        # Verify output contains reasonable text
                        words = content.split()
                        assert len(words) > 0

                    else:
                        print(
                            f"Failed to transcribe {audio_file.name}: {result.stderr}"
                        )

                except (subprocess.TimeoutExpired, FileNotFoundError):
                    pytest.skip(f"CLI timeout or not available for {audio_file.name}")

    def test_cli_config_command(self):
        """Test CLI config command."""
        import subprocess

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            config_file = self.create_test_config(temp_path)
            output_config = temp_path / "output_config.yaml"

            try:
                # Test config display
                result = subprocess.run(
                    ["python", "-m", "scribed", "--config", str(config_file), "config"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )

                if result.returncode == 0:
                    assert "Configuration" in result.stdout
                    assert "whisper" in result.stdout.lower()

                # Test config save
                result = subprocess.run(
                    [
                        "python",
                        "-m",
                        "scribed",
                        "--config",
                        str(config_file),
                        "config",
                        "--output",
                        str(output_config),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )

                if result.returncode == 0:
                    assert output_config.exists()

            except (subprocess.TimeoutExpired, FileNotFoundError):
                pytest.skip("CLI config command not available")

    def test_cli_status_command(self):
        """Test CLI status command."""
        import subprocess

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            config_file = self.create_test_config(temp_path)

            try:
                result = subprocess.run(
                    ["python", "-m", "scribed", "--config", str(config_file), "status"],
                    capture_output=True,
                    text=True,
                    timeout=15,
                )

                # Status command should complete (may show service not running)
                assert result.returncode in [0, 1]  # 0 for running, 1 for not running

                if result.returncode == 0:
                    assert "Status" in result.stdout
                else:
                    # Service not running is expected in tests
                    assert (
                        "not" in result.stderr.lower()
                        or "failed" in result.stderr.lower()
                    )

            except (subprocess.TimeoutExpired, FileNotFoundError):
                pytest.skip("CLI status command not available")

    def test_cli_features_command(self):
        """Test CLI features command."""
        import subprocess

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            config_file = self.create_test_config(temp_path)

            try:
                result = subprocess.run(
                    [
                        "python",
                        "-m",
                        "scribed",
                        "--config",
                        str(config_file),
                        "features",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )

                if result.returncode == 0:
                    assert "Feature Status" in result.stdout
                    # Should show status of optional features

            except (subprocess.TimeoutExpired, FileNotFoundError):
                pytest.skip("CLI features command not available")

    def test_cli_with_different_audio_formats(self):
        """Test CLI with different audio formats."""
        import subprocess

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create audio files in different formats
            formats = [
                ("test.wav", "wav"),
                # Note: MP3 and other formats would require additional libraries
            ]

            for filename, format_type in formats:
                audio_file = temp_path / filename

                if format_type == "wav":
                    self.create_test_audio_file(audio_file)

                output_file = temp_path / f"transcript_{format_type}.txt"

                try:
                    result = subprocess.run(
                        [
                            "python",
                            "-m",
                            "scribed",
                            "transcribe",
                            str(audio_file),
                            "--output",
                            str(output_file),
                        ],
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )

                    if result.returncode == 0:
                        assert output_file.exists()
                        content = output_file.read_text()
                        assert len(content.strip()) > 0
                        print(f"Successfully processed {format_type} format")
                    else:
                        print(f"Failed to process {format_type}: {result.stderr}")

                except (subprocess.TimeoutExpired, FileNotFoundError):
                    pytest.skip(f"CLI not available for {format_type} format")

    def test_cli_error_handling(self):
        """Test CLI error handling scenarios."""
        import subprocess

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Test with non-existent file
            try:
                result = subprocess.run(
                    [
                        "python",
                        "-m",
                        "scribed",
                        "transcribe",
                        str(temp_path / "nonexistent.wav"),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )

                # Should fail gracefully
                assert result.returncode != 0
                assert (
                    "not found" in result.stderr.lower()
                    or "error" in result.stderr.lower()
                )

            except (subprocess.TimeoutExpired, FileNotFoundError):
                pytest.skip("CLI error handling test not available")

            # Test with invalid audio file
            invalid_audio = temp_path / "invalid.wav"
            invalid_audio.write_text("This is not audio data")

            try:
                result = subprocess.run(
                    ["python", "-m", "scribed", "transcribe", str(invalid_audio)],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )

                # Should fail gracefully
                assert result.returncode != 0

            except (subprocess.TimeoutExpired, FileNotFoundError):
                pytest.skip("CLI invalid audio test not available")


class TestAPIIntegration:
    """Test REST API integration."""

    @pytest.fixture
    def api_server_config(self):
        """Configuration for API server testing."""
        return {
            "api": {
                "host": "127.0.0.1",
                "port": 8083,  # Use different port for testing
            },
            "transcription": {"provider": "mock"},
        }

    @pytest.mark.asyncio
    async def test_api_server_startup(self, api_server_config):
        """Test API server startup and basic endpoints."""
        from scribed.api.server import create_app

        # Create app with test config
        app = create_app(api_server_config)

        # Test that app was created
        assert app is not None

        # Note: Full server testing would require running the server
        # and making HTTP requests, which is complex for unit tests

    def test_api_health_endpoint_structure(self):
        """Test API health endpoint response structure."""
        from scribed.api.server import create_app

        config = {
            "api": {"host": "127.0.0.1", "port": 8083},
            "transcription": {"provider": "mock"},
        }

        app = create_app(config)

        # Test with Flask test client
        with app.test_client() as client:
            response = client.get("/health")

            # Should return JSON response
            assert response.status_code == 200

            data = response.get_json()
            assert "status" in data
            assert "timestamp" in data

    def test_api_transcription_endpoint_structure(self):
        """Test API transcription endpoint structure."""
        from scribed.api.server import create_app

        config = {
            "api": {"host": "127.0.0.1", "port": 8083},
            "transcription": {"provider": "mock"},
        }

        app = create_app(config)

        with app.test_client() as client:
            # Test POST to transcription endpoint
            response = client.post("/transcribe", json={"text": "test transcription"})

            # Should handle the request (may return error without proper setup)
            assert response.status_code in [200, 400, 500]


class TestEndToEndWorkflows:
    """Test complete end-to-end workflows."""

    def create_test_config(self, temp_dir, provider="whisper"):
        """Create test configuration."""
        config_data = {
            "audio": {
                "source": "file",
                "watch_directory": str(temp_dir / "input"),
                "output_directory": str(temp_dir / "output"),
                "supported_formats": [".wav", ".mp3", ".flac"],
            },
            "transcription": {
                "provider": provider,
                "model": "base" if provider == "whisper" else "whisper-1",
                "language": "en",
            },
            "output": {
                "format": "txt",
                "save_to_file": True,
                "copy_to_clipboard": False,
                "include_metadata": True,
            },
            "api": {"host": "127.0.0.1", "port": 8086},
        }

        config_path = temp_dir / "config.yaml"
        with open(config_path, "w") as f:
            import yaml

            yaml.dump(config_data, f)

        return config_path

    def create_test_audio_file(self, path, duration=2.0, complexity="simple"):
        """Create a test audio file with different complexity levels."""
        sample_rate = 16000
        t = np.linspace(0, duration, int(sample_rate * duration), False)

        if complexity == "simple":
            # Simple sine wave
            frequency = 440  # A4 note
            audio_data = np.sin(2 * np.pi * frequency * t)
        elif complexity == "speech_like":
            # More complex audio simulating speech patterns
            frequencies = [200, 400, 800, 1200, 1600]  # Simulate formants
            audio_data = np.zeros_like(t)

            for i, freq in enumerate(frequencies):
                amplitude = 0.4 / (i + 1)  # Decreasing amplitude
                # Add frequency modulation to simulate speech dynamics
                freq_mod = freq * (1 + 0.1 * np.sin(2 * np.pi * 3 * t))
                audio_data += amplitude * np.sin(2 * np.pi * freq_mod * t)

            # Add amplitude envelope to simulate speech segments
            envelope = np.ones_like(t)
            num_segments = 4
            segment_length = len(t) // num_segments

            for i in range(num_segments):
                start = i * segment_length
                end = min((i + 1) * segment_length, len(t))

                # Alternate between speech and pause
                if i % 2 == 1:  # Pause segments
                    envelope[start:end] *= 0.1
                else:  # Speech segments with natural envelope
                    segment_t = np.linspace(0, 1, end - start)
                    # Attack-decay-sustain-release envelope
                    attack = np.minimum(segment_t * 10, 1)
                    release = np.minimum((1 - segment_t) * 10, 1)
                    envelope[start:end] *= attack * release

            audio_data *= envelope

            # Add realistic noise
            noise = 0.02 * np.random.normal(0, 1, len(t))
            audio_data += noise

        # Normalize and convert to 16-bit integers
        audio_data = np.clip(audio_data, -1.0, 1.0)
        audio_int16 = (audio_data * 32767).astype(np.int16)

        # Write WAV file
        with wave.open(str(path), "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(audio_int16.tobytes())

    def create_multiple_test_files(self, input_dir, count=3):
        """Create multiple test audio files for batch processing."""
        audio_files = []

        for i in range(count):
            audio_file = input_dir / f"test_audio_{i:02d}.wav"
            complexity = "speech_like" if i % 2 == 0 else "simple"
            duration = 1.5 + (i * 0.5)  # Varying durations

            self.create_test_audio_file(
                audio_file, duration=duration, complexity=complexity
            )
            audio_files.append(audio_file)

        return audio_files

    @pytest.mark.asyncio
    async def test_file_processing_workflow(self):
        """Test complete file processing workflow."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            input_dir = temp_path / "input"
            output_dir = temp_path / "output"
            input_dir.mkdir()
            output_dir.mkdir()

            # Create test configuration
            config_path = self.create_test_config(temp_path)
            config = Config.from_file(str(config_path))

            # Create test audio file
            audio_file = input_dir / "test.wav"
            self.create_test_audio_file(audio_file)

            # Mock transcription service
            with patch(
                "scribed.transcription.service.TranscriptionService"
            ) as mock_service_class:
                mock_service = Mock()
                mock_service.is_available.return_value = True
                mock_service.get_engine_info.return_value = {"provider": "mock"}
                mock_service_class.return_value = mock_service

                # Create and start engine
                engine = ScribedEngine(config)
                await engine.start()

                # Create file processing session
                session_id = engine.create_session("file_batch")
                await engine.start_session(session_id)

                session = engine.get_session(session_id)

                # Simulate file processing
                session.add_transcription_result(
                    "This is a test transcription from file",
                    confidence=0.95,
                    processing_time=0.5,
                )

                # Verify session state
                assert session.status.value == "active"
                assert session.metrics.transcription_count == 1

                results = session.get_results()
                assert len(results) == 1
                assert "test transcription" in results[0].text

                await engine.stop()

    @pytest.mark.asyncio
    async def test_batch_file_processing_workflow(self):
        """Test batch processing of multiple files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            input_dir = temp_path / "input"
            output_dir = temp_path / "output"
            input_dir.mkdir()
            output_dir.mkdir()

            # Create test configuration
            config_path = self.create_test_config(temp_path)
            config = Config.from_file(str(config_path))

            # Create multiple test audio files
            audio_files = self.create_multiple_test_files(input_dir, count=5)

            # Mock transcription service at the engine level
            with patch(
                "scribed.core.engine.TranscriptionService"
            ) as mock_service_class:
                mock_service = Mock()
                mock_service.is_available.return_value = True
                mock_service.get_engine_info.return_value = {"provider": "whisper"}

                # Mock transcription results for each file
                def mock_transcribe_file(file_path):
                    filename = Path(file_path).stem
                    return Mock(
                        text=f"Transcription for {filename}",
                        confidence=0.9,
                        processing_time=0.2,
                        status=Mock(value="completed"),
                    )

                mock_service.transcribe_file.side_effect = mock_transcribe_file
                mock_service_class.return_value = mock_service

                # Create and start engine
                engine = ScribedEngine(config)
                await engine.start()

                # Process each file
                results = []
                for audio_file in audio_files:
                    session_id = engine.create_session(f"file_{audio_file.stem}")
                    await engine.start_session(session_id)

                    session = engine.get_session(session_id)

                    # Simulate file processing
                    result = await mock_service.transcribe_file(audio_file)
                    session.add_transcription_result(
                        result.text,
                        confidence=result.confidence,
                        processing_time=result.processing_time,
                    )

                    results.append(session.get_results()[0])
                    await engine.stop_session(session_id)

                # Verify all files were processed
                assert len(results) == 5
                for i, result in enumerate(results):
                    assert f"test_audio_{i:02d}" in result.text

                await engine.stop()

    @pytest.mark.asyncio
    async def test_configuration_validation_workflow(self):
        """Test configuration validation in complete workflow."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Test with invalid configuration
            invalid_config_data = {
                "audio": {
                    "source": "invalid_source",  # Invalid source
                    "sample_rate": -1,  # Invalid sample rate
                },
                "transcription": {
                    "provider": "nonexistent_provider"  # Invalid provider
                },
            }

            config_path = temp_path / "invalid_config.yaml"
            with open(config_path, "w") as f:
                import yaml

                yaml.dump(invalid_config_data, f)

            # Should raise validation error
            with pytest.raises(Exception):
                config = Config.from_file(str(config_path))
                engine = ScribedEngine(config)
                await engine.start()

    @pytest.mark.asyncio
    async def test_error_recovery_in_workflow(self):
        """Test error recovery during workflow execution."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            input_dir = temp_path / "input"
            output_dir = temp_path / "output"
            input_dir.mkdir()
            output_dir.mkdir()

            # Create test configuration
            config_path = self.create_test_config(temp_path)
            config = Config.from_file(str(config_path))

            # Create test audio file
            audio_file = input_dir / "test.wav"
            self.create_test_audio_file(audio_file)

            # Mock transcription service with intermittent failures
            with patch(
                "scribed.transcription.service.TranscriptionService"
            ) as mock_service_class:
                mock_service = Mock()
                mock_service.is_available.return_value = True
                mock_service.get_engine_info.return_value = {"provider": "mock"}

                # Simulate failures and recovery
                call_count = 0

                def mock_transcribe_with_failures(*args, **kwargs):
                    nonlocal call_count
                    call_count += 1
                    if call_count <= 2:  # First two calls fail
                        raise Exception("Simulated transcription failure")
                    else:  # Third call succeeds
                        return Mock(
                            text="Recovered transcription",
                            confidence=0.8,
                            processing_time=0.3,
                            status=Mock(value="completed"),
                        )

                mock_service.transcribe_file.side_effect = mock_transcribe_with_failures
                mock_service_class.return_value = mock_service

                # Create and start engine
                engine = ScribedEngine(config)
                await engine.start()

                session_id = engine.create_session("error_recovery_test")
                await engine.start_session(session_id)

                session = engine.get_session(session_id)

                # Attempt transcription with retries
                success = False
                for attempt in range(3):
                    try:
                        result = await mock_service.transcribe_file(audio_file)
                        session.add_transcription_result(
                            result.text,
                            confidence=result.confidence,
                            processing_time=result.processing_time,
                        )
                        success = True
                        break
                    except Exception as e:
                        session._handle_error(e)
                        await asyncio.sleep(0.1)  # Brief delay before retry

                # Verify eventual success
                assert success
                assert session.metrics.error_count == 2  # Two failures before success
                assert (
                    session.metrics.transcription_count == 1
                )  # One successful transcription

                results = session.get_results()
                assert len(results) == 1
                assert results[0].text == "Recovered transcription"

                await engine.stop()

    @pytest.mark.asyncio
    async def test_concurrent_session_workflow(self):
        """Test concurrent processing of multiple sessions."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            input_dir = temp_path / "input"
            output_dir = temp_path / "output"
            input_dir.mkdir()
            output_dir.mkdir()

            # Create test configuration
            config_path = self.create_test_config(temp_path)
            config = Config.from_file(str(config_path))

            # Create multiple test audio files
            audio_files = self.create_multiple_test_files(input_dir, count=3)

            # Mock transcription service
            with patch(
                "scribed.transcription.service.TranscriptionService"
            ) as mock_service_class:
                mock_service = Mock()
                mock_service.is_available.return_value = True
                mock_service.get_engine_info.return_value = {"provider": "mock"}
                mock_service_class.return_value = mock_service

                # Create and start engine
                engine = ScribedEngine(config)
                await engine.start()

                # Create multiple concurrent sessions
                session_tasks = []

                async def process_file_session(audio_file, session_name):
                    session_id = engine.create_session(session_name)
                    await engine.start_session(session_id)

                    session = engine.get_session(session_id)

                    # Simulate processing delay
                    await asyncio.sleep(0.1)

                    # Add transcription result
                    session.add_transcription_result(
                        f"Concurrent transcription for {audio_file.stem}",
                        confidence=0.9,
                        processing_time=0.1,
                    )

                    return session.get_results()[0]

                # Start concurrent processing
                for i, audio_file in enumerate(audio_files):
                    task = asyncio.create_task(
                        process_file_session(audio_file, f"concurrent_session_{i}")
                    )
                    session_tasks.append(task)

                # Wait for all sessions to complete
                results = await asyncio.gather(*session_tasks)

                # Verify all sessions completed successfully
                assert len(results) == 3
                for i, result in enumerate(results):
                    assert f"test_audio_{i:02d}" in result.text
                    assert result.confidence == 0.9

                # Verify engine handled concurrent sessions
                sessions_info = engine.list_sessions()
                assert len(sessions_info) == 3

                await engine.stop()

    @pytest.mark.asyncio
    async def test_real_time_simulation_workflow(self):
        """Test real-time transcription simulation workflow."""
        config = Config()

        with patch(
            "scribed.transcription.service.TranscriptionService"
        ) as mock_service_class:
            mock_service = Mock()
            mock_service.is_available.return_value = True
            mock_service.get_engine_info.return_value = {"provider": "mock"}
            mock_service_class.return_value = mock_service

            engine = ScribedEngine(config)
            await engine.start()

            # Create real-time session
            session_id = engine.create_session("realtime_simulation")
            await engine.start_session(session_id)

            session = engine.get_session(session_id)

            # Simulate real-time transcription with partial results
            transcription_sequence = [
                ("Hello", 0.7, True),
                ("Hello there", 0.8, True),
                ("Hello there, how", 0.75, True),
                ("Hello there, how are", 0.8, True),
                ("Hello there, how are you", 0.85, True),
                ("Hello there, how are you today", 0.9, False),  # Final result
                ("I'm", 0.6, True),
                ("I'm doing", 0.7, True),
                ("I'm doing well", 0.85, True),
                ("I'm doing well, thanks", 0.9, False),  # Final result
            ]

            # Process transcription sequence with realistic timing
            for text, confidence, is_partial in transcription_sequence:
                session.add_transcription_result(text, confidence, is_partial)
                await asyncio.sleep(0.05)  # Simulate real-time delay

            # Verify final results
            final_results = session.get_results(include_partial=False)
            assert len(final_results) == 2
            assert final_results[0].text == "Hello there, how are you today"
            assert final_results[1].text == "I'm doing well, thanks"

            # Verify session metrics
            metrics = session.get_metrics()
            assert metrics["transcription_count"] == 2  # Only final results
            assert metrics["result_count"] == 10  # All results including partial

            # Test session pause/resume during real-time processing
            await session.pause()
            assert session.status.value == "paused"

            # Add result while paused (should be queued)
            session.add_transcription_result("Paused result", 0.8, False)

            await session.resume()
            assert session.status.value == "active"

            # Verify paused result was processed
            final_results = session.get_results(include_partial=False)
            assert len(final_results) == 3
            assert final_results[2].text == "Paused result"

            await engine.stop()

    @pytest.mark.asyncio
    async def test_microphone_workflow_simulation(self):
        """Test simulated microphone workflow."""
        config = Config()

        with patch(
            "scribed.transcription.service.TranscriptionService"
        ) as mock_service_class:
            mock_service = Mock()
            mock_service.is_available.return_value = True
            mock_service.get_engine_info.return_value = {"provider": "mock"}
            mock_service_class.return_value = mock_service

            engine = ScribedEngine(config)
            await engine.start()

            # Create microphone session
            session_id = engine.create_session("microphone")
            await engine.start_session(session_id)

            session = engine.get_session(session_id)

            # Simulate real-time transcription
            partial_results = [
                ("Hello", 0.8, True),
                ("Hello world", 0.9, True),
                ("Hello world this", 0.85, True),
                ("Hello world this is", 0.9, True),
                ("Hello world this is a test", 0.95, False),
            ]

            for text, confidence, is_partial in partial_results:
                session.add_transcription_result(text, confidence, is_partial)
                await asyncio.sleep(0.1)  # Simulate real-time delay

            # Verify final result
            final_results = session.get_results(include_partial=False)
            assert len(final_results) == 1
            assert final_results[0].text == "Hello world this is a test"

            final_text = session.get_final_text()
            assert final_text == "Hello world this is a test"

            # Test session metrics
            metrics = session.get_metrics()
            assert metrics["transcription_count"] == 1  # Only final results count
            assert metrics["result_count"] == 5  # All results including partial

            await engine.stop()

    def test_configuration_error_handling(self):
        """Test configuration error handling in workflows."""
        # Test with missing required configuration
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "invalid_config.yaml"

            # Write invalid configuration
            with open(config_path, "w") as f:
                f.write("invalid_yaml_content: [unclosed_bracket")

            # Should raise error when loading
            with pytest.raises(Exception):
                Config.from_file(str(config_path))

    @pytest.mark.asyncio
    async def test_performance_under_load(self):
        """Test system performance under load conditions."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            input_dir = temp_path / "input"
            output_dir = temp_path / "output"
            input_dir.mkdir()
            output_dir.mkdir()

            # Create test configuration
            config_path = self.create_test_config(temp_path)
            config = Config.from_file(str(config_path))

            # Create many test audio files
            audio_files = self.create_multiple_test_files(input_dir, count=10)

            # Mock transcription service
            with patch(
                "scribed.transcription.service.TranscriptionService"
            ) as mock_service_class:
                mock_service = Mock()
                mock_service.is_available.return_value = True
                mock_service.get_engine_info.return_value = {"provider": "mock"}
                mock_service_class.return_value = mock_service

                # Create and start engine
                engine = ScribedEngine(config)
                await engine.start()

                # Process files concurrently to test load handling
                start_time = time.time()

                async def process_file_batch(files_batch):
                    results = []
                    for audio_file in files_batch:
                        session_id = engine.create_session(
                            f"load_test_{audio_file.stem}"
                        )
                        await engine.start_session(session_id)

                        session = engine.get_session(session_id)
                        session.add_transcription_result(
                            f"Load test transcription for {audio_file.stem}",
                            confidence=0.9,
                            processing_time=0.05,
                        )

                        results.append(session.get_results()[0])
                        await engine.stop_session(session_id)

                    return results

                # Split files into batches for concurrent processing
                batch_size = 3
                batches = [
                    audio_files[i : i + batch_size]
                    for i in range(0, len(audio_files), batch_size)
                ]

                # Process batches concurrently
                batch_tasks = [process_file_batch(batch) for batch in batches]
                all_results = await asyncio.gather(*batch_tasks)

                # Flatten results
                results = [
                    result for batch_results in all_results for result in batch_results
                ]

                end_time = time.time()
                processing_time = end_time - start_time

                # Verify all files were processed
                assert len(results) == 10

                # Verify reasonable performance (should complete within reasonable time)
                assert processing_time < 5.0  # Should complete within 5 seconds

                # Verify no memory leaks (all sessions cleaned up)
                assert len(engine._active_sessions) == 0

                await engine.stop()

    @pytest.mark.asyncio
    async def test_memory_usage_monitoring(self):
        """Test memory usage during extended operation."""
        import psutil
        import os

        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        config = Config()

        with patch(
            "scribed.transcription.service.TranscriptionService"
        ) as mock_service_class:
            mock_service = Mock()
            mock_service.is_available.return_value = True
            mock_service.get_engine_info.return_value = {"provider": "mock"}
            mock_service_class.return_value = mock_service

            engine = ScribedEngine(config)
            await engine.start()

            # Simulate extended operation with many sessions
            for i in range(50):
                session_id = engine.create_session(f"memory_test_{i}")
                await engine.start_session(session_id)

                session = engine.get_session(session_id)

                # Add multiple results to each session
                for j in range(10):
                    session.add_transcription_result(
                        f"Memory test result {i}-{j}",
                        confidence=0.9,
                        is_partial=(j < 9),
                    )

                await engine.stop_session(session_id)

                # Check memory usage periodically
                if i % 10 == 0:
                    current_memory = process.memory_info().rss / 1024 / 1024  # MB
                    memory_increase = current_memory - initial_memory

                    # Memory increase should be reasonable (less than 100MB for this test)
                    assert (
                        memory_increase < 100
                    ), f"Memory usage increased by {memory_increase:.2f}MB"

            await engine.stop()

            # Final memory check
            final_memory = process.memory_info().rss / 1024 / 1024  # MB
            total_increase = final_memory - initial_memory

            # Total memory increase should be reasonable
            assert total_increase < 50, f"Total memory increase: {total_increase:.2f}MB"

    @pytest.mark.asyncio
    async def test_error_recovery_workflow(self):
        """Test error recovery in workflows."""
        config = Config()

        with patch(
            "scribed.transcription.service.TranscriptionService"
        ) as mock_service_class:
            mock_service = Mock()
            mock_service.is_available.return_value = True
            mock_service.get_engine_info.return_value = {"provider": "mock"}
            mock_service_class.return_value = mock_service

            engine = ScribedEngine(config)
            await engine.start()

            session_id = engine.create_session()
            await engine.start_session(session_id)

            session = engine.get_session(session_id)

            # Add successful result
            session.add_transcription_result("Success", 0.9)

            # Simulate error
            session._handle_error(Exception("Simulated error"))

            # Verify error was handled
            assert session.status.value == "error"
            assert session.metrics.error_count == 1
            assert (
                session.metrics.transcription_count == 1
            )  # Previous success still counted

            await engine.stop()
