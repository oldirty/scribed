# Development Tools

This directory contains copilot-generated development and debugging tools created during the development of Scribed. The tools and documentation here were primarily used for:

- Debugging specific issues and edge cases
- Validating fixes and new features
- Creating regression tests for critical bugs
- Documenting implementation details and decisions

## Directory Structure

### `tests/`

Contains one-off test files created for debugging, validation, and regression testing. These tests complement the main test suite in the project root's `tests/` directory.

**Key areas covered:**
- Audio processing and microphone input
- Wake word detection (both Picovoice and Whisper)
- Text-to-Speech (TTS) integration and fallbacks
- Threading and performance issues
- Power words and clipboard functionality
- CLI and integration testing

### `docs/`

Contains detailed documentation, implementation summaries, and fix notes created during development.

**Document types:**
- Fix summaries explaining specific bug resolutions
- Complete feature implementation documentation
- Technical notes on complex integrations
- Historical context for design decisions

## Purpose

These tools were created to:

1. **Isolate Issues**: Create minimal reproducible test cases
2. **Validate Fixes**: Ensure solutions work correctly
3. **Prevent Regressions**: Catch issues before they reach main codebase
4. **Document Decisions**: Preserve reasoning behind implementation choices
5. **Knowledge Transfer**: Help future developers understand complex areas

## Usage Guidelines

- Files in `tests/` can be run independently for debugging
- Documentation in `docs/` provides context for understanding the codebase
- These are supplementary to the main project structure
- Not intended for production use

## Relationship to Main Codebase

While these tools were created during development, the actual fixes and features have been integrated into:

- `src/scribed/` - Main application code
- `tests/` - Official test suite
- Project documentation files

This directory serves as a historical record and debugging resource.
