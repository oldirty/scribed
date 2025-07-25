@echo off
REM Development batch script for Scribed on Windows
REM Alternative to Makefile for Windows users

if "%1"=="" goto help
if "%1"=="help" goto help
if "%1"=="install" goto install
if "%1"=="install-dev" goto install-dev
if "%1"=="test" goto test
if "%1"=="test-watch" goto test-watch
if "%1"=="lint" goto lint
if "%1"=="format" goto format
if "%1"=="type-check" goto type-check
if "%1"=="clean" goto clean
if "%1"=="run" goto run
if "%1"=="docs" goto docs
if "%1"=="build" goto build
if "%1"=="package-python" goto package-python
if "%1"=="package-test" goto package-test
if "%1"=="package-windows" goto package-windows
if "%1"=="package-source" goto package-source
if "%1"=="package-all" goto package-all
goto help

:help
echo Usage: make.bat [target]
echo.
echo Targets:
echo   help         Show this help message
echo   install      Install the package
echo   install-dev  Install development dependencies
echo   test         Run tests
echo   test-watch   Run tests in watch mode
echo   lint         Run linting
echo   format       Format code with black
echo   type-check   Run type checking with mypy
echo   clean        Clean build artifacts
echo   run          Run the daemon
echo   docs         Generate documentation
echo   build        Build Python packages
echo   package-python    Build Python packages
echo   package-test      Test Python packages
echo   package-windows   Build Windows executable
echo   package-source    Create source archive
echo   package-all       Build all packages
goto end

:install
echo Installing the package...
pip install -e .
goto end

:install-dev
echo Installing development dependencies...
pip install -e ".[dev]"
pre-commit install
goto end

:test
echo Running tests...
pytest
goto end

:test-watch
echo Running tests in watch mode...
pytest-watch
goto end

:lint
echo Running linting...
flake8 src tests
goto end

:format
echo Formatting code...
black src tests
isort src tests
goto end

:type-check
echo Running type checking...
mypy src
goto end

:clean
echo Cleaning build artifacts...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist *.egg-info rmdir /s /q *.egg-info
if exist src\scribed\__pycache__ rmdir /s /q src\scribed\__pycache__
if exist tests\__pycache__ rmdir /s /q tests\__pycache__
for /r . %%d in (__pycache__) do @if exist "%%d" rmdir /s /q "%%d"
for /r . %%f in (*.pyc) do @if exist "%%f" del /q "%%f"
goto end

:run
echo Starting Scribed daemon...
scribed daemon --config config.yaml
goto end

:docs
echo Generating documentation...
REM Add documentation generation commands here
echo Documentation generation not yet configured
goto end

:build
echo Building Python packages...
python -m build
goto end

:package-python
echo Building Python packages...
python scripts\package.py python
goto end

:package-test
echo Testing Python packages...
python scripts\package.py test
goto end

:package-windows
echo Building Windows executable...
python scripts\package.py windows
goto end

:package-source
echo Creating source archive...
python scripts\package.py source
goto end

:package-all
echo Building all packages...
python scripts\package.py all
goto end

:end
