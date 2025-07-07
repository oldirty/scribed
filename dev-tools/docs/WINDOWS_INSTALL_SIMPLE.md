# Easy Windows Installation for Scribed

This guide provides the **simplest and most reliable** methods to install Scribed on Windows.

## 🚀 Quick Install (Choose One Method)

### Method 1: One-Command Install (Easiest)

If you have the Scribed source code, open PowerShell or Command Prompt in the project directory and run:

**PowerShell (Recommended):**

```powershell
# Create virtual environment and install
python -m venv scribed-env
scribed-env\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
```

**Command Prompt:**

```cmd
# Create virtual environment and install
python -m venv scribed-env
scribed-env\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -e .
```

### Method 2: Use Our Installation Scripts

We provide automated installation scripts:

**For PowerShell users:**
```powershell
.\install-windows-simple.ps1
```

**For Command Prompt users:**
```cmd
install-windows-simple.bat
```

### Method 3: User Installation (No Virtual Environment)

If you prefer to install directly to your user account:

```cmd
python -m pip install --user --upgrade pip
python -m pip install --user -e .
```

## ✅ Test Your Installation

After installation, test that Scribed works:

```cmd
# If using virtual environment, activate it first:
scribed-env\Scripts\activate.bat

# Test the installation:
scribed --version
scribed --help
```

If the `scribed` command doesn't work, try:
```cmd
python -m scribed --version
python -m scribed --help
```

## 🎯 Quick Start

1. **Create a config file:**
   ```cmd
   scribed config-cmd init
   ```

2. **Edit the config (optional):**
   ```cmd
   notepad config.yaml
   ```

3. **Start Scribed:**
   ```cmd
   scribed start
   ```

4. **Check status:**
   ```cmd
   scribed status
   ```

## 🔧 Add Whisper Support (Optional)

For local audio transcription, install Whisper:

```cmd
# If using virtual environment, activate it first
scribed-env\Scripts\activate.bat

# Install Whisper
python -m pip install "openai-whisper>=20231117" "faster-whisper>=0.10.0"
```

## 🛠️ Troubleshooting

### Python Not Found
- Install Python from https://python.org/downloads/
- **Important:** Check "Add Python to PATH" during installation
- Restart your terminal after installation

### Permission Errors
- Use virtual environment method (Method 1)
- Or run terminal as administrator for system-wide install

### Command Not Found
- If `scribed` command doesn't work, use `python -m scribed`
- Make sure virtual environment is activated if you used one

### Import Errors
- Make sure you're in the project root directory (where `src/scribed` exists)
- Try reinstalling: `python -m pip install --force-reinstall -e .`

## 📝 Important Notes

- **Virtual environments are recommended** - they prevent conflicts with other Python packages
- **Always activate your virtual environment** before using Scribed if you chose that method
- The `-e .` flag installs in "editable" mode, perfect for development

## 🔄 Uninstalling

To uninstall Scribed:

```cmd
# If using virtual environment, just delete the folder:
rmdir /s scribed-env

# If installed to user account:
python -m pip uninstall scribed
```

## 💡 Pro Tips

1. **Create a desktop shortcut** for your virtual environment:
   - Create a `.bat` file with: `call C:\path\to\scribed-env\Scripts\activate.bat && cmd`

2. **Add to Windows Terminal** for easy access:
   - Add the virtual environment path to your terminal profiles

3. **Use Windows Package Manager** (if available):
   ```cmd
   # Future: when published to PyPI
   winget install scribed
   ```

---

**Need help?** Open an issue at https://github.com/oldirty/scribed/issues
