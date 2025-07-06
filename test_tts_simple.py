import pytest
import tempfile
import os
from pathlib import Path


def test_tts_fallback_works():
    """Test that audio generation works even when TTS libraries fail."""
    # Import after setting up environment
    from tests.test_integration import generate_wav, _generate_synthetic_wav

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
        test_path = temp_file.name

    try:
        # Test synthetic audio generation directly
        _generate_synthetic_wav("test audio", test_path)

        assert Path(test_path).exists()
        assert Path(test_path).stat().st_size > 0
        print(f"Synthetic audio size: {Path(test_path).stat().st_size} bytes")

        # Test the full generate_wav function
        Path(test_path).unlink()  # Remove previous file
        generate_wav("Hello world test", test_path)

        assert Path(test_path).exists()
        assert Path(test_path).stat().st_size > 0
        print(f"Generated audio size: {Path(test_path).stat().st_size} bytes")

    finally:
        # Clean up
        if Path(test_path).exists():
            Path(test_path).unlink()


if __name__ == "__main__":
    test_tts_fallback_works()
    print("✅ TTS fallback test passed!")
