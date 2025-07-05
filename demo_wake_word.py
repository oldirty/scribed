#!/usr/bin/env python3
"""Demo script for wake word functionality with real audio."""

import asyncio
import logging
import sys
import signal
from pathlib import Path

# Add the src directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from scribed.config import Config
from scribed.realtime.transcription_service import RealTimeTranscriptionService


class WakeWordDemo:
    """Demo application for wake word functionality."""
    
    def __init__(self, config_path: str = "test_config.yaml"):
        """Initialize the demo."""
        self.config = Config.from_file(config_path)
        self.service = None
        self.running = False
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
    
    async def on_transcription(self, result: str, partial: bool) -> None:
        """Handle transcription results."""
        result_type = "PARTIAL" if partial else "FINAL"
        print(f"\n[{result_type}] Transcription: {result}")
        
        if not partial:
            print(f"✅ Final transcription saved!")
            print("-" * 50)
    
    def on_wake_word(self, keyword_index: int, keyword_name: str) -> None:
        """Handle wake word detection."""
        print(f"\n🎙️  Wake word detected: '{keyword_name}'")
        print("📝 Listening for speech... (say 'stop listening' or wait for silence)")
    
    async def on_state_change(self, old_state, new_state) -> None:
        """Handle state changes."""
        if new_state.value == "listening_for_wake_word":
            print(f"\n👂 Listening for wake word: {self.config.wake_word.keywords}")
        elif new_state.value == "active_transcription":
            print("🔴 Recording and transcribing...")
        elif new_state.value == "processing":
            print("⚙️  Processing final transcription...")
        elif new_state.value == "idle":
            print("💤 Service idle")
        elif new_state.value == "error":
            print("❌ Error occurred")
    
    async def start(self) -> None:
        """Start the demo."""
        try:
            print("🚀 Starting Wake Word Demo")
            print("=" * 50)
            
            # Check dependencies
            deps = RealTimeTranscriptionService.check_dependencies()
            if not all(deps.values()):
                print(f"❌ Missing dependencies: {deps}")
                return
            
            # Create service
            self.service = RealTimeTranscriptionService(
                wake_word_config=self.config.wake_word.model_dump(),
                microphone_config=self.config.microphone.model_dump(),
                transcription_config=self.config.transcription.model_dump()
            )
            
            # Set callbacks
            self.service.set_transcription_callback(self.on_transcription)
            self.service.set_wake_word_callback(self.on_wake_word)
            self.service.set_state_change_callback(self.on_state_change)
            
            # Start the service
            await self.service.start_service()
            
            print(f"🎯 Wake words: {self.config.wake_word.keywords}")
            print(f"🔇 Stop phrase: '{self.config.wake_word.stop_phrase}'")
            print(f"⏱️  Silence timeout: {self.config.wake_word.silence_timeout}s")
            print(f"📁 Output directory: {self.config.file_watcher.output_directory}")
            print("\n✨ Demo ready! Say your wake word to start transcription.")
            print("   Press Ctrl+C to exit.")
            
            self.running = True
            
            # Run until interrupted
            while self.running:
                await asyncio.sleep(1)
                
        except KeyboardInterrupt:
            print("\n🛑 Stopping demo...")
        except Exception as e:
            print(f"❌ Error: {e}")
            self.logger.exception("Demo error")
        finally:
            await self.stop()
    
    async def stop(self) -> None:
        """Stop the demo."""
        self.running = False
        if self.service:
            await self.service.stop_service()
        print("👋 Demo stopped. Thanks for trying wake word functionality!")
    
    def signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        print(f"\n🛑 Received signal {signum}")
        self.running = False


async def main():
    """Run the demo."""
    demo = WakeWordDemo()
    
    # Setup signal handling
    def signal_handler(signum, frame):
        demo.running = False
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    await demo.start()


if __name__ == "__main__":
    # Check config file exists
    config_file = "test_config.yaml"
    if not Path(config_file).exists():
        print(f"❌ Config file not found: {config_file}")
        print(f"💡 Copy config.yaml.example to {config_file} and add your Picovoice access key.")
        sys.exit(1)
    
    # Check for access key
    try:
        config = Config.from_file(config_file)
        if not config.wake_word.access_key:
            print("❌ Picovoice access key not configured!")
            print("💡 Get a free access key at: https://console.picovoice.ai/")
            print(f"💡 Add it to {config_file} under wake_word.access_key")
            sys.exit(1)
    except Exception as e:
        print(f"❌ Config error: {e}")
        sys.exit(1)
    
    # Run the demo
    asyncio.run(main())
