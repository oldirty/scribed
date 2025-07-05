# Changelog

All notable changes to Scribed will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2025-07-05

### Added

- **Clipboard Transcription**: New feature to transcribe speech directly to system clipboard
  - CLI command `record-to-clipboard` with duration, provider, and daemon options
  - API endpoint `/record-to-clipboard` for programmatic access
  - Cross-platform clipboard support (Windows, macOS, Linux)
  - Integration with daemon for automatic clipboard copying
  - Configuration options for clipboard behavior
- Initial project structure and configuration
- Audio transcription daemon with file watching
- Wake word detection using Picovoice Porcupine
- Real-time microphone transcription
- Voice command execution with security controls
- REST API with FastAPI
- CLI interface with Click
- Multiple transcription engines (Whisper, OpenAI)
- Comprehensive test suite
- CI/CD pipeline with GitHub Actions
- Multi-platform packaging (DEB, RPM, MSI, ZIP)
- Development tools and scripts

### Changed

- Enhanced CLI with `--use-daemon` flag for API integration
- Improved error handling and user feedback
- Updated configuration system with clipboard options

### Security

- Voice command execution is disabled by default
- Secure power word implementation with safety controls
- Clipboard functionality with platform-appropriate security measures

## [Unreleased]

### Template for Future Releases

## Release Template

```markdown
## [X.Y.Z] - YYYY-MM-DD

### Added
- New features

### Changed
- Changes in existing functionality

### Deprecated
- Soon-to-be removed features

### Removed
- Removed features

### Fixed
- Bug fixes

### Security
- Security improvements
```

## Version History

_Versions will be added here as releases are made._
