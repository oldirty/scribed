# 🚀 Quick Start for Windows

Get Scribed running on Windows in just a few minutes!

## Prerequisites

- **Python 3.10+** installed from [python.org](https://python.org/downloads)
- **Make sure "Add Python to PATH" was checked** during Python installation
- **Download or clone the Scribed source code**

## Installation (Choose One Method)

### Method 1: Simple Installer (Recommended)

Open PowerShell or Command Prompt in the Scribed project folder and run:

**PowerShell:**
```powershell
.\install-windows-simple.ps1
```

**Command Prompt:**
```cmd
install-windows-simple.bat
```

This will:
✅ Check your Python installation  
✅ Create a virtual environment  
✅ Install Scribed in development mode  
✅ Install Whisper for local transcription  
✅ Test everything works  

### Method 2: One Command Install

For quick setup, run this single command:

```powershell
python -m venv venv && venv\Scripts\Activate.ps1 && python -m pip install --upgrade pip && python -m pip install -e .
```

### Method 3: Manual Step-by-Step

```powershell
# 1. Create virtual environment
python -m venv venv

# 2. Activate it
venv\Scripts\Activate.ps1

# 3. Update pip
python -m pip install --upgrade pip

# 4. Install Scribed
python -m pip install -e .

# 5. (Optional) Install Whisper for local transcription
python -m pip install "openai-whisper>=20231117" "faster-whisper>=0.10.0"

# 6. (Optional) Install TTS support for realistic test audio
# Note: This may fail on systems without eSpeak/eSpeak-ng - that's OK!
python -m pip install -e ".[tts]"
```

## First Time Setup

After installation, set up Scribed:

```powershell
# Activate virtual environment (if you used one)
venv\Scripts\Activate.ps1

# Create default config
scribed config -o config.yaml

# Edit config file if needed
notepad config.yaml

# Test it works
scribed --version
scribed --help
```

## Start Using Scribed

### File Mode (Process Audio Files)
```powershell
# Start watching a directory for audio files
scribed start

# Check status
scribed status

# Stop when done
scribed stop
```

### Real-time Mode (Live Audio)
```powershell
# Start real-time transcription
scribed start --mode realtime

# Or with wake word detection
scribed start --mode wake_word
```

## Troubleshooting

### "scribed command not found"
If `scribed` doesn't work, try `python -m scribed` instead:
```powershell
python -m scribed --version
python -m scribed start
```

### "Python not found"
1. Install Python from [python.org](https://python.org/downloads)
2. **Important:** Check "Add Python to PATH" during installation
3. Restart your terminal after installation

### Virtual Environment Issues
If you're using a virtual environment, make sure it's activated:
```powershell
venv\Scripts\Activate.ps1
```

You should see `(venv)` at the start of your command prompt.

### Permission Errors
- Use virtual environment method (avoids system-wide changes)
- Or run terminal as administrator for system-wide install

### TTS (Text-to-Speech) Errors
If you see "eSpeak or eSpeak-ng not installed" errors:
- This only affects test audio generation, not core Scribed functionality
- Tests will automatically fall back to synthetic audio
- To fix: Install eSpeak-ng from [GitHub releases](https://github.com/espeak-ng/espeak-ng/releases)
- Or simply ignore - it doesn't affect transcription features

## What's Next?

- 📖 Read the full [README.md](README.md) for advanced features
- 🔧 Check [WINDOWS_INSTALL.md](WINDOWS_INSTALL.md) for detailed Windows setup
- 🐛 Report issues at [GitHub Issues](https://github.com/oldirty/scribed/issues)

---

**Need Help?** Join our community or open an issue for support!
