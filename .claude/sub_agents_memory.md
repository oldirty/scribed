# Sub-Agent Memory and Knowledge Base

## Purpose
This file serves as a shared knowledge base for context related to sub-agent usage, decisions, and any special context sub-agents wish to convey to the main LLM. Sub-agents MUST explicitly add memories here to ensure knowledge continuity across sessions.

## Usage Guidelines for Sub-Agents
When you (as a sub-agent) discover important context, make decisions, or learn something valuable that would benefit the main LLM or other sub-agents, you MUST add it to this file. Focus on:

- **Hard-won knowledge** that's not obvious from reading code
- **Important decisions** and the reasoning behind them  
- **Project-specific quirks** or gotchas discovered during work
- **Cross-agent coordination** information
- **Context about failed approaches** to avoid repeating mistakes
- **Domain-specific insights** relevant to your expertise area

## Sub-Agent Operations Log

### Project Context Discovered
- **Project Type**: Python transcription service (Scribed) - Advanced audio transcription with voice activation
- **Primary Technologies**: Python 3.10+, FastAPI, OpenAI Whisper, Picovoice Porcupine, sounddevice, librosa
- **Key Features**: Real-time transcription, wake words, power words (secure command execution), audio preprocessing
- **Architecture**: Clean modular design with separate audio sources, transcription engines, output handlers, and core orchestration
- **Security Focus**: Power words feature disabled by default due to command execution risks
- **Cross-Platform**: Windows, Linux, macOS support with platform-specific audio handling
- **Optional Dependencies**: Whisper (local), OpenAI API, wake word detection, audio processing enhancements

### Sub-Agent Team Created (12 Specialists)

#### Core Technical Specialists
1. **audio-processing-expert** (opus, Think Hard)
   - 20+ years real-time audio systems, signal processing, acoustics
   - Triggers: audio processing, noise reduction, microphone input issues
   - Expertise: sounddevice, librosa, scipy.signal, cross-platform audio

2. **ml-transcription-specialist** (opus, Think Hard)  
   - 15+ years ASR, Whisper optimization, multi-language transcription
   - Triggers: transcription accuracy, model selection, speech recognition issues
   - Expertise: OpenAI API, Whisper models, transformer architectures

3. **realtime-systems-architect** (opus, Think Harder)
   - 18+ years low-latency systems, streaming applications, high-performance computing
   - Triggers: performance bottlenecks, latency optimization, concurrent processing
   - Expertise: memory pools, lock-free structures, sub-millisecond timing

4. **python-async-expert** (sonnet, Think)
   - 12+ years asyncio, FastAPI, concurrent Python applications  
   - Triggers: async issues, FastAPI optimization, concurrent programming
   - Expertise: event loop management, async/await patterns, high-performance web services

5. **security-privacy-auditor** (opus, Think Hard)
   - 16+ years application security, privacy compliance, secure audio processing
   - Triggers: security reviews, privacy assessment, command execution analysis
   - Expertise: command injection prevention, audio data protection, OWASP frameworks

#### Configuration & DevOps Specialists  
6. **config-deployment-specialist** (sonnet, Think)
   - 14+ years Python deployment, configuration management, cross-platform delivery
   - Triggers: configuration validation, deployment troubleshooting, compatibility issues
   - Expertise: YAML design, setuptools/pip, virtual environments, automation

7. **integration-testing-expert** (sonnet, Think)
   - 13+ years audio system testing, async Python testing, integration automation
   - Triggers: test strategy, async testing challenges, audio verification
   - Expertise: pytest frameworks, mock strategies, audio testing methodologies

#### Quality Assurance & Critics (Fresh Eyes Assessment)
8. **code-architecture-reviewer** (opus, Think Hard)
   - 18+ years clean architecture, design patterns, code quality assessment
   - Triggers: architecture reviews, design analysis, technical debt evaluation
   - Expertise: SOLID principles, Python architectural patterns, dependency injection

9. **performance-optimization-critic** (opus, Think Harder)
   - 16+ years system optimization, profiling, performance analysis
   - Triggers: performance reviews, resource utilization, optimization analysis
   - Expertise: Python tuning, memory optimization, real-time constraints

10. **security-compliance-auditor** (sonnet, Think)
    - 14+ years security standards, regulatory compliance, systematic auditing
    - Triggers: compliance reviews, security standard validation, systematic audits
    - Expertise: OWASP Top 10, SOC 2, ISO 27001, automated security scanning

#### Project Management & Coordination
11. **audio-project-planner** (sonnet, Think)
    - 15+ years audio technology project management, feature planning, roadmap management
    - Triggers: project planning, feature roadmap, technical strategy decisions
    - Expertise: audio product strategy, transcription technology evolution, prioritization

