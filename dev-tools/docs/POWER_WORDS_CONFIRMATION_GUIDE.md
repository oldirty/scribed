# Enhanced Power Words Configuration Example

This document shows how to configure the enhanced power word confirmation system in Scribed.

## Configuration Options

Add these options to your `power_words` section in the config file:

```yaml
power_words:
  enabled: true
  require_confirmation: true
  
  # Confirmation method: "voice" or "log_only"
  confirmation_method: "voice"
  
  # Voice confirmation settings
  confirmation_timeout: 10.0  # seconds to wait for confirmation
  confirmation_retries: 2     # number of retry attempts
  
  # Safety settings
  auto_approve_safe: false    # auto-approve commands assessed as safe
  log_only_approve: false     # in log_only mode, whether to approve by default
  
  # Command mappings
  mappings:
    discord: 'C:\Users\username\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Discord Inc\Discord.lnk'
    gemini: 'C:\ProgramData\Microsoft\Windows\Start Menu\Programs\Google Chrome.lnk https://gemini.google.com'
    notepad: 'notepad.exe'
    calculator: 'calc.exe'
  
  # Security settings
  allowed_commands: ["notepad.exe", "calc.exe", "explorer.exe"]
  blocked_commands: []
  dangerous_keywords:
    - delete
    - format
    - sudo
    - admin
    - reboot
    - shutdown
    - rm
  max_command_length: 200
```

## Confirmation Methods

### Voice Confirmation (`confirmation_method: "voice"`)

When a power word is detected:

1. **Safety Assessment**: Command is automatically assessed as "safe", "dangerous", or "unknown"
2. **Auto-Deny Dangerous**: Commands with dangerous keywords are automatically denied
3. **Voice Prompt**: For other commands, the system asks for voice confirmation
4. **Listen for Response**: Waits for "yes", "okay", "confirm" (approve) or "no", "cancel", "deny" (reject)
5. **Timeout/Retry**: If no clear response, retries up to the configured limit

Example flow:
```
User: "Hey Scribed, open Discord"
System: [Detects "discord" power word]
System: [Assesses command safety: "safe"]
System: [Requests voice confirmation]
System: "Confirm execution of: open Discord shortcut?"
User: "Yes"
System: [Executes command]
```

### Log-Only Mode (`confirmation_method: "log_only"`)

Commands are logged but not executed (useful for testing):

```
User: "Hey Scribed, open Discord"
System: [Logs: "Would execute: Discord shortcut"]
System: [Returns based on log_only_approve setting]
```

## Safety Assessment

Commands are automatically categorized:

### Safe Commands
- Windows shortcuts (`.lnk` files)
- URLs (`https://`)
- Whitelisted applications (`notepad`, `calc`, etc.)
- Commands in `allowed_commands` list

### Dangerous Commands
- Contains keywords from `dangerous_keywords`
- System administration commands
- File deletion commands

### Unknown Commands
- Everything else not clearly safe or dangerous

## Voice Confirmation Keywords

### Affirmative (Approve)
- "yes", "yeah", "yep"
- "confirm", "approve"
- "ok", "okay"
- "sure", "proceed"

### Negative (Deny)
- "no", "nope"
- "cancel", "deny"
- "stop", "abort"
- "negative"

## Security Best Practices

1. **Use Whitelist**: Configure `allowed_commands` to restrict execution
2. **Review Mappings**: Ensure power word mappings are safe
3. **Test First**: Use `log_only` mode to test configurations
4. **Monitor Logs**: Review transcription logs for unexpected commands
5. **Limit Scope**: Keep command mappings focused on common, safe tasks

## Example Configurations

### Conservative (High Security)
```yaml
power_words:
  enabled: true
  require_confirmation: true
  confirmation_method: "voice"
  auto_approve_safe: false
  allowed_commands: ["notepad.exe", "calc.exe"]
  dangerous_keywords: ["delete", "format", "sudo", "admin", "reboot", "shutdown", "rm", "kill", "stop"]
```

### Balanced (Medium Security)
```yaml
power_words:
  enabled: true
  require_confirmation: true
  confirmation_method: "voice"
  auto_approve_safe: true
  confirmation_timeout: 8.0
  allowed_commands: ["notepad.exe", "calc.exe", "explorer.exe", "chrome.exe"]
```

### Testing Mode (Low Security)
```yaml
power_words:
  enabled: true
  require_confirmation: true
  confirmation_method: "log_only"
  log_only_approve: true
```
