# Python Version Support Update

## Summary

Removed support for Python 3.8 and 3.9, setting the minimum required Python version to 3.10.

## Motivation

1. **Simplified Maintenance**: Fewer Python versions to test and support
2. **Modern Features**: Can now use Python 3.10+ features like improved type hints, pattern matching, and better asyncio support
3. **Dependency Compatibility**: Many modern packages are dropping Python 3.8/3.9 support
4. **Security**: Python 3.10+ have better security features and active support

## Changes Made

### Core Configuration

**File**: `pyproject.toml`
- Updated `requires-python = ">=3.10"`
- Removed Python 3.8 and 3.9 from classifiers
- Updated mypy target to `python_version = "3.10"`

### CI/CD Pipeline

**File**: `.github/workflows/ci.yml`
- Updated test matrix: `python-version: ["3.10", "3.11", "3.12"]`

**File**: `.github/workflows/release.yml`
- Updated Debian package dependency: `python3 (>= 3.10)`
- Updated documentation requirement: `Python 3.10 or higher`

### Documentation

**File**: `README.md`
- Updated badge: `Python 3.10+`

**File**: `WINDOWS_INSTALL.md`
- Updated requirement: `Python 3.10 or later`

**File**: `QUICK_START_WINDOWS.md` 
- Updated requirement: `Python 3.10+`

### Installation Scripts

**Files**: `install-windows.bat`, `install-windows.ps1`, `install-windows-simple.bat`, `install-windows-simple.ps1`
- Updated error messages: `Python 3.10 or later`

### Summary Documents

**File**: `TTS_FIX_SUMMARY.md`
- Updated: `Tests work on all Python versions (3.10+)`

**File**: `INTEGRATION_TEST_SUCCESS.md`
- Updated: `Python 3.10, 3.11, and 3.12+`

## Impact

### ✅ Benefits
- **Cleaner CI**: Faster CI runs with fewer test matrix combinations
- **Modern Features**: Can use Python 3.10+ features like:
  - Structural pattern matching (`match` statements)
  - Better type hints (union operator `|`)
  - Improved error messages
  - Better asyncio performance
- **Better Dependencies**: Access to packages that require Python 3.10+
- **Future-Proof**: Aligned with current Python ecosystem trends

### ⚠️ Breaking Changes
- **Compatibility**: Users with Python 3.8 or 3.9 will need to upgrade
- **Deployment**: Older systems may need Python upgrades

## Supported Versions

| Python Version | Support Status |
|---|---|
| 3.8 | ❌ Dropped |
| 3.9 | ❌ Dropped |
| 3.10 | ✅ Supported |
| 3.11 | ✅ Supported |
| 3.12 | ✅ Supported |

## Migration Guide

For users currently using Python 3.8 or 3.9:

1. **Install Python 3.10+** from [python.org](https://python.org/downloads)
2. **Recreate virtual environment**:
   ```bash
   rm -rf venv  # or rmdir /s venv on Windows
   python -m venv venv
   source venv/bin/activate  # or venv\Scripts\activate on Windows
   pip install -e ".[dev]"
   ```
3. **Update CI/CD** if using older Python versions

## Testing

- ✅ Integration tests pass with Python 3.11.3
- ✅ All existing functionality preserved
- ✅ CI pipeline updated to test Python 3.10, 3.11, and 3.12

This change positions Scribed to take advantage of modern Python features while maintaining compatibility with currently supported Python versions.
