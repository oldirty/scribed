#!/usr/bin/env python3
"""Simple audio recording test for Scribed."""

import asyncio
import signal
import sys
from pathlib import Path

# Add the src directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))


class SimpleAudioTest:
    """Simple audio recording test."""

    def __init__(self):
        """Initialize the test."""
        self.running = False
        self.audio_count = 0

    def on_audio_data(self, audio_data: bytes) -> None:
        """Handle incoming audio data."""
        self.audio_count += 1

        # Show audio activity every 10 chunks
        if self.audio_count % 10 == 0:
            # Calculate simple volume level
            import struct
            try:
                # Convert bytes to 16-bit integers
                samples = struct.unpack(f'{len(audio_data)//2}h', audio_data)
                # Calculate RMS (root mean square) for volume
                rms = (sum(s*s for s in samples) / len(samples)) ** 0.5
                volume_bars = int(rms / 1000)  # Scale for display
                volume_display = "█" * min(volume_bars, 20)
                print(f"🎵 Audio: [{volume_display:<20}] RMS: {rms:6.0f}")
            except:
                print(f"🎵 Audio chunk {self.audio_count} received ({len(audio_data)} bytes)")

    async def test_audio_recording(self, duration: int = 10):
        """Test audio recording for a specified duration."""
        print(f"🎤 Testing audio recording for {duration} seconds...")
        print("📢 Speak into your microphone!")
        print("🔊 Audio levels will be displayed below:")
        print()

        try:
            from scribed.audio.microphone_input import MicrophoneInput

            config = {
                "device_index": None,  # Default device
                "sample_rate": 16000,
                "channels": 1,
                "chunk_size": 1024
            }

            mic = MicrophoneInput(config)

            # Start recording
            mic.start_recording(self.on_audio_data)

            print("🔴 Recording started...")
            self.running = True

            # Record for specified duration
            for i in range(duration):
                if not self.running:
                    break
                await asyncio.sleep(1)
                print(f"⏱️  {duration - i - 1}s remaining...")

            # Stop recording
            mic.stop_recording()
            print("\n🛑 Recording stopped.")
            print(f"📊 Total audio chunks received: {self.audio_count}")

            if self.audio_count > 0:
                print("✅ Audio recording is working correctly!")
            else:
                print("❌ No audio data received. Check your microphone.")

        except Exception as e:
            print(f"❌ Audio recording test failed: {e}")

    def stop(self):
        """Stop the test."""
        self.running = False


async def main():
    """Run the audio recording test."""
    print("🎵 Simple Audio Recording Test")
    print("=" * 40)

    test = SimpleAudioTest()

    # Set up signal handling
    def signal_handler(signum, frame):
        print(f"\n🛑 Received signal {signum}, stopping...")
        test.stop()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        await test.test_audio_recording(duration=10)
    except KeyboardInterrupt:
        print("\n🛑 Test interrupted by user")

    print("👋 Audio test completed!")


if __name__ == "__main__":
    asyncio.run(main())
