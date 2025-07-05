#!/usr/bin/env python
"""
Test script for Scribed CLI functionality.

This script allows testing the CLI without full installation.
"""

import sys
from pathlib import Path

# Add src to path for testing
sys.path.insert(0, str(Path(__file__).parent / "src"))

if __name__ == "__main__":
    from scribed.cli import main
    main()
