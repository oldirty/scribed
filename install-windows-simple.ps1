#Requires -Version 5.1
<#
.SYNOPSIS
    Simple Windows PowerShell installer for Scribed (Development Version)
.DESCRIPTION
    This script provides an automated installation of Scribed from the current development directory
    with better error handling and user experience.
.PARAMETER InstallType
    Installation type: VirtualEnv, User, or Manual
.EXAMPLE
    .\install-windows-simple.ps1
    Interactive installation with menu
.EXAMPLE
    .\install-windows-simple.ps1 -InstallType VirtualEnv
    Non-interactive virtual environment installation
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory=$false)]
    [ValidateSet("VirtualEnv", "User", "Manual")]
    [string]$InstallType
)

# Set up error handling
$ErrorActionPreference = "Stop"

function Write-Header {
    param([string]$Text)
    Write-Host "=" * 80 -ForegroundColor Cyan
    Write-Host $Text -ForegroundColor Cyan
    Write-Host "=" * 80 -ForegroundColor Cyan
    Write-Host
}

function Write-Step {
    param([string]$Text)
    Write-Host ">>> $Text" -ForegroundColor Yellow
}

function Write-Success {
    param([string]$Text)
    Write-Host "✓ $Text" -ForegroundColor Green
}

function Write-Warning {
    param([string]$Text)
    Write-Host "⚠ $Text" -ForegroundColor Yellow
}

function Write-Error {
    param([string]$Text)
    Write-Host "✗ $Text" -ForegroundColor Red
}

function Test-ProjectDirectory {
    if (-not (Test-Path "src\scribed")) {
        Write-Error "This script must be run from the Scribed project root directory."
        Write-Host "Please ensure you have the Scribed source code and run this script from"
        Write-Host "the directory containing src\scribed\"
        return $false
    }
    Write-Success "Found Scribed project directory"
    return $true
}

function Test-PythonInstallation {
    try {
        $pythonVersion = python --version 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Success "Python found: $pythonVersion"
            return $true
        }
    } catch {
        # Python not found
    }
    
    Write-Error "Python is not installed or not in PATH."
    Write-Host "Please install Python 3.8 or later from: https://www.python.org/downloads/"
    Write-Host "Make sure to check 'Add Python to PATH' during installation."
    return $false
}

function Install-VirtualEnvMode {
    Write-Step "Creating virtual environment for Scribed development..."
    
    # Remove existing venv if it exists
    if (Test-Path "venv") {
        Write-Step "Removing existing virtual environment..."
        Remove-Item -Recurse -Force "venv"
    }
    
    Write-Step "Creating new virtual environment..."
    python -m venv venv
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create virtual environment"
    }
    
    Write-Step "Activating virtual environment..."
    & "venv\Scripts\Activate.ps1"
    
    Write-Step "Upgrading pip..."
    python -m pip install --upgrade pip
    
    Write-Step "Installing Scribed in development mode with basic features..."
    python -m pip install -e .
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to install Scribed"
    }
    
    Write-Step "Installing optional Whisper support..."
    try {
        python -m pip install "openai-whisper>=20231117" "faster-whisper>=0.10.0"
        Write-Success "Whisper support installed successfully"
    } catch {
        Write-Warning "Failed to install Whisper support, but basic Scribed functionality should work"
    }
    
    Write-Step "Installing optional TTS support for testing..."
    try {
        python -m pip install -e ".[tts]"
        Write-Success "TTS support installed successfully"
    } catch {
        Write-Warning "Failed to install TTS support. Tests will use synthetic audio instead."
    }
    
    Write-Success "Virtual environment installation completed!"
    Write-Host
    Write-Header "Virtual Environment Installation Complete!"
    Write-Host "To use Scribed:"
    Write-Host "1. Activate the virtual environment: venv\Scripts\Activate.ps1"
    Write-Host "2. Run scribed commands: scribed --help"
    Write-Host
    Write-Host "Quick start:"
    Write-Host "  venv\Scripts\Activate.ps1"
    Write-Host "  scribed config-cmd init"
    Write-Host "  scribed start"
}

function Install-UserMode {
    Write-Step "Installing Scribed for current user..."
    
    Write-Step "Upgrading pip..."
    python -m pip install --upgrade pip --user
    
    Write-Step "Installing Scribed in development mode..."
    python -m pip install --user -e .
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to install Scribed"
    }
    
    Write-Step "Installing optional Whisper support..."
    try {
        python -m pip install --user "openai-whisper>=20231117" "faster-whisper>=0.10.0"
        Write-Success "Whisper support installed successfully"
    } catch {
        Write-Warning "Failed to install Whisper support, but basic Scribed functionality should work"
    }
    
    Write-Success "User installation completed!"
}

