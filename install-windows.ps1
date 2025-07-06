#Requires -Version 5.1
<#
.SYNOPSIS
    Windows PowerShell installer for Scribed Audio Transcription Daemon
.DESCRIPTION
    This script provides an automated installation of Scribed on Windows systems
    with multiple installation options and comprehensive error handling.
.PARAMETER InstallType
    Installation type: User, Global, VirtualEnv, or Development
.PARAMETER Features
    Optional features to install: whisper, wake_word, openai, gui
.EXAMPLE
    .\install-windows.ps1
    Interactive installation with menu
.EXAMPLE
    .\install-windows.ps1 -InstallType User -Features whisper,wake_word
    Non-interactive user installation with specific features
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory=$false)]
    [ValidateSet("User", "Global", "VirtualEnv", "Development")]
    [string]$InstallType,
    
    [Parameter(Mandatory=$false)]
    [string[]]$Features = @("whisper")
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

function Install-UserMode {
    param([string[]]$Features)
    
    Write-Step "Installing Scribed for current user..."
    
    Write-Step "Updating pip..."
    python -m pip install --upgrade pip --user
    
    $packageName = "scribed"
    if ($Features.Count -gt 0) {
        $featureString = $Features -join ","
        $packageName = "scribed[$featureString]"
    }
    
    Write-Step "Installing $packageName..."
    python -m pip install --user $packageName
    
    Write-Success "User installation completed!"
}

function Install-GlobalMode {
    param([string[]]$Features)
    
    Write-Step "Installing Scribed globally..."
    Write-Warning "This may require administrator privileges."
    
    Write-Step "Updating pip..."
    python -m pip install --upgrade pip
    
    $packageName = "scribed"
    if ($Features.Count -gt 0) {
        $featureString = $Features -join ","
        $packageName = "scribed[$featureString]"
    }
    
    Write-Step "Installing $packageName..."
    python -m pip install $packageName
    
    Write-Success "Global installation completed!"
}

function Install-VirtualEnv {
    param([string[]]$Features)
    
    $venvName = "scribed-env"
    
    Write-Step "Creating virtual environment: $venvName"
    python -m venv $venvName
    
    Write-Step "Activating virtual environment..."
    & "$venvName\Scripts\Activate.ps1"
    
    Write-Step "Updating pip..."
    python -m pip install --upgrade pip
    
    $packageName = "scribed"
    if ($Features.Count -gt 0) {
        $featureString = $Features -join ","
        $packageName = "scribed[$featureString]"
    }
    
    Write-Step "Installing $packageName..."
    python -m pip install $packageName
    
    Write-Success "Virtual environment installation completed!"
    Write-Host "Virtual environment location: $(Get-Location)\$venvName"
    Write-Host "To activate in the future: $venvName\Scripts\Activate.ps1"
}

function Install-Development {
    Write-Step "Setting up development installation..."
    
    if (-not (Test-Path "src\scribed")) {
        Write-Error "This doesn't appear to be the Scribed source directory."
        Write-Host "Please run this script from the root of the Scribed repository."
        exit 1
    }
    
    Write-Step "Creating development virtual environment..."
    python -m venv venv
    
    Write-Step "Activating virtual environment..."
    & "venv\Scripts\Activate.ps1"
    
    Write-Step "Updating pip..."
    python -m pip install --upgrade pip
    
    Write-Step "Installing Scribed in development mode..."
    python -m pip install -e ".[dev]"
    
    Write-Step "Running tests to verify installation..."
    python -m pytest tests/ -v
    
    Write-Success "Development installation completed!"
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
            return $true
        }
    } catch {
        Write-Error "Scribed installation test failed."
        return $false
    }
}

function Show-NextSteps {
    Write-Header "Next Steps"
    
    Write-Host "1. Create a configuration file:"
    Write-Host "   scribed config -o config.yaml" -ForegroundColor Cyan
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
    
    Write-Host "For detailed documentation, see: WINDOWS_INSTALL.md"
}

function Show-Menu {
    Write-Host "Choose installation method:"
    Write-Host "1. User installation (recommended - no admin required)"
    Write-Host "2. Global installation (requires admin privileges)"
    Write-Host "3. Virtual environment (safest - isolated installation)"
    Write-Host "4. Development installation (for developers)"
    Write-Host
    
    do {
        $choice = Read-Host "Enter your choice (1-4)"
    } while ($choice -notin @("1", "2", "3", "4"))
    
    switch ($choice) {
        "1" { return "User" }
        "2" { return "Global" }
        "3" { return "VirtualEnv" }
        "4" { return "Development" }
    }
}

function Select-Features {
    Write-Host "Available optional features:"
    Write-Host "- whisper: Local Whisper transcription (recommended)"
    Write-Host "- wake_word: Wake word detection"
    Write-Host "- openai: OpenAI API transcription"
    Write-Host "- gui: Graphical user interface"
    Write-Host
    
    $userInput = Read-Host "Enter features to install (comma-separated, or press Enter for whisper)"
    if ([string]::IsNullOrWhiteSpace($userInput)) {
        return @("whisper")
    }
    
    return $userInput.Split(",") | ForEach-Object { $_.Trim() }
}

# Main installation logic
try {
    Write-Header "Scribed Windows Installer"
    
    # Test Python installation
    if (-not (Test-PythonInstallation)) {
        exit 1
    }
    
    # Get installation type
    if (-not $InstallType) {
        $InstallType = Show-Menu
    }
    
    # Get features if not specified
    if (-not $Features -or $Features.Count -eq 0) {
        $Features = Select-Features
    }
    
    Write-Header "Installing Scribed"
    Write-Host "Installation type: $InstallType"
    Write-Host "Features: $($Features -join ', ')"
    Write-Host
    
    # Perform installation
    switch ($InstallType) {
        "User" { Install-UserMode -Features $Features }
        "Global" { Install-GlobalMode -Features $Features }
        "VirtualEnv" { Install-VirtualEnv -Features $Features }
        "Development" { Install-Development }
    }
    
    # Test installation
    if (Test-Installation) {
        Write-Success "Installation completed successfully!"
        Show-NextSteps
    } else {
        Write-Error "Installation test failed. Please check the error messages above."
        exit 1
    }
    
} catch {
    Write-Error "Installation failed: $($_.Exception.Message)"
    Write-Host "Stack trace: $($_.ScriptStackTrace)" -ForegroundColor Red
    exit 1
}

Write-Host "Installation script completed!" -ForegroundColor Green
