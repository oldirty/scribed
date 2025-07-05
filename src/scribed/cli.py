"""Command-line interface for Scribed."""

import asyncio
import click
import sys
from pathlib import Path
from typing import Optional

from .config import Config
from .daemon import ScribedDaemon


@click.group()
@click.version_option(version="0.1.0", prog_name="scribed")
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True, path_type=Path),
    help="Path to configuration file",
)
@click.pass_context
def cli(ctx: click.Context, config: Optional[Path]) -> None:
    """Scribed - Audio Transcription Daemon.

    A powerful audio transcription service with wake word detection,
    voice commands, and batch processing capabilities.
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
    help="Run in daemon mode (background)",
)
@click.pass_context
def start(ctx: click.Context, daemon: bool) -> None:
    """Start the transcription daemon."""
    config: Config = ctx.obj["config"]

    if daemon:
        click.echo("Daemon mode not yet implemented. Running in foreground...")

    try:
        click.echo("Starting Scribed daemon...")
        scribed_daemon = ScribedDaemon(config)
        scribed_daemon.setup_signal_handlers()

        # Run the daemon
        asyncio.run(scribed_daemon.start())

    except KeyboardInterrupt:
        click.echo("\\nShutdown requested by user")
    except Exception as e:
        click.echo(f"Error starting daemon: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.pass_context
def stop(ctx: click.Context) -> None:
    """Stop the transcription daemon."""
    # TODO: Implement daemon stop via API call or PID file
    click.echo("Stop command not yet implemented")
    click.echo("Use Ctrl+C to stop the daemon for now")


@cli.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Check daemon status."""
    config: Config = ctx.obj["config"]

    try:
        import requests
        
        # Check daemon status first
        response = requests.get(f"http://{config.api.host}:{config.api.port}/status", timeout=5)
        if response.status_code == 200:
            status_data = response.json()
            click.echo(f"Status: {status_data['status']}")
            click.echo(f"Running: {status_data['running']}")
            click.echo(f"Mode: {status_data['config']['source_mode']}")
            click.echo(f"API Port: {status_data['config']['api_port']}")
        else:
            click.echo("Daemon is not responding", err=True)
    except ImportError:
        click.echo("requests library not available", err=True)
    except Exception as e:
        if "ConnectionError" in str(type(e)):
            click.echo("Daemon is not running", err=True)
        else:
            click.echo(f"Error checking status: {e}", err=True)


@cli.command()
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    help="Output file path",
)
@click.pass_context
def config_cmd(ctx: click.Context, output: Optional[Path]) -> None:
    """Manage daemon configuration."""
    config: Config = ctx.obj["config"]

    if output:
        config.to_file(str(output))
        click.echo(f"Configuration saved to: {output}")
    else:
        # Display current configuration
        click.echo("Current Configuration:")
        click.echo(f"  Source Mode: {config.source_mode}")
        click.echo(f"  Watch Directory: {config.file_watcher.watch_directory}")
        click.echo(f"  Output Directory: {config.file_watcher.output_directory}")
        click.echo(f"  API Host: {config.api.host}")
        click.echo(f"  API Port: {config.api.port}")
        click.echo(f"  Transcription Provider: {config.transcription.provider}")
        click.echo(f"  Output Format: {config.output.format}")


