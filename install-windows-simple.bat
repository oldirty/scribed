@echo off
REM Simple Windows Installation Script for Scribed (Development Version)
REM This script installs Scribed from the local development directory

setlocal enabledelayedexpansion

echo ================================================================================
echo                    Scribed Simple Windows Installer
echo ================================================================================
echo.
echo This script will install Scribed from the current development directory.
echo.

REM Check if we're in the right directory
if not exist "src\scribed" (
    echo ERROR: This script must be run from the Scribed project root directory.
    echo Please ensure you have the Scribed source code and run this script from
    echo the directory containing src\scribed\
    pause
    exit /b 1
)

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH.
    echo.
    echo Please install Python 3.8 or later from:
    echo https://www.python.org/downloads/
    echo.
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

echo Python found:
python --version
echo.

REM Ask user for installation type
echo Choose installation method:
echo 1. Development installation in virtual environment (recommended)
echo 2. User installation (installs to current user)
echo 3. Show manual installation instructions
echo.
set /p choice="Enter your choice (1-3): "

if "%choice%"=="1" goto venv_dev_install
if "%choice%"=="2" goto user_dev_install
if "%choice%"=="3" goto show_manual
echo Invalid choice. Using virtual environment installation as default.
goto venv_dev_install

:venv_dev_install
echo.
echo Creating virtual environment for Scribed development...
echo.

REM Remove existing venv if it exists
if exist "venv" (
    echo Removing existing virtual environment...
    rmdir /s /q venv
)

echo Creating new virtual environment...
python -m venv venv
if errorlevel 1 (
    echo ERROR: Failed to create virtual environment.
    pause
    exit /b 1
)

echo Activating virtual environment...
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo ERROR: Failed to activate virtual environment.
    pause
    exit /b 1
)

echo Upgrading pip...
python -m pip install --upgrade pip

echo Installing Scribed in development mode with basic features...
python -m pip install -e .
if errorlevel 1 (
    echo ERROR: Failed to install Scribed.
    pause
    exit /b 1
)

echo Installing optional whisper support...
python -m pip install "openai-whisper>=20231117" "faster-whisper>=0.10.0"

echo Installing optional TTS support for testing...
python -m pip install -e ".[tts]" 2>nul
if errorlevel 1 (
    echo WARNING: Failed to install TTS support. Tests will use synthetic audio instead.
)

echo.
echo ================================================================================
echo                 Virtual Environment Installation Complete!
echo ================================================================================
echo.
echo To use Scribed:
echo 1. Activate the virtual environment: venv\Scripts\activate.bat
echo 2. Run scribed commands: scribed --help
echo.
echo Quick start:
echo   venv\Scripts\activate.bat
echo   scribed config-cmd init
echo   scribed start
echo.
goto test_install

:user_dev_install
echo.
echo Installing Scribed for current user...
echo.
echo Upgrading pip...
python -m pip install --upgrade pip --user

echo Installing Scribed in development mode...
python -m pip install --user -e .
if errorlevel 1 (
    echo ERROR: Failed to install Scribed.
    pause
    exit /b 1
)

echo Installing optional whisper support...
python -m pip install --user "openai-whisper>=20231117" "faster-whisper>=0.10.0"

goto test_install

:show_manual
echo.
echo ================================================================================
echo                    Manual Installation Instructions
echo ================================================================================
echo.
echo If you prefer to install manually, here are the commands:
echo.
echo For virtual environment (recommended):
echo   python -m venv scribed-env
echo   scribed-env\Scripts\activate.bat
echo   python -m pip install --upgrade pip
echo   python -m pip install -e .
echo   python -m pip install "openai-whisper>=20231117" "faster-whisper>=0.10.0"
echo.
echo For user installation:
echo   python -m pip install --user --upgrade pip
echo   python -m pip install --user -e .
echo   python -m pip install --user "openai-whisper>=20231117" "faster-whisper>=0.10.0"
echo.
echo For system-wide installation (requires admin):
echo   python -m pip install --upgrade pip
echo   python -m pip install -e .
echo   python -m pip install "openai-whisper>=20231117" "faster-whisper>=0.10.0"
echo.
goto end

:test_install
echo.
echo ================================================================================
echo                            Testing Installation
echo ================================================================================
echo.

REM Test if scribed command works
scribed --version >nul 2>&1
if errorlevel 1 (
    echo WARNING: 'scribed' command not found in PATH.
    echo Trying with 'python -m scribed'...
    python -m scribed --version
    if errorlevel 1 (
        echo ERROR: Scribed installation failed.
        pause
        exit /b 1
    ) else (
        echo SUCCESS: Scribed installed! Use 'python -m scribed' to run commands.
    )
) else (
    echo SUCCESS: Scribed installed successfully!
    scribed --version
)

echo.
echo ================================================================================
echo                              Next Steps
echo ================================================================================
echo.
echo 1. Create a configuration file:
if "%choice%"=="1" (
    echo    venv\Scripts\activate.bat
    echo    scribed config -o config.yaml
) else (
    echo    scribed config -o config.yaml
)
echo.
echo 2. Edit the configuration file as needed:
echo    notepad config.yaml
echo.
echo 3. Start the daemon:
echo    scribed start
echo.
echo 4. Check status:
echo    scribed status
echo.
echo 5. View help:
echo    scribed --help
echo.

if "%choice%"=="1" (
    echo IMPORTANT: Remember to activate the virtual environment before using Scribed:
    echo    venv\Scripts\activate.bat
    echo.
)

:end
echo Installation completed successfully!
echo.
echo For troubleshooting, see: WINDOWS_INSTALL.md
pause