function Show-ManualInstructions {
    Write-Header "Manual Installation Instructions"
    
    Write-Host "If you prefer to install manually, here are the commands:"
    Write-Host
    Write-Host "For virtual environment (recommended):" -ForegroundColor Cyan
    Write-Host "  python -m venv scribed-env"
    Write-Host "  scribed-env\Scripts\Activate.ps1"
    Write-Host "  python -m pip install --upgrade pip"
    Write-Host "  python -m pip install -e ."
    Write-Host "  python -m pip install `"openai-whisper>=20231117`" `"faster-whisper>=0.10.0`""
    Write-Host
    Write-Host "For user installation:" -ForegroundColor Cyan
    Write-Host "  python -m pip install --user --upgrade pip"
    Write-Host "  python -m pip install --user -e ."
    Write-Host "  python -m pip install --user `"openai-whisper>=20231117`" `"faster-whisper>=0.10.0`""
    Write-Host
    Write-Host "For system-wide installation (requires admin):" -ForegroundColor Cyan
    Write-Host "  python -m pip install --upgrade pip"
    Write-Host "  python -m pip install -e ."
    Write-Host "  python -m pip install `"openai-whisper>=20231117`" `"faster-whisper>=0.10.0`""
    Write-Host
}

function Test-Installation {
    Write-Header "Testing Installation"
    
    try {
        $version = scribed --version 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Success "Scribed command works: $version"
            return $true
        }
    } catch {
        # Command not found, try python -m
    }
    
    try {
        $version = python -m scribed --version 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Warning "'scribed' command not in PATH, but 'python -m scribed' works: $version"
            Write-Host "You may need to add Python Scripts directory to your PATH."
            Write-Success "Scribed installation successful! Use 'python -m scribed' to run commands."
            return $true
        }
    } catch {
        Write-Error "Scribed installation test failed."
        return $false
    }
}

function Show-NextSteps {
    param([string]$InstallType)
    
    Write-Header "Next Steps"
    
    Write-Host "1. Create a configuration file:"
    if ($InstallType -eq "VirtualEnv") {
        Write-Host "   venv\Scripts\Activate.ps1" -ForegroundColor Cyan
        Write-Host "   scribed config -o config.yaml" -ForegroundColor Cyan
    } else {
        Write-Host "   scribed config -o config.yaml" -ForegroundColor Cyan
    }
    Write-Host
    
    Write-Host "2. Edit the configuration file:"
    Write-Host "   notepad config.yaml" -ForegroundColor Cyan
    Write-Host
    
    Write-Host "3. Start the daemon:"
    Write-Host "   scribed start" -ForegroundColor Cyan
    Write-Host
    
    Write-Host "4. Check status:"
    Write-Host "   scribed status" -ForegroundColor Cyan
    Write-Host
    
    Write-Host "5. View help:"
    Write-Host "   scribed --help" -ForegroundColor Cyan
    Write-Host
    
    if ($InstallType -eq "VirtualEnv") {
        Write-Host "IMPORTANT: Remember to activate the virtual environment before using Scribed:" -ForegroundColor Yellow
        Write-Host "   venv\Scripts\Activate.ps1" -ForegroundColor Cyan
        Write-Host
    }
    
    Write-Host "For troubleshooting, see: WINDOWS_INSTALL.md"
}

function Show-Menu {
    Write-Host "Choose installation method:"
    Write-Host "1. Virtual environment installation (recommended - isolated)"
    Write-Host "2. User installation (installs to current user)"
    Write-Host "3. Show manual installation instructions"
    Write-Host
    
    do {
        $choice = Read-Host "Enter your choice (1-3)"
    } while ($choice -notin @("1", "2", "3"))
    
    switch ($choice) {
        "1" { return "VirtualEnv" }
        "2" { return "User" }
        "3" { return "Manual" }
    }
}

# Main installation logic
try {
    Write-Header "Scribed Simple Windows Installer"
    Write-Host "This script will install Scribed from the current development directory."
    Write-Host
    
    # Test if we're in the right directory
    if (-not (Test-ProjectDirectory)) {
        exit 1
    }
    
    # Test Python installation
    if (-not (Test-PythonInstallation)) {
        exit 1
    }
    
    # Get installation type
    if (-not $InstallType) {
        $InstallType = Show-Menu
    }
    
    Write-Header "Installing Scribed"
    Write-Host "Installation type: $InstallType"
    Write-Host
    
    # Perform installation
    switch ($InstallType) {
        "VirtualEnv" { 
            Install-VirtualEnvMode
            # Test installation
            if (Test-Installation) {
                Show-NextSteps -InstallType $InstallType
            }
        }
        "User" { 
            Install-UserMode
            # Test installation
            if (Test-Installation) {
                Show-NextSteps -InstallType $InstallType
            }
        }
        "Manual" { 
            Show-ManualInstructions
        }
    }
    
    Write-Success "Installation script completed successfully!"
    
} catch {
    Write-Error "Installation failed: $($_.Exception.Message)"
    Write-Host "Stack trace: $($_.ScriptStackTrace)" -ForegroundColor Red
    Write-Host
    Write-Host "For troubleshooting help, see: WINDOWS_INSTALL.md"
    exit 1
}
