# Cyber-AutoAgent Interfaces

> React-based terminal interface for autonomous cybersecurity assessments

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.0+-blue.svg)](https://www.typescriptlang.org/)
[![React Ink](https://img.shields.io/badge/React%20Ink-4.0+-green.svg)](https://github.com/vadimdemedes/ink)

## Overview

Modern terminal UI for Cyber-AutoAgent built with React Ink and TypeScript. Provides real-time streaming of agent operations with comprehensive state management.

## Architecture

```
┌─────────────────────────────────────────────┐
│           React Terminal UI (Ink)           │
├─────────────────────────────────────────────┤
│         Event Bridge & State Management     │
├─────────────────────────────────────────────┤
│      Python Backend (Strands SDK Agent)     │
└─────────────────────────────────────────────┘
```

## Quick Start

```bash
# Python backend
python -m venv venv && source venv/bin/activate
pip install -e .

# React terminal UI
cd src/modules/interfaces/react
npm install && npm start
```

## Project Structure

```
src/modules/interfaces/
├── react/src/
│   ├── components/          # 62 UI components
│   │   ├── ConfigEditor.tsx
│   │   ├── DirectTerminal.tsx
│   │   ├── MainAppView.tsx    
│   │   └── InitializationWrapper.tsx
│   ├── hooks/              # Custom React hooks
│   │   ├── useKeyboardHandlers.ts
│   │   ├── useOperationManager.ts
│   │   └── useApplicationState.ts
│   ├── contexts/           # React contexts
│   ├── types/              # TypeScript definitions
│   └── App.tsx            # Main (205 lines, from 902)
└── python/                # Python UI handlers
```

## Recent Refactoring (Phase 1 Complete)

### App.tsx Simplification
- **Before**: 902 lines monolithic
- **After**: 205 lines + extracted components

| Component | Lines | Purpose |
|-----------|-------|---------|
| `useKeyboardHandlers.ts` | 49 | Keyboard shortcuts |
| `useOperationManager.ts` | 120 | Operation lifecycle |
| `MainAppView.tsx` | 163 | UI rendering |
| `InitializationWrapper.tsx` | 93 | Setup flow |


## Event System

```typescript
interface BaseEvent {
  id: string;
  timestamp: string;
  type: EventType;
  sessionId: string;
  traceId?: string;
}

enum EventType {
  // SDK Native
  AGENT_INITIALIZED,
  REASONING_START,
  REASONING_END,
  
  // Tool Execution
  TOOL_START,
  TOOL_OUTPUT,
  TOOL_END,
  
  // System (20+ more)
  SWARM_START,
  MEMORY_STORE,
  HTTP_REQUEST,
  SHELL_COMMAND
}
```

**Flow**: Python Backend → JSON Event → Parser → React State → UI

## State Management

```typescript
interface ApplicationState {
  // Core
  isConfigLoaded: boolean;
  isInitializationFlowActive: boolean;
  
  // Assessment
  activeOperation: Operation | null;
  operationHistory: OperationHistoryEntry[];
  
  // UI
  terminalDisplayWidth: number;
  modalState: ModalState;
  theme: ThemeConfig;
}
```

**Config Context**: `~/.cyber-autoagent/config.json`
- Multi-provider support (Bedrock, Ollama, LiteLLM)
- Model pricing, Docker settings, Observability
- Memory backend selection

## Key Components

### ConfigEditor
Interactive configuration with validation and env var integration

### DirectTerminal
Main interface with event stream and operation history

### StreamDisplay
Real-time event rendering and tool visualization

### SwarmDisplay
Multi-agent coordination and handoff tracking

## Commands & Shortcuts

```bash
# Assessment
target <url>              # Set target
execute [objective]       # Start assessment

# Configuration
/config                   # View/edit
/provider <name>          # Switch provider
/iterations <n>           # Set max iterations

# Utility
/plugins                  # Select modules
/memory <list|search>     # Memory ops
/health                   # System status
```

**Keyboard**: `Ctrl+C` pause | `Esc` cancel | `Ctrl+L` clear | `Tab` navigate

## Development

```bash
# Run locally
cd src/modules/interfaces/react
npm start                 # Dev mode
npm run build            # Production
npm test                 # Tests

# Code quality
npm run typecheck && npm run lint
pylint src/ && black src/ && mypy src/
```

## Configuration

### Environment Variables
```bash
AWS_REGION=us-east-1
AWS_BEARER_TOKEN_BEDROCK=<token>
OLLAMA_HOST=http://localhost:11434
LANGFUSE_HOST=http://localhost:3000
CYBER_THEME=retro
```

### Config Structure
```json
{
  "modelProvider": "bedrock",
  "modelId": "claude-sonnet-4",
  "iterations": 100,
  "observability": true,
  "deploymentMode": "full-stack"
}
```

## Performance

- Event debouncing
- React.memo memoization
- Lazy loading
- Buffer limits
- State batching

## Security

- Dual confirmation for assessments
- Strict input validation
- Complete audit logs
- Environment-based credentials

## Deployment Modes

1. **Local CLI** - Direct Python
2. **Single Container** - Docker isolated
3. **Full Stack** - With Langfuse monitoring

## Contributing

1. Fork → 2. Feature branch → 3. Tests → 4. PR

**Standards**: TypeScript strict | Python type hints | >80% coverage

## Roadmap

**Near**: WebSocket | Accessibility | Performance

**Future**: Web dashboard | Mobile | Cloud native | SIEM/SOAR

## License

MIT - see [LICENSE](LICENSE)

## Support

Docs: `docs/` | Issues: GitHub | Security: SECURITY.md

---

**Built for the cybersecurity community**