@cli.command()
@click.option(
    "--lines",
    "-n",
    default=50,
    help="Number of lines to show",
)
@click.pass_context
def logs(ctx: click.Context, lines: int) -> None:
    """View daemon logs."""
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
    """Transcribe an audio file directly (without daemon)."""
    import asyncio
    from scribed.transcription.service import TranscriptionService

    config: Config = ctx.obj["config"]

    # Override provider if specified
    if provider:
        config.transcription.provider = provider

    click.echo(f"Transcribing: {audio_file}")
    click.echo(f"Provider: {config.transcription.provider}")

    async def run_transcription():
        try:
            # Initialize transcription service
            service = TranscriptionService(config.transcription.model_dump())

            if not service.is_available():
                click.echo("Error: Transcription service not available", err=True)
                engine_info = service.get_engine_info()
                click.echo(f"Engine info: {engine_info}", err=True)
                return

            # Transcribe the file
            click.echo("Processing...")
            result = await service.transcribe_file(audio_file)

            if result.status.value == "completed":
                click.echo(
                    f"✓ Transcription completed in {result.processing_time:.2f}s"
                )

                # Determine output file
                if output:
                    output_file = output
                else:
                    output_file = audio_file.with_suffix(".txt")

                # Write transcription
                content = result.text
                if result.segments:
                    content += "\n\n## Segments\n"
                    for i, segment in enumerate(result.segments, 1):
                        start = (
                            f"{segment.start_time:.2f}s"
                            if segment.start_time
                            else "N/A"
                        )
                        end = f"{segment.end_time:.2f}s" if segment.end_time else "N/A"
                        content += f"{i}. [{start} - {end}] {segment.text}\n"

                with open(output_file, "w", encoding="utf-8") as f:
                    f.write(content)

                click.echo(f"Transcript saved to: {output_file}")

                # Show preview
                preview = (
                    result.text[:200] + "..." if len(result.text) > 200 else result.text
                )
                click.echo(f"\nPreview:\n{preview}")

            else:
                click.echo(f"✗ Transcription failed: {result.error}", err=True)

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
    """Record audio and transcribe directly to clipboard."""
    config: Config = ctx.obj["config"]

    if use_daemon:
        # Use daemon API
        try:
            import requests
            
            # Prepare request data
            request_data: dict = {
                "duration": duration
            }
            if provider:
                request_data["provider"] = provider

            click.echo(f"🎤 Recording for {duration} seconds via daemon...")
            
            # Make API request
            response = requests.post(
                f"http://{config.api.host}:{config.api.port}/record-to-clipboard",
                json=request_data,
                timeout=duration + 30  # Give extra time for processing
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
                        click.echo(f"⏱️  Processing time: {result['processing_time']:.2f}s")
                else:
                    click.echo(f"❌ Failed: {result.get('error', 'Unknown error')}", err=True)
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
                click.echo("❌ Cannot connect to daemon. Make sure it's running.", err=True)
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
    """Direct recording and transcription to clipboard (without daemon)."""
    import asyncio
    import tempfile
    from pathlib import Path
    from scribed.transcription.service import TranscriptionService
    from scribed.clipboard import set_clipboard_text, is_clipboard_available

    config: Config = ctx.obj["config"]

    # Check clipboard availability
    if not is_clipboard_available():
        click.echo("Error: Clipboard functionality not available", err=True)
        click.echo("On Linux, install xclip or xsel: sudo apt-get install xclip", err=True)
        return

    # Override provider if specified
    if provider:
        config.transcription.provider = provider

    click.echo(f"Recording for {duration} seconds...")
    click.echo(f"Provider: {config.transcription.provider}")
    click.echo("Press Ctrl+C to stop early")
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
                dtype=np.int16
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
                with wave.open(str(temp_path), 'wb') as wav_file:
                    wav_file.setnchannels(channels)
                    wav_file.setsampwidth(2)  # 16-bit
                    wav_file.setframerate(sample_rate)
                    wav_file.writeframes(audio_data.tobytes())

            try:
                # Initialize transcription service
                service = TranscriptionService(config.transcription.model_dump())

                if not service.is_available():
                    click.echo("Error: Transcription service not available", err=True)
                    engine_info = service.get_engine_info()
                    click.echo(f"Engine info: {engine_info}", err=True)
                    return

                # Transcribe the recording
                click.echo("🔄 Transcribing...")
                result = await service.transcribe_file(temp_path)

                if result.status.value == "completed":
                    # Copy to clipboard
                    if set_clipboard_text(result.text):
                        click.echo("✅ Transcription copied to clipboard!")
                        
                        if not silent:
                            # Show preview
                            preview = (
                                result.text[:200] + "..." 
                                if len(result.text) > 200 
                                else result.text
                            )
                            click.echo(f"\n📝 Transcribed text:\n{preview}")
                        
                        click.echo(f"⏱️  Processing time: {result.processing_time:.2f}s")
                    else:
                        click.echo("❌ Failed to copy to clipboard", err=True)
                        click.echo(f"Text: {result.text}")
                else:
                    click.echo(f"❌ Transcription failed: {result.error}", err=True)

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


# Backward compatibility alias
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
@click.pass_context
def transcribe_to_clipboard(
    ctx: click.Context,
    duration: int,
    provider: Optional[str],
    silent: bool,
) -> None:
    """Record audio and transcribe directly to clipboard (legacy command)."""
    click.echo("⚠️  Note: 'transcribe-to-clipboard' is deprecated. Use 'record-to-clipboard' instead.")
    # Call the new command function
    _record_to_clipboard_direct(ctx, duration, provider, silent)


def main() -> None:
    """Main entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()
