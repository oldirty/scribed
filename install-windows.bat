@echo off
REM Windows Installation Script for Scribed
REM This script automates the installation of Scribed on Windows

setlocal enabledelayedexpansion

echo ================================================================================
echo                        Scribed Windows Installer
echo ================================================================================
echo.
echo This script will install Scribed on your Windows system.
echo.

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
echo 1. User installation (recommended - no admin required)
echo 2. Global installation (requires admin privileges)
echo 3. Virtual environment (safest - isolated installation)
echo 4. Development installation (for developers)
echo.
set /p choice="Enter your choice (1-4): "

if "%choice%"=="1" goto user_install
if "%choice%"=="2" goto global_install
if "%choice%"=="3" goto venv_install
if "%choice%"=="4" goto dev_install

echo Invalid choice. Using user installation as default.
goto user_install

:user_install
echo.
echo Installing Scribed for current user only...
echo.
echo Updating pip...
python -m pip install --upgrade pip --user
echo.
echo Installing Scribed...
python -m pip install --user scribed[whisper]
goto test_install

:global_install
echo.
echo Installing Scribed globally (requires administrator privileges)...
echo.
echo Updating pip...
python -m pip install --upgrade pip
echo.
echo Installing Scribed...
python -m pip install scribed[whisper]
goto test_install

:venv_install
echo.
echo Creating virtual environment installation...
echo.
set venv_name=scribed-env
echo Creating virtual environment: %venv_name%
python -m venv %venv_name%
echo.
echo Activating virtual environment...
call %venv_name%\Scripts\activate.bat
echo.
echo Updating pip...
python -m pip install --upgrade pip
echo.
echo Installing Scribed...
python -m pip install scribed[whisper]
echo.
echo Virtual environment created at: %cd%\%venv_name%
echo To use Scribed in the future, run: %venv_name%\Scripts\activate.bat
goto test_install

:dev_install
echo.
echo Development installation requires the Scribed source code.
echo Please ensure you are running this script from the Scribed repository directory.
echo.
set /p confirm="Continue with development installation? (y/N): "
if /i not "%confirm%"=="y" goto end

if not exist "src\scribed" (
    echo ERROR: This doesn't appear to be the Scribed source directory.
    echo Please run this script from the root of the Scribed repository.
    pause
    exit /b 1
)

echo Creating virtual environment for development...
python -m venv venv
call venv\Scripts\activate.bat
echo.
echo Updating pip...
python -m pip install --upgrade pip
echo.
echo Installing Scribed in development mode...
python -m pip install -e ".[dev]"
echo.
echo Running tests to verify installation...
python -m pytest tests/ -v
goto test_install

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
    echo You may need to use 'python -m scribed' instead.
    echo.
    python -m scribed --version
) else (
    echo SUCCESS: Scribed installed successfully!
    echo.
    scribed --version
)

echo.
echo ================================================================================
echo                              Next Steps
echo ================================================================================
echo.
echo 1. Create a configuration file:
echo    scribed config -o config.yaml
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

if "%choice%"=="3" (
    echo NOTE: Since you used virtual environment installation, remember to activate
    echo the environment before using Scribed:
    echo    %venv_name%\Scripts\activate.bat
    echo.
)

echo For more help, see: WINDOWS_INSTALL.md
echo.

:end
echo Installation script completed.
pause
