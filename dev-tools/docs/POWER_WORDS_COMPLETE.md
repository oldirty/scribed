# Power Words (Voice Commands) - Complete Implementation

This document describes the secure power words functionality that has been implemented in Scribed.

## Overview

Power words enable voice-activated command execution with comprehensive security controls. When transcribed speech contains configured phrases, the system can automatically execute mapped shell commands.

## ✅ What's Implemented

### Core Functionality
- **Voice Command Detection**: Flexible pattern matching for power word phrases in transcribed text
- **Secure Command Execution**: Shell command execution with safety controls and validation
- **Real-time Integration**: Seamless integration with wake word detection and real-time transcription
- **Async Processing**: Non-blocking command execution for real-time audio processing

### Security Features
- **Disabled by Default**: Power words must be explicitly enabled for security
- **Command Validation**: All commands validated before execution
- **Whitelist Support**: `allowed_commands` for maximum security
- **Blacklist Protection**: `blocked_commands` to prevent dangerous commands
- **Length Limits**: Configurable maximum command length
- **Dangerous Keywords**: Warning system for potentially harmful commands
- **Confirmation Options**: Optional user confirmation before execution
- **Sandboxed Execution**: Commands run in user's home directory with timeout

### Configuration Options
- **Enable/Disable**: Global toggle for power words functionality
- **Phrase Mappings**: Voice phrase → command mappings
- **Security Controls**: Multiple layers of command validation
- **Execution Settings**: Timeouts, confirmation requirements, etc.

## Configuration

### Basic Configuration

```yaml
power_words:
  enabled: true                    # Enable/disable power words
  require_confirmation: false      # Require confirmation before execution
  max_command_length: 100         # Maximum command length
  mappings:                       # Voice phrase → command mappings
    "what time is it": "date"
    "hello world": "echo 'Hello!'"
    "show calendar": "cal"
    "list files": "ls -la"
```

### Security Configuration

```yaml
power_words:
  enabled: true
  require_confirmation: true       # Always ask for confirmation
  max_command_length: 50          # Shorter command limit
  allowed_commands:               # Whitelist only these commands
    - "echo"
    - "date"
    - "cal"
    - "ls"
  blocked_commands:               # Blacklist dangerous commands
    - "rm"
    - "delete"
    - "sudo"
    - "format"
  dangerous_keywords:             # Keywords that trigger warnings
    - "reboot"
    - "shutdown"
    - "kill"
  mappings:
    "safe greeting": "echo 'Hello from power words!'"
    "show time": "date"
```

## Usage Examples

### Voice Commands
Once configured, you can use natural speech to trigger commands:

- Say: "What time is it?" → Executes: `date`
- Say: "Hello world" → Executes: `echo 'Hello!'`
- Say: "Please show me the calendar" → Executes: `cal`
- Say: "Can you list files here?" → Executes: `ls -la`

### Pattern Matching
The system uses flexible pattern matching:
- **Exact Match**: "hello world" matches "hello world"
- **Partial Match**: "show files" matches "can you show files please?"
- **Case Insensitive**: "HELLO WORLD" matches "hello world"
- **Multiple Commands**: One transcription can trigger multiple commands

## Security Model

### Default Security Posture
- **Disabled by default**: Must be explicitly enabled
- **Confirmation required**: Commands require confirmation by default
- **Basic validation**: Command length and basic security checks

### Enhanced Security (Recommended)
```yaml
power_words:
  enabled: true
  require_confirmation: true
  max_command_length: 30
  allowed_commands: ["echo", "date", "cal"]  # Whitelist only
  blocked_commands: ["rm", "sudo", "delete"]
  dangerous_keywords: ["format", "reboot"]
```

### Security Layers
1. **Enabled Check**: Must be explicitly enabled
2. **Pattern Validation**: Commands must match configured patterns
3. **Length Validation**: Commands cannot exceed max length
4. **Blacklist Check**: Blocked commands are rejected
5. **Whitelist Check**: Only allowed commands are permitted (if configured)
6. **Keyword Warning**: Dangerous keywords trigger warnings
7. **Confirmation**: Optional user confirmation before execution
8. **Sandboxed Execution**: Commands run with limited privileges and timeout