12. **memory-manager** (sonnet, Think)
    - 12+ years knowledge management, context curation, cross-functional coordination
    - Triggers: memory curation, context management, cross-agent coordination
    - Expertise: knowledge base management, context sharing, team coordination

### Important Decisions Made
- **Sub-Agent Architecture**: Implemented 12 specialized agents with clear separation of concerns and minimal tool access (No Direct Code Modification policy)
- **Model Selection Strategy**: Used opus for complex analysis (audio, ML, real-time, security, architecture) and sonnet for structured tasks (async, config, testing, compliance, planning, memory)
- **Thinking Budget Allocation**: Applied Think Hard/Harder for complex domains requiring deep analysis, standard Think for well-defined structured tasks
- **Security-First Approach**: Dual security coverage with security-privacy-auditor (implementation focus) and security-compliance-auditor (standards focus)
- **Critic Agent Strategy**: Implemented multiple "fresh eyes" critics for unbiased assessment (architecture, performance, security compliance)

### Cross-Agent Coordination Notes
- **Memory Management**: memory-manager coordinates cross-agent findings and maintains knowledge base
- **Security Coverage**: Two security agents with different perspectives ensure comprehensive coverage
- **Performance Focus**: realtime-systems-architect handles system-level optimization, performance-optimization-critic provides fresh analytical perspective
- **Testing Strategy**: integration-testing-expert focuses on audio-specific testing challenges and async patterns

### Known Issues and Workarounds
- **Power Words Security**: Feature disabled by default due to command execution risks - requires security-privacy-auditor review before enabling
- **Cross-Platform Audio**: Platform-specific audio handling requires audio-processing-expert analysis for compatibility
- **Real-time Constraints**: <50ms latency requirements need realtime-systems-architect optimization
- **Model Selection**: Whisper vs OpenAI API trade-offs require ml-transcription-specialist evaluation

### Consolidated Refactoring Analysis (Latest)

#### Project Simplification Initiative - Key Findings
- **Current State**: 19,494 LOC across 40 source files - significantly over-engineered
- **Complexity Assessment**: Multiple experimental features adding complexity without clear value
- **Performance Analysis**: Good foundations but 3-5x improvement opportunities identified
- **Target Reduction**: 53% LOC reduction (to ~9,000 lines) while improving performance

#### Architecture Analysis Results
**Critical Complexity Drivers**:
- Real-time transcription service: 1000+ lines in single file with complex async management
- SpeechLM2 integration: 800+ LOC experimental feature with minimal value
- Test file sprawl: 2000+ LOC in scattered test files indicating historical instability
- Multiple TTS implementations: 500+ LOC of duplicate functionality
- Audio preprocessing complexity: Advanced features that may not be needed for core use cases

**Performance Bottlenecks Identified**:
- Memory allocation patterns in audio processing pipeline
- Inefficient async queue management in real-time service
- Multiple format conversions in audio chain
- Complex startup sequence with unnecessary dependencies
- Session management overhead for simple transcription tasks

#### Consolidated Implementation Strategy
**Three-Phase Approach**:
1. **Phase 1 (Safe Cleanup)**: Remove experimental features, consolidate tests, clean docs - 3,600 LOC reduction (18.5%)
2. **Phase 2 (Performance)**: Refactor real-time service, optimize audio pipeline - 1,050 LOC reduction + 3-5x performance gains
3. **Phase 3 (Architecture)**: Simplify core engine, streamline configuration - 1,000 LOC reduction + maintainability improvements

#### Risk Assessment and Mitigation
**Low Risk Items** (Phase 1):
- SpeechLM2 removal: Experimental, no core functionality impact
- Test consolidation: Improves rather than risks stability
- Documentation cleanup: Pure maintenance benefit

**Medium Risk Items** (Phase 2):
- Real-time service refactor: Core functionality but clear performance benefits
- Audio pipeline optimization: Careful testing required

**Higher Risk Items** (Phase 3):
- Engine core changes: Require extensive compatibility testing
- Configuration changes: May impact existing deployments

#### Success Metrics Established
**Code Metrics**: 53% LOC reduction, 37% file count reduction, 40% complexity reduction
**Performance Targets**: 3x startup speed, 2x memory efficiency, 3x latency improvement, 4x throughput increase
**Quality Improvements**: Higher test coverage, unified documentation, reduced error rates

#### Team Coordination Plan
- **Phase 1**: code-architecture-reviewer, dependency-auditor, test-consolidator
- **Phase 2**: performance-optimization-critic, concurrency-specialist, memory-profiler
- **Phase 3**: design-pattern-specialist, api-designer, integration-tester
- **Cross-Phase**: memory-manager (coordination), quality-assurance, documentation-writer

#### Implementation Timeline
6-week timeline with 1-week validation phase, each phase building on previous achievements

---
*This file is automatically maintained by the Astraeus Σ-9000 sub-agent system*