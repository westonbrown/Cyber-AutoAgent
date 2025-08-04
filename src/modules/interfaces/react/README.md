# Cyber-AutoAgent React CLI

A minimal terminal interface for Cyber-AutoAgent that provides direct streaming of Python agent output without parsing or interpretation.

## Overview

This React-based CLI wraps the Python Cyber-AutoAgent implementation, providing:
- Simple module → target → objective flow
- Direct output streaming from Python Docker container
- No parsing or interpretation of agent output
- Minimal UI inspired by Claude Code and Gemini CLI
- Elegant ASCII logo with real-time status indicators
- Slash commands for quick configuration access

## Architecture

```
┌─────────────────────┐
│   React CLI (Ink)   │
│  ┌───────────────┐  │
│  │ AssessmentFlow│  │  State machine for module/target/objective
│  └───────┬───────┘  │
│          │          │
│  ┌───────▼───────┐  │
│  │ DockerService │  │  Spawns Python CLI in Docker
│  └───────┬───────┘  │
└──────────┼──────────┘
           │
    ┌──────▼──────┐
    │   Docker    │
    │ ┌─────────┐ │
    │ │ Python  │ │     Actual agent execution
    │ │  Agent  │ │
    │ └─────────┘ │
    └─────────────┘
```

## Installation

```bash
# Install dependencies
npm install

# Build TypeScript
npm run build

# Run the CLI
npm start
```

## Usage

### Interactive Mode

```bash
# Start interactive CLI
cyber-react

# Flow:
# 1. Load a module
module general

# 2. Set target
target example.com

# 3. Set objective (or press Enter for default)
SQL injection testing

# 4. Press Enter to start assessment
```

### Direct Execution

```bash
# Run assessment directly with CLI arguments
cyber-react --module general --target example.com --objective "SQL injection testing"
```

### Available Commands

- `module <name>` - Load a security module
- `target <url|ip>` - Set assessment target
- `help` - Show context-aware help
- `clear` - Clear terminal
- `reset` - Reset assessment flow
- `exit` - Exit application

### Slash Commands

- `/module <name>` - Quick module loading
- `/target <url|ip>` - Quick target setting
- `/config` - Open configuration editor
- `/memory` - Search past assessments
- `/help` - Show all commands
- `/clear` - Clear screen
- `/exit` - Exit application

## Modules

Available modules are dynamically loaded from `/app/modules`:
- `general` - General security assessment

## Configuration

First-time setup will guide you through provider configuration:
- AWS Bedrock (recommended)
- Ollama (local)
- LiteLLM (universal)

Configuration is stored in `~/.cyber-autoagent/config.json`

### Configuration Options

- **Model Provider**: bedrock, ollama, litellm
- **Model ID**: Specific model to use
- **AWS Region**: For Bedrock provider
- **Iterations**: Maximum assessment iterations (1-100)
- **Memory Mode**: auto or fresh
- **Max Threads**: Thread limit for parallel operations
- **Auto Approve**: Skip tool confirmation prompts
- **Verbose**: Enable debug output

## Development

### Project Structure

```
src/
├── App.tsx                    # Main application component
├── index.tsx                  # CLI entry point
├── components/
│   ├── Terminal.tsx          # Output display
│   ├── Prompt.tsx            # Input handling
│   ├── MainScreen.tsx        # Main UI with logo
│   ├── WelcomeScreen.tsx     # Welcome screen
│   ├── ConfigEditor.tsx      # Configuration UI
│   └── MemorySearch.tsx      # Memory browser
├── services/
│   ├── AssessmentFlow.ts     # State machine
│   ├── DockerService.ts      # Docker execution
│   └── MemoryService.ts      # Memory interface
└── types/
    └── Assessment.ts         # TypeScript interfaces
```

### Key Design Decisions

1. **No Output Parsing**: All Python output streams directly to terminal
2. **Minimal State**: Only tracks module/target/objective flow
3. **Docker Execution**: Uses spawn() for real-time streaming
4. **Simple Commands**: No complex parsing, just basic commands
5. **Split View**: Main screen remains visible with terminal output below
6. **Slash Commands**: Quick access inspired by modern CLI tools
7. **No Target Sanitization**: Accept any user input without validation

### Testing

```bash
# Run all tests
npm test

# Run tests in watch mode
npm run test:watch

# Generate coverage report
npm run test:coverage
```

## Environment Variables

The CLI passes these to the Python Docker container:
- `CYBERAGENT_MODULE` - Selected module
- `CYBERAGENT_MODULE_PATH` - Module directory path
- `AWS_REGION` - AWS region for Bedrock
- `PYTHONUNBUFFERED=1` - Ensure real-time output
- `FORCE_COLOR=1` - Preserve ANSI colors

## Troubleshooting

### Docker not found
Ensure Docker is installed and running:
```bash
docker --version
```

### No modules found
Verify modules are mounted correctly:
```bash
ls /app/modules
```

### Assessment not starting
Check Docker logs:
```bash
docker logs cyber-assessment-*
```

## Contributing

1. Keep the UI minimal - no complex features
2. Don't parse Python output - let it stream
3. Test all changes with actual Python agent
4. Follow existing code style

## License

See main project LICENSE file.