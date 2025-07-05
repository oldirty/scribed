# Release Strategy and Packaging Guide

This document outlines the release strategy for Scribed and provides instructions for creating packages for different platforms.

## Release Strategy Overview

Scribed follows a comprehensive multi-platform release strategy that creates packages for:

- **Python Package Index (PyPI)**: Wheel and source distributions
- **Linux RPM packages**: For RedHat, CentOS, Fedora, and compatible distributions
- **Linux DEB packages**: For Ubuntu, Debian, and compatible distributions  
- **Windows MSI installer**: Professional installer for Windows systems
- **Windows ZIP package**: Portable version for Windows
- **Source archive**: For building from source

## Automated Release Process

### Triggering a Release

Releases are automatically triggered when you push a version tag:

```bash
# Create and push a version tag
git tag v1.0.0
git push origin v1.0.0
```

The GitHub Actions workflow will automatically:

1. Build Python packages (wheel and source distribution)
2. Build Linux DEB packages for Ubuntu 20.04 and 22.04
3. Build Linux RPM packages for Fedora/RHEL
4. Build Windows MSI installer and ZIP package
5. Create a GitHub release with all packages attached
6. Publish Python packages to PyPI (if configured)

### GitHub Secrets Configuration

To enable full automation, configure these secrets in your GitHub repository:

- `PICOVOICE_ACCESS_KEY`: For testing wake word functionality
- `CODECOV_TOKEN`: For code coverage reporting
- `PYPI_TOKEN`: For publishing to PyPI (optional)

## Package Types and Installation

### Python Packages (All Platforms)

**Installation:**
```bash
pip install scribed
# or from wheel
pip install scribed-1.0.0-py3-none-any.whl
```

**Features:**
- Cross-platform compatibility
- Automatic dependency management
- Integration with Python virtual environments

### Linux DEB Packages (Ubuntu/Debian)

**Installation:**
```bash
sudo dpkg -i scribed_1.0.0-1_all.deb
sudo apt-get install -f  # Fix any missing dependencies
```

**Features:**
- System integration with systemd
- Automatic dependency resolution
- Standard Debian package management
- Installs to standard system paths

### Linux RPM Packages (RedHat/CentOS/Fedora)

**Installation:**
```bash
sudo rpm -ivh scribed-1.0.0-1.noarch.rpm
# or with dependency resolution
sudo dnf install scribed-1.0.0-1.noarch.rpm
```

**Features:**
- System integration with systemd
- RPM package management
- Compatible with YUM/DNF package managers

### Windows MSI Installer

**Installation:**
- Double-click the `.msi` file
- Follow the installation wizard
- Installs to `Program Files\Scribed`

**Features:**
- Professional Windows installer experience
- Registry integration
- Automatic uninstallation support
- Start menu shortcuts

### Windows ZIP Package

**Installation:**
- Extract the ZIP file to any directory
- Run `scribed.exe` directly

**Features:**
- Portable installation (no admin rights required)
- Self-contained executable
- Includes configuration templates

## Local Development and Testing

### Testing Packages Locally

Use the provided scripts to test packaging locally before creating releases:

**Linux/macOS:**
```bash
# Build and test Python packages
python scripts/package.py python
python scripts/package.py test

# Create source archive
python scripts/package.py source

# Build everything
python scripts/package.py all
```

**Windows:**
```cmd
# Using Python script
python scripts\package.py all

# Using PowerShell script
.\scripts\package.ps1 all

# Using batch file
.\make.bat package-all
```

### Make Commands

**Linux/macOS:**
```bash
make package-python     # Build Python packages
make package-test       # Test Python packages  
make package-source     # Create source archive
make package-all        # Build all packages
make release-check      # Verify ready for release
```

**Windows:**
```cmd
.\make.bat package-python
.\make.bat package-windows
.\make.bat package-all
```

## Binary Distribution Strategy

### Linux Binaries

The DEB and RPM packages install the `scribed` command to standard system paths:

- Executable: `/usr/bin/scribed`
- Configuration: `/etc/scribed/` (system) or `~/.config/scribed/` (user)
- Logs: `/var/log/scribed/` (system) or `~/.local/share/scribed/logs/` (user)
- Service files: `/etc/systemd/system/scribed.service`

### Windows Binaries

The Windows packages provide:

- **MSI Installer**: Installs to `C:\Program Files\Scribed\scribed.exe`
- **ZIP Package**: Portable `scribed.exe` with bundled dependencies

Both include:
- Example configuration file
- Documentation (README, LICENSE)
- PowerShell integration scripts

## Version Management

### Version Numbering

Scribed follows [Semantic Versioning](https://semver.org/):

- `MAJOR.MINOR.PATCH` (e.g., `1.2.3`)
- Pre-release: `1.2.3-alpha.1`, `1.2.3-beta.2`, `1.2.3-rc.1`

### Creating Releases

1. **Update version** in `pyproject.toml`:
   ```toml
   version = "1.2.3"
   ```

2. **Update CHANGELOG.md** with release notes

3. **Commit changes**:
   ```bash
   git add .
   git commit -m "Release v1.2.3"
   ```

4. **Create and push tag**:
   ```bash
   git tag v1.2.3
   git push origin main v1.2.3
   ```

5. **Monitor GitHub Actions** for build completion

## Package Contents

### All Packages Include

- `scribed` executable/command
- Configuration template (`config.yaml`)
- Documentation (README.md, LICENSE)
- Example files

### Platform-Specific Additions

**Linux packages (DEB/RPM):**
- Systemd service file
- Man page
- Desktop entry (for GUI future)

**Windows packages:**
- Windows-specific configuration examples
- PowerShell integration scripts
- Uninstaller (MSI only)

## Distribution Channels

### Primary Channels

1. **GitHub Releases**: All package types
2. **PyPI**: Python packages only
3. **Direct Download**: From GitHub releases page

### Future Channels (Planned)

1. **Ubuntu PPA**: For easier DEB installation
2. **Homebrew**: For macOS support
3. **Chocolatey**: For Windows package management
4. **Docker Hub**: Containerized versions

## Security Considerations

### Package Signing

- **Windows**: MSI packages should be code-signed (future enhancement)
- **Linux**: GPG-signed packages (future enhancement)
- **Python**: Packages published to PyPI with verified publisher

### Distribution Security

- All packages built in isolated CI environments
- Dependencies pinned and verified
- Automated vulnerability scanning
- Checksums provided for all packages

## Troubleshooting

### Common Issues

**Build Failures:**
- Check GitHub Actions logs
- Verify all dependencies are available
- Ensure version tags are properly formatted

**Installation Issues:**
- Verify system requirements are met
- Check for conflicting installations
- Review platform-specific documentation

**Testing Locally:**
- Use provided scripts in `scripts/` directory
- Test in clean virtual environments
- Verify package contents before releasing

### Getting Help

- Check the [Issues](https://github.com/oldirty/scribed/issues) page
- Review build logs in GitHub Actions
- Test locally using provided scripts

## Future Enhancements

### Planned Improvements

1. **Container Images**: Docker images for easy deployment
2. **Package Repositories**: Dedicated APT/YUM repositories
3. **Code Signing**: Signed packages for enhanced security
4. **Homebrew Formula**: macOS package management
5. **Snap Package**: Universal Linux package
6. **AppImage**: Portable Linux application

### Automation Enhancements

1. **Automated Testing**: Package installation testing in containers
2. **Performance Testing**: Automated benchmarks
3. **Security Scanning**: Automated vulnerability detection
4. **Release Notes**: Automated changelog generation
