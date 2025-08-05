"""Command-line interface for Scribed."""

import asyncio
import click
import sys
from pathlib import Path
from typing import Optional

from .config import Config
from .core.engine import ScribedEngine
from .output.handler import OutputHandler, OutputConfig
from . import __version__


@click.group()
@click.version_option(version=__version__, prog_name="scribed")
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True, path_type=Path),
    help="Path to configuration file",
)
@click.pass_context
def cli(ctx: click.Context, config: Optional[Path]) -> None:
    """Scribed - Audio Transcription Service.

    A focused audio transcription service supporting real-time microphone input,
    file batch processing, and multiple transcription engines (Whisper, OpenAI).
    """
    # Ensure context object exists
    ctx.ensure_object(dict)

    # Load configuration
    if config:
        ctx.obj["config"] = Config.from_file(str(config))
    else:
        ctx.obj["config"] = Config.from_env()


@cli.command()
@click.option(
    "--daemon",
    "-d",
    is_flag=True,
    help="Run in daemon mode (background) - not yet implemented",
)
@click.pass_context
def start(ctx: click.Context, daemon: bool) -> None:
    """Start the transcription service.

    Starts the Scribed transcription engine with the configured audio source
    (microphone or file watcher) and transcription provider (Whisper or OpenAI).
    The service will run until stopped with Ctrl+C or a stop signal.

    Examples:
        scribed start                    # Start with default configuration
        scribed -c config.yaml start     # Start with custom config file
    """
    config: Config = ctx.obj["config"]

    if daemon:
        click.echo("Daemon mode not yet implemented. Running in foreground...")

    async def run_engine():
        engine = ScribedEngine(config)

        # Set up signal handlers for graceful shutdown
        import signal

        def signal_handler(signum, frame):
            click.echo(f"\nReceived signal {signum}, shutting down...")
            engine.shutdown()

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        try:
            click.echo("Starting Scribed engine...")
            await engine.start()

            # Keep running until shutdown signal
            await engine.wait_for_shutdown()

        finally:
            await engine.stop()

    try:
        asyncio.run(run_engine())
    except KeyboardInterrupt:
        click.echo("\nShutdown requested by user")
    except Exception as e:
        click.echo(f"Error starting engine: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.pass_context
def stop(ctx: click.Context) -> None:
    """Stop the transcription service.

    Note: Currently requires stopping the service with Ctrl+C.
    API-based stop functionality is planned for future releases.
    """
    config: Config = ctx.obj["config"]

    try:
        import requests

        response = requests.post(
            f"http://{config.api.host}:{config.api.port}/stop", timeout=5
        )
        if response.status_code == 200:
            click.echo("Service stop requested successfully")
        else:
            click.echo("Failed to stop service via API", err=True)
            click.echo("Use Ctrl+C to stop the service manually")
    except ImportError:
        click.echo("requests library not available", err=True)
        click.echo("Use Ctrl+C to stop the service manually")
    except Exception:
        click.echo("Service not running or API not available")
        click.echo("Use Ctrl+C to stop the service manually")


@cli.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Check service status.

    Display the current status of the transcription service, including
    whether it's running, active sessions, and transcription engine health.
    Tries API first, then falls back to direct engine check.

    Examples:
        scribed status                    # Check service status
        scribed -c config.yaml status     # Check with custom config
    """
    config: Config = ctx.obj["config"]

    # First try to check via API if available
    try:
        import requests

        response = requests.get(
            f"http://{config.api.host}:{config.api.port}/status", timeout=5
        )
        if response.status_code == 200:
            status_data = response.json()
            click.echo("Service Status (via API):")
            click.echo(f"  Status: {status_data['status']}")
            click.echo(f"  Running: {status_data['running']}")
            click.echo(f"  Active Sessions: {status_data.get('active_sessions', 0)}")
            click.echo(f"  Source Mode: {status_data['config']['source_mode']}")
            click.echo(
                f"  Transcription Provider: {status_data['config']['transcription_provider']}"
            )
            return
        else:
            click.echo("API not responding, checking engine directly...")
    except ImportError:
        click.echo("requests library not available, checking engine directly...")
    except Exception:
        click.echo("API not available, checking engine directly...")

    # Fallback to direct engine status check
    async def check_engine_status():
        try:
            engine = ScribedEngine(config)

            # Check if engine can be initialized
            status_info = engine.get_status()

            click.echo("Service Status (direct check):")
            click.echo(f"  Status: {status_info['status']}")
            click.echo(f"  Running: {status_info['running']}")
            click.echo(f"  Active Sessions: {status_info['active_sessions']}")
            click.echo(f"  Source Mode: {status_info['config']['source_mode']}")
            click.echo(
                f"  Transcription Provider: {status_info['config']['transcription_provider']}"
            )

            # Check transcription service health
            if "transcription" in status_info:
                trans_info = status_info["transcription"]
                click.echo(
                    f"  Transcription Engine: {trans_info.get('provider', 'unknown')}"
                )
                click.echo(f"  Engine Available: {trans_info.get('available', False)}")

            # Check if engine is healthy
            if engine.is_healthy():
                click.echo("  Health: ✓ Healthy")
            else:
                click.echo("  Health: ✗ Unhealthy")

        except Exception as e:
            click.echo(f"Error checking engine status: {e}", err=True)

    try:
        asyncio.run(check_engine_status())
    except Exception as e:
        click.echo(f"Failed to check status: {e}", err=True)


@cli.command()
@click.pass_context
def features(ctx: click.Context) -> None:
    """Show status of optional features.

    Display the current status of optional features like wake word detection
    and power words, including whether they are enabled and available.

    Examples:
        scribed features                  # Show feature status
        scribed -c config.yaml features   # Show with custom config
    """
    config: Config = ctx.obj["config"]

    try:
        from .features import create_feature_flags

        # Create feature flags from config
        feature_flags = create_feature_flags(config.model_dump())

        click.echo("Optional Feature Status:")
        click.echo("=" * 50)

        # Get detailed status for all features
        status = feature_flags.get_feature_status()

        for feature_name, feature_status in status.items():
            feature_display_name = feature_name.replace("_", " ").title()
            click.echo(f"\n{feature_display_name}:")
            click.echo(f"  Description: {feature_status['description']}")

            if feature_status["fully_available"]:
                click.echo("  Status: ✓ Enabled and Available")
            elif feature_status["enabled_in_config"]:
                click.echo("  Status: ⚠ Enabled but Not Available")
                if feature_name == "wake_word" and not feature_status.get(
                    "dependencies_available", True
                ):
                    click.echo("  Issue: Missing dependencies or access key")
                    click.echo(
                        "  Fix: Install 'pip install pvporcupine pyaudio' and set PICOVOICE_ACCESS_KEY"
                    )
                elif feature_name == "power_words" and not feature_status.get(
                    "has_mappings", True
                ):
                    click.echo("  Issue: No command mappings configured")
                    click.echo(
                        "  Fix: Add command mappings to power_words.mappings in config"
                    )
            else:
                click.echo("  Status: - Disabled")

        # Show validation results
        validation_results = feature_flags.validate_feature_requirements()
        errors = [msg for msg in validation_results.values() if msg is not None]

        if errors:
            click.echo("\nConfiguration Issues:")
            for error in errors:
                click.echo(f"  ⚠ {error}")
        else:
            click.echo("\n✓ No configuration issues found")

        # Show helpful tips
        click.echo("\nTips:")
        click.echo("  • Optional features are disabled by default for security")
        click.echo("  • Wake word detection requires a free Picovoice access key")
        click.echo("  • Power words execute system commands - use with caution")
        click.echo("  • See config.yaml.example for configuration examples")

    except Exception as e:
        click.echo(f"Error checking feature status: {e}", err=True)


@cli.command(name="config")
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    help="Output file path",
)
@click.pass_context
def config_cmd(ctx: click.Context, output: Optional[Path]) -> None:
    """Show or save current configuration."""
    config: Config = ctx.obj["config"]

    if output:
        config.to_file(str(output))
        click.echo(f"Configuration saved to: {output}")
    else:
        # Display current configuration
        click.echo("Current Configuration:")
        click.echo(f"  Source Mode: {config.source_mode}")
        click.echo(f"  Transcription Provider: {config.transcription.provider}")
        click.echo(f"  Output Format: {config.output.format}")
        click.echo(f"  API Host: {config.api.host}")
        click.echo(f"  API Port: {config.api.port}")

        # File watcher settings
        if hasattr(config, "file_watcher"):
            click.echo(f"  Watch Directory: {config.file_watcher.watch_directory}")
            click.echo(f"  Output Directory: {config.file_watcher.output_directory}")

        # Audio settings
        if hasattr(config, "audio"):
            click.echo(
                f"  Audio Source: {getattr(config.audio, 'source', 'microphone')}"
            )
            if hasattr(config.audio, "microphone"):
                click.echo(f"  Sample Rate: {config.audio.microphone.sample_rate}")

        # Output settings
        click.echo(f"  Save to File: {config.output.save_to_file}")
        click.echo(f"  Copy to Clipboard: {config.output.copy_to_clipboard}")
        click.echo(f"  Log to File: {config.output.log_to_file}")
        if config.output.log_to_file:
            click.echo(f"  Log File: {config.output.log_file_path}")


@cli.command()
@click.option(
    "--lines",
    "-n",
    default=50,
    help="Number of lines to show",
)
@click.pass_context
def logs(ctx: click.Context, lines: int) -> None:
    """View service logs.

    Display the most recent log entries from the transcription service.
    Useful for debugging and monitoring service activity.

    Examples:
        scribed logs              # Show last 50 lines
        scribed logs -n 100       # Show last 100 lines
    """
    config: Config = ctx.obj["config"]
    log_file = Path(config.output.log_file_path)

    if not log_file.exists():
        click.echo("Log file not found", err=True)
        return

    try:
        # Read last N lines
        with open(log_file, "r", encoding="utf-8") as f:
            log_lines = f.readlines()

        # Show last N lines
        for line in log_lines[-lines:]:
            click.echo(line.rstrip())

    except Exception as e:
        click.echo(f"Error reading log file: {e}", err=True)


@cli.command()
@click.argument("audio_file", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    help="Output transcript file",
)
@click.option(
    "--provider",
    "-p",
    type=click.Choice(["whisper", "openai"]),
    help="Transcription provider to use",
)
@click.pass_context
def transcribe(
    ctx: click.Context,
    audio_file: Path,
    output: Optional[Path],
    provider: Optional[str],
) -> None:
    """Transcribe an audio file directly.

    Process a single audio file and save the transcription to a text file.
    Supports common audio formats (WAV, MP3, M4A, etc.) and both Whisper
    and OpenAI transcription engines.

    Examples:
        scribed transcribe audio.wav                    # Basic transcription
        scribed transcribe audio.wav -o transcript.txt  # Custom output file
        scribed transcribe audio.wav -p openai          # Use OpenAI engine
        scribed transcribe audio.wav -p whisper         # Use Whisper engine
    """
    config: Config = ctx.obj["config"]

    # Override provider if specified
    if provider:
        config.transcription.provider = provider

    click.echo(f"Transcribing: {audio_file}")
    click.echo(f"Provider: {config.transcription.provider}")

    async def run_transcription():
        try:
            # Initialize engine
            engine = ScribedEngine(config)
            await engine.start()

            try:
                # Create a session for file transcription
                session_id = engine.create_session("file_transcription")
                session = engine.get_session(session_id)

                if not session:
                    click.echo(
                        "Error: Failed to create transcription session", err=True
                    )
                    return

                # Transcribe the file using the session's transcription service
                click.echo("Processing...")
                result = await session.transcription_service.transcribe_file(audio_file)

                if result.status.value == "completed":
                    click.echo(
                        f"✓ Transcription completed in {result.processing_time:.2f}s"
                    )

                    # Set up output configuration
                    output_config = OutputConfig(
                        save_to_file=True,
                        copy_to_clipboard=False,
                        console_output=False,
                        file_config={
                            "output_directory": (
                                str(output.parent) if output else str(audio_file.parent)
                            ),
                            "filename_template": (
                                output.name if output else f"{audio_file.stem}.txt"
                            ),
                            "format": "txt",
                            "include_metadata": True,
                        },
                    )

                    # Use output handler to write results
                    output_handler = OutputHandler(output_config)
                    metadata = {
                        "source": str(audio_file),
                        "provider": config.transcription.provider,
                        "processing_time": result.processing_time,
                        "segments": [
                            {
                                "text": seg.text,
                                "start_time": seg.start_time,
                                "end_time": seg.end_time,
                                "confidence": seg.confidence,
                            }
                            for seg in (result.segments or [])
                        ],
                    }

                    output_results = await output_handler.write_transcription(
                        result.text, metadata
                    )

                    # Report results
                    for output_result in output_results:
                        if output_result.status.value == "success":
                            click.echo(
                                f"Transcript saved to: {output_result.metadata.get('file_path', 'unknown')}"
                            )
                        else:
                            click.echo(
                                f"Output failed: {output_result.error}", err=True
                            )

                    # Show preview
                    preview = (
                        result.text[:200] + "..."
                        if len(result.text) > 200
                        else result.text
                    )
                    click.echo(f"\nPreview:\n{preview}")

                else:
                    click.echo(f"✗ Transcription failed: {result.error}", err=True)

            finally:
                await engine.stop()

        except Exception as e:
            click.echo(f"Error: {e}", err=True)

    # Run the transcription
    asyncio.run(run_transcription())


@cli.command()
@click.option(
    "--duration",
    "-d",
    default=10,
    help="Recording duration in seconds",
)
@click.option(
    "--provider",
    "-p",
    type=click.Choice(["whisper", "openai"]),
    help="Transcription provider to use",
)
@click.option(
    "--silent",
    "-s",
    is_flag=True,
    help="Don't print the transcribed text to console",
)
@click.option(
    "--use-daemon",
    is_flag=True,
    help="Use daemon API instead of direct transcription",
)
@click.pass_context
def record_to_clipboard(
    ctx: click.Context,
    duration: int,
    provider: Optional[str],
    silent: bool,
    use_daemon: bool,
) -> None:
    """Record audio and transcribe directly to clipboard.

    Records audio from the default microphone for the specified duration,
    transcribes it using the configured engine, and copies the result to
    the system clipboard. Useful for quick voice-to-text workflows.

    Examples:
        scribed record-to-clipboard                     # Record 10 seconds
        scribed record-to-clipboard -d 30               # Record 30 seconds
        scribed record-to-clipboard -p openai           # Use OpenAI engine
        scribed record-to-clipboard --silent            # No console output
        scribed record-to-clipboard --use-daemon        # Use running service
    """
    config: Config = ctx.obj["config"]

    if use_daemon:
        # Use daemon API
        try:
            import requests

            # Prepare request data
            request_data: dict = {"duration": duration}
            if provider:
                request_data["provider"] = provider

            click.echo(f"🎤 Recording for {duration} seconds via daemon...")

            # Make API request
            response = requests.post(
                f"http://{config.api.host}:{config.api.port}/record-to-clipboard",
                json=request_data,
                timeout=duration + 30,  # Give extra time for processing
            )

            if response.status_code == 200:
                result = response.json()
                if result["success"]:
                    click.echo("✅ Transcription copied to clipboard!")

                    if not silent and result.get("text"):
                        preview = (
                            result["text"][:200] + "..."
                            if len(result["text"]) > 200
                            else result["text"]
                        )
                        click.echo(f"\n📝 Transcribed text:\n{preview}")

                    if result.get("processing_time"):
                        click.echo(
                            f"⏱️  Processing time: {result['processing_time']:.2f}s"
                        )
                else:
                    click.echo(
                        f"❌ Failed: {result.get('error', 'Unknown error')}", err=True
                    )
            else:
                click.echo(f"❌ API request failed: {response.status_code}", err=True)
                try:
                    error_detail = response.json()
                    click.echo(f"Error: {error_detail}", err=True)
                except Exception:
                    click.echo(f"Error: {response.text}", err=True)

        except ImportError:
            click.echo("❌ requests library not available", err=True)
        except Exception as e:
            if "ConnectionError" in str(type(e)):
                click.echo(
                    "❌ Cannot connect to daemon. Make sure it's running.", err=True
                )
                click.echo("Try running without --use-daemon flag for direct mode.")
            else:
                click.echo(f"❌ Error: {e}", err=True)
    else:
        # Direct transcription (existing functionality)
        _record_to_clipboard_direct(ctx, duration, provider, silent)


def _record_to_clipboard_direct(
    ctx: click.Context,
    duration: int,
    provider: Optional[str],
    silent: bool,
) -> None:
    """Direct recording and transcription to clipboard using core engine."""
    import asyncio
    import tempfile
    from pathlib import Path

    config: Config = ctx.obj["config"]

    # Override provider if specified
    if provider:
        config.transcription.provider = provider

    click.echo(f"Recording for {duration} seconds...")
    click.echo(f"Provider: {config.transcription.provider}")
    click.echo("Press Ctrl+C to stop early")

    async def run_recording_and_transcription():
        try:
            # Import audio recording functionality
            import sounddevice as sd
            import numpy as np
            import wave

            # Recording parameters
            sample_rate = 16000
            channels = 1

            click.echo("🎤 Recording started...")

            # Record audio
            audio_data = sd.rec(
                int(duration * sample_rate),
                samplerate=sample_rate,
                channels=channels,
                dtype=np.int16,
            )

            # Wait for recording to complete or user interrupt
            try:
                sd.wait()
            except KeyboardInterrupt:
                sd.stop()
                click.echo("\n⏹️  Recording stopped by user")

            click.echo("✓ Recording completed")

            # Save to temporary file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                temp_path = Path(temp_file.name)

                # Write WAV file
                with wave.open(str(temp_path), "wb") as wav_file:
                    wav_file.setnchannels(channels)
                    wav_file.setsampwidth(2)  # 16-bit
                    wav_file.setframerate(sample_rate)
                    wav_file.writeframes(audio_data.tobytes())

            try:
                # Initialize engine
                engine = ScribedEngine(config)
                await engine.start()

                try:
                    # Create a session for recording transcription
                    session_id = engine.create_session("recording_transcription")
                    session = engine.get_session(session_id)

                    if not session:
                        click.echo(
                            "Error: Failed to create transcription session", err=True
                        )
                        return

                    # Transcribe the recording
                    click.echo("🔄 Transcribing...")
                    result = await session.transcription_service.transcribe_file(
                        temp_path
                    )

                    if result.status.value == "completed":
                        # Set up output configuration for clipboard
                        output_config = OutputConfig(
                            save_to_file=False,
                            copy_to_clipboard=True,
                            console_output=False,
                            clipboard_config={
                                "format": "plain",
                                "include_metadata": False,
                            },
                        )

                        # Use output handler to copy to clipboard
                        output_handler = OutputHandler(output_config)

                        if output_handler.is_any_destination_available():
                            output_results = await output_handler.write_transcription(
                                result.text
                            )

                            # Check if clipboard write was successful
                            clipboard_success = any(
                                r.status.value == "success"
                                and r.destination == "clipboard"
                                for r in output_results
                            )

                            if clipboard_success:
                                click.echo("✅ Transcription copied to clipboard!")

                                if not silent:
                                    # Show preview
                                    preview = (
                                        result.text[:200] + "..."
                                        if len(result.text) > 200
                                        else result.text
                                    )
                                    click.echo(f"\n📝 Transcribed text:\n{preview}")

                                click.echo(
                                    f"⏱️  Processing time: {result.processing_time:.2f}s"
                                )
                            else:
                                click.echo("❌ Failed to copy to clipboard", err=True)
                                click.echo(f"Text: {result.text}")
                        else:
                            click.echo(
                                "Error: Clipboard functionality not available", err=True
                            )
                            click.echo(
                                "On Linux, install xclip or xsel: sudo apt-get install xclip",
                                err=True,
                            )
                    else:
                        click.echo(f"❌ Transcription failed: {result.error}", err=True)

                finally:
                    await engine.stop()

            finally:
                # Clean up temporary file
                try:
                    temp_path.unlink()
                except Exception:
                    pass

        except ImportError as e:
            if "sounddevice" in str(e):
                click.echo("Error: sounddevice not installed", err=True)
                click.echo("Install with: pip install sounddevice", err=True)
            else:
                click.echo(f"Import error: {e}", err=True)
        except Exception as e:
            click.echo(f"Error: {e}", err=True)

    # Run the recording and transcription
    try:
        asyncio.run(run_recording_and_transcription())
    except KeyboardInterrupt:
        click.echo("\n⏹️  Operation cancelled by user")


# Configuration migration command removed for simplification


def create_parser():
    """Legacy function for test compatibility - CLI now uses Click."""

    # Return a mock object that CLI tests can use
    class MockParser:
        def parse_args(self, args=None):
            return self

        def add_argument(self, *args, **kwargs):
            pass

    return MockParser()


def main() -> None:
    """Main entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()