## Integration

### Real-time Transcription
Power words are automatically processed during real-time transcription:

1. **Wake Word Detected** → Start listening
2. **Speech Transcribed** → Check for power words
3. **Power Words Found** → Validate and execute commands
4. **Commands Executed** → Continue listening

### Manual Processing
You can also process text directly:

```python
from src.scribed.power_words import PowerWordsEngine
from src.scribed.config import PowerWordsConfig

config = PowerWordsConfig(enabled=True, mappings={"hello": "echo Hi"})
engine = PowerWordsEngine(config)

# Process transcribed text
executed = engine.process_transcription("hello there")
print(f"Executed {executed} commands")
```

## Testing

### Run Tests
```bash
# Test power words functionality
python test_power_words.py

# Demo power words features
python demo_power_words.py

# Test with real-time transcription
scribed daemon --config test_config.yaml
```

### Test Configuration
See `test_config.yaml` for a safe testing configuration with:
- Safe commands only (echo, cd, dir)
- No dangerous operations
- Confirmation disabled for testing

## Implementation Details

### Files Added/Modified
- `src/scribed/power_words/__init__.py` - Main power words engine
- `src/scribed/config.py` - Enhanced PowerWordsConfig with security options
- `src/scribed/realtime/transcription_service.py` - Integration with real-time transcription
- `src/scribed/daemon.py` - Power words configuration passing
- `config.yaml.example` - Configuration examples
- `test_config.yaml` - Test configuration with power words enabled
- `test_power_words.py` - Comprehensive test suite
- `demo_power_words.py` - Interactive demonstration

### Key Classes
- **PowerWordsEngine**: Synchronous power words detection and execution
- **AsyncPowerWordsEngine**: Asynchronous version for real-time integration
- **PowerWordsSecurityError**: Exception for security violations
- **PowerWordsConfig**: Configuration model with validation

## Security Recommendations

### Production Deployment
1. **Use Whitelists**: Configure `allowed_commands` with only necessary commands
2. **Enable Confirmation**: Set `require_confirmation: true`
3. **Limit Commands**: Keep `max_command_length` small (≤50)
4. **Monitor Logs**: Watch for security warnings and failed attempts
5. **Regular Review**: Periodically review configured mappings

### Safe Command Examples
```yaml
mappings:
  "what time": "date"              # Show current time
  "show calendar": "cal"           # Display calendar
  "hello": "echo 'Hello!'"         # Simple greeting
  "list directory": "ls -la"       # Show files
  "where am i": "pwd"              # Show current directory
  "disk space": "df -h"            # Show disk usage
```

### Commands to Avoid
- File operations: `rm`, `delete`, `mv`, `cp`
- System operations: `sudo`, `reboot`, `shutdown`
- Network operations: `wget`, `curl` (with URLs)
- Installation: `apt`, `yum`, `pip install`

## Future Enhancements

Potential future improvements:
- Voice confirmation prompts
- GUI confirmation dialogs
- Command output capture and display
- Command history and audit logging
- User-specific command restrictions
- Time-based access controls

## Troubleshooting

### Common Issues

**Power words not working**
- Check `enabled: true` in configuration
- Verify mappings are configured
- Check logs for security errors

**Commands not executing**
- Verify commands are in `allowed_commands` (if using whitelist)
- Check commands aren't in `blocked_commands`
- Ensure commands are under `max_command_length`

**Security errors**
- Review security configuration
- Check command validation logs
- Adjust whitelist/blacklist as needed

### Debug Logging
Enable debug logging to see power word detection:
```python
import logging
logging.getLogger('src.scribed.power_words').setLevel(logging.DEBUG)
```

## Conclusion

The power words implementation provides a secure, flexible system for voice-activated command execution. The multi-layered security approach ensures that the feature can be used safely while providing the convenience of hands-free computer interaction.

**Remember**: Power words execute shell commands - always prioritize security over convenience!
