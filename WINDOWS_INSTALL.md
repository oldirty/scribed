# Windows Installation Guide for Scribed

This guide provides multiple methods to install Scribed on Windows, from simple to advanced.

## 🚀 Quick Install (Recommended)

### Method 1: Python Package Manager (pip)

This is the easiest method if you have Python already installed:

```powershell
# Option A: Install globally (may require admin privileges)
pip install scribed

# Option B: Install for current user only (recommended)
pip install --user scribed

# Option C: Install with all optional features
pip install --user scribed[wake_word,whisper,openai]
```

After installation, you can run Scribed from anywhere:
```powershell
scribed --help
```

### Method 2: Virtual Environment (Safest)

This method isolates Scribed and prevents conflicts with other Python packages:

```powershell
# Create a virtual environment
python -m venv scribed-env

# Activate the virtual environment
scribed-env\Scripts\activate

# Install Scribed
pip install scribed[wake_word,whisper]

# Run Scribed (while virtual environment is active)
scribed --help
```

## 🔧 Development Installation

For developers or advanced users who want the latest features:

```powershell
# Clone the repository
git clone https://github.com/oldirty/scribed.git
cd scribed

# Create and activate virtual environment
python -m venv venv
venv\Scripts\activate

# Install in development mode
pip install -e ".[dev]"

# Run tests to verify installation
pytest

# Use the development version
scribed --help
```

## 🏗️ Building Windows Executable

To create a standalone executable that doesn't require Python:

```powershell
# In the scribed directory with virtual environment activated
pip install pyinstaller

# Build standalone executable
pyinstaller --onefile --name scribed src\scribed\cli.py --hidden-import=scribed

# The executable will be created in dist\scribed.exe
dist\scribed.exe --help
```

## 🛠️ System Requirements

### Required
- **Python 3.8 or later** (download from [python.org](https://www.python.org/downloads/))
- **pip** (usually comes with Python)

### Optional (for specific features)
- **FFmpeg** (for advanced audio processing) - Download from [ffmpeg.org](https://ffmpeg.org/download.html)
- **Microsoft Visual C++ Redistributable** (for some audio libraries)

## 🚨 Common Issues and Solutions

### Issue 1: "scribed command not found"

**Cause**: Python Scripts directory not in PATH

**Solutions**:
```powershell
# Option A: Use full path
C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python311\Scripts\scribed.exe

# Option B: Add to PATH permanently
# Add this to your PATH environment variable:
C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python311\Scripts

# Option C: Use python -m
python -m scribed --help
```

### Issue 2: Permission Denied

**Solution**: Install for current user only:
```powershell
pip install --user scribed
```

### Issue 3: Package installation fails

**Solutions**:
```powershell
# Update pip first
python -m pip install --upgrade pip

# Install with verbose output to see errors
pip install -v scribed

# Install without binary wheels (compile from source)
pip install --no-binary=:all: scribed
```

### Issue 4: Audio libraries fail to install

**Cause**: Missing system dependencies

**Solutions**:
```powershell
# Install Microsoft Visual C++ Redistributable
# Download from: https://aka.ms/vs/17/release/vc_redist.x64.exe

# Or install conda instead of pip
conda install -c conda-forge scribed
```

### Issue 5: Wake word detection not working

**Solution**: Install wake word dependencies:
```powershell
pip install scribed[wake_word]

# Set Picovoice access key
set PICOVOICE_ACCESS_KEY=your_access_key_here
```

## 🎯 Recommended Installation Process

1. **Install Python 3.11** from [python.org](https://www.python.org/downloads/) (check "Add to PATH")
2. **Open PowerShell or Command Prompt**
3. **Update pip**: `python -m pip install --upgrade pip`
4. **Install Scribed**: `pip install --user scribed[whisper]`
5. **Test installation**: `scribed --help`
6. **Create config**: `scribed config-cmd init`
7. **Start daemon**: `scribed start`

## 📁 Portable Installation

For a completely portable installation that doesn't require admin rights:

1. **Download Portable Python** (like WinPython)
2. **Extract to a folder** (e.g., `C:\Portable\Python`)
3. **Open command prompt in that folder**
4. **Install Scribed**: `Scripts\pip.exe install scribed`
5. **Run Scribed**: `Scripts\scribed.exe --help`

## 🔒 Security Considerations

- **Virtual environments** are safer than global installation
- **User installation** (`--user`) is safer than system-wide
- **Review permissions** when using voice commands feature
- **Keep dependencies updated**: `pip install --upgrade scribed`

## 📞 Getting Help

If you're still having issues:

1. **Check the error message** carefully
2. **Update your Python** to the latest version
3. **Try the virtual environment method**
4. **Search existing issues** on GitHub
5. **Create a new issue** with your error message and system info

```powershell
# Get system info for bug reports
python --version
pip --version
scribed --version
```
