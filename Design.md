## 1. Overview 📝
This document outlines the design for a multifaceted Audio Transcription Daemon. The daemon functions as a voice assistant capable of:
- Acting as a hands-free command interface, mapping spoken "power words" to execute predefined terminal commands.
- Providing real-time transcription, activated by a user-defined wake word.
- Transcribing audio from files in a batch processing mode.

A core principle is to access the system's audio stream without blocking other applications, ensuring seamless background operation. Security is a paramount concern and is addressed throughout the design to prevent unintended command execution.

## 2. Goals and Non-Goals
Goals
- Voice-Activated Command Execution: Map user-defined spoken phrases to specific, pre-approved terminal commands.
- Hands-Free Activation: Use a custom wake word to start and stop transcription sessions.
- Non-Exclusive Audio Access: Listen to the microphone without taking exclusive control, permitting other applications (e.g., video conferencing, games) to use the audio device concurrently.
- Real-time & Batch Transcription: Support both live microphone input and pre-existing audio files as sources.
- Security: Implement robust safeguards to prevent accidental or malicious command execution.
- Configurability: Allow for easy configuration of the wake word, power words, language, and output formats.

Non-Goals
- Dynamic Command Generation: The daemon will not attempt to interpret natural language to create commands. It will only execute commands from a pre-defined whitelist.
- Complex User Interface (UI): This design is for a headless daemon controlled via a configuration file and a simple API.
- Running as a Privileged User: The daemon is intended to run with standard user privileges, not as root or administrator.

## 3. Security Considerations 🔒
Introducing command execution requires a security-first mindset. The following principles are mandatory:
* Explicit Opt-In: The power words feature will be disabled by default. The user must explicitly enable it in the configuration.
* Command Whitelisting: The daemon will only execute commands that are explicitly defined in the power_words mapping in the configuration file. Any spoken phrase not on this list will be ignored (other than being transcribed).
* No Arbitrary Execution: The daemon will never execute a command constructed from arbitrary spoken input. The mapping is strictly 1:1 from a fixed phrase to a fixed command.
* User Context: Commands will be executed in a subshell running with the exact same user privileges as the daemon itself.
* Transparent Logging: Every detected power word and subsequent command execution (including failures) will be logged clearly and conspicuously.

## 4. High-Level Architecture 🏗️
The architecture uses a two-stage listening model for efficiency, combined with a parallel processing pipeline in the active stage.

Architectural Diagram
                  [ Audio Sources ]
                        |
      +-----------------+-----------------+
      |                                   |
      v                                   v
[File Watcher]                  [Shared System Audio Stream]
      |                                   |
      v                                   v
[Batch Queue]             [1. Wake Word Detection Stage (Low CPU)]
      |                       (Listens with Wake Word Engine)
      |                                   |
      +-----------------+         [Wake Word Detected!]
                        |                 |
                        v                 v
          [2. Active Transcription Stage]
                        |
            [Speech-to-Text Service API]
                        |
            [Finalized Transcript Snippet]
                        |
         +--------------+---------------+
         |                              |
         v                              v
[A. Command Mapper & Executor]     [B. Output Formatter]
(Checks against Whitelist)         (For Display/Logging)
         |                              |
   [Execute Command]              [Save/Stream Output]

## 5. Detailed Design ⚙️
#### 5.1. Audio Input and Sharing Strategy
To avoid conflicts with other applications, the daemon must not claim exclusive access to the audio device.

Mechanism:

On Windows: Utilize the Windows Audio Session API (WASAPI) in Shared Mode.

On Linux: Leverage PulseAudio or PipeWire to tap into the default source's "monitor" stream.

On macOS: Use the Core Audio API, which is inherently designed for multi-app audio routing.

#### 5.2. Mode 1: Microphone Input
Stage 1: Wake Word Detection
This is the default, always-on, low-power state.

Wake Word Engine: Integrates a lightweight engine like Picovoice Porcupine that supports custom, user-defined wake word models.

Process: Audio frames are captured and passed only to the local Wake Word Engine. The audio is immediately discarded. No data is sent over the network, ensuring privacy and low resource usage.

Stage 2: Active Transcription
Upon wake word detection, the daemon transitions to this active state.

Process Flow: Audio is now buffered and streamed to the main Speech-to-Text (STT) service. As the STT service returns finalized text segments, the text is sent to two components in parallel: the Command Mapper and the Output Formatter.

Stopping Transcription: The daemon returns to the Wake Word Detection stage upon a "stop phrase", a configurable silence timeout, or an API call.

Component A: Command Mapper and Executor
Mapping: Takes the finalized text and performs a case-insensitive, exact match against the whitelisted power_words in the configuration.

Execution: If a match is found, the corresponding command string is passed to the Command Executor, which spawns a new process with user-level privileges. The result is logged.

Component B: Output Formatter
Takes all transcribed text (commands and dictation) and formats it as .txt, .srt, or JSON for display in the console or saving to a file.

#### 5.3. Mode 2: File-Based (Batch) Input
File Watcher: Monitors a designated directory for new audio files using an efficient file system event listener (e.g., inotify).

Queueing: When a new file is detected, a job is placed on a message queue.

Processing: A worker pulls the job, sends the entire file to the configured STT service, and passes the result to the Output Formatter to be saved to the designated output directory.

## 6. Configuration 📋
A single config.yaml file controls the daemon's behavior, including the new power_words section.

Example config.yaml:

```YAML
# 'file' for batch mode, 'microphone' for real-time mode
source_mode: microphone

# --- BATCH FILE MODE SETTINGS ---
file_watcher:
  watch_directory: /path/to/my/audio/files
  output_directory: /path/to/transcripts

# --- MICROPHONE MODE SETTINGS ---
microphone:
  # Index of the audio device to use. null for default.
  device_index: null

wake_word:
  engine: picovoice
  # Path to the user-defined model file (e.g., my-wake-word.ppn)
  model_path: /path/to/wakeword.ppn
  # Stop transcription after this many seconds of silence
  silence_timeout: 15
  # A phrase that, when spoken, will stop the transcription
  stop_phrase: "stop listening"

# New section for voice commands.
# Disabled by default for security.
power_words:
  enabled: true
  mappings:
    # Phrase to speak: "Command to execute"
    "open browser": "firefox"
    "open my notes": "obsidian"
    "lock the screen": "loginctl lock-session" # Example for Linux
    "show me the weather": "curl wttr.in"
    "list my projects": "ls -la ~/Projects"

# --- GENERAL TRANSCRIPTION SETTINGS ---
transcription:
  provider: google_speech # or whisper, aws_transcribe
  language: en-US

output:
  format: txt
  # For 'microphone' mode, controls if the live transcript is also saved
  log_to_file: true
  log_file_path: /path/to/live_transcript.log
```

## 7. API and Monitoring 📡
A simple REST API is exposed for control and monitoring.

`GET /status`: Returns the daemon's current state (listening_for_wake_word, transcribing, processing_batch, idle).

`POST /start_transcription`: Manually forces the daemon into active transcription mode.

`POST /stop_transcription`: Manually stops transcription and returns to the wake word listening state.

`POST /reload_wakeword`: Reloads the wake word engine with a new model from the config file.

`GET /jobs/{job_id}`: (Batch mode) Returns the status of a specific file transcription job.
