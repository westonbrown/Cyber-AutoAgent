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
│   └── App.tsx            # Main 
└── python/                # Python UI handlers
```

## Event Flow Architecture

```
Python Backend (Strands SDK) 
    ↓ tool execution
ReactBridgeHandler 
    ↓ emits structured events
StreamDisplay.tsx 
    ↓ renders UI
Terminal Interface
```

## Event Types & Display Patterns

### Tool Start Events (`tool_start`)

Every tool execution begins with a `tool_start` event that shows the tool name and parameters.

**Event Structure:**
```json
{
  "type": "tool_start",
  "tool_name": "tool_name",
  "tool_input": { /* parameters */ }
}
```

## Tool Display Patterns

### Core Security Tools (Hardcoded Formatters)

These tools have dedicated display formatters in `StreamDisplay.tsx`:

#### `mem0_memory` - Memory Operations
```
tool: mem0_memory
├─ action: storing
└─ content: Evidence from vulnerability scan...
```
**Parameters:** `action` (list/store/retrieve), `content`/`query`

#### `shell` - Command Execution  
```
tool: shell
⎿ curl -s http://target.com/robots.txt
⎿ nmap -sV target.com
```
**Display:** Tool name only, commands shown via separate `command` events

#### `http_request` - HTTP Operations
```
tool: http_request
├─ method: GET
└─ url: https://target.com/api/endpoint
```
**Parameters:** `method`, `url`

#### `swarm` - Multi-Agent Operations
```
tool: swarm
├─ agents: 3
└─ task: Comprehensive security assessment of target...
```
**Parameters:** `agents`/`num_agents`, `task`/`objective`

#### `python_repl` - Code Execution
```
tool: python_repl
├─ code:
│  import requests
│  response = requests.get("http://target.com")
│  print(response.status_code)
└─ ... (2 more lines)
```
**Parameters:** `code` (shows first 5 lines, truncates if longer)

#### `report_generator` - Report Creation
```
tool: report_generator
├─ target: testphp.vulnweb.com
└─ type: security_assessment
```
**Parameters:** `target`, `report_type`/`type`

#### `file_write` - File Operations
```
tool: file_write
├─ path: /tmp/scan_results.txt
└─ size: 1024 chars
```
**Parameters:** `path`, `content` (shown as size)

#### `editor` - File Editing
```
tool: editor
├─ command: edit
├─ path: /config/settings.conf
└─ size: 512 chars
```
**Parameters:** `command`, `path`, `content`

#### `think` - Agent Reasoning
```
tool: think
└─ I need to analyze the scan results to identify...
```
**Parameters:** `thought`/`thinking`/`content`/`text`

#### `load_tool` - Dynamic Tool Loading
```
tool: load_tool
├─ loading: custom_scanner
├─ path: /tools/custom_scanner.py
└─ description: Custom vulnerability scanner
```
**Parameters:** `tool_name`/`tool`, `path`, `description`

#### `stop` - Execution Control
```
tool: stop
└─ reason: Assessment complete, all objectives met
```
**Parameters:** `reason`

#### `handoff_to_agent` - Agent Handoffs
```
tool: handoff_to_agent
├─ target: vulnerability_analyst
└─ message: Found 5 potential issues, please analyze...
```
**Parameters:** `agent`/`target_agent`, `message`

### Unknown/Dynamic Tools (Generic Pattern)

For tools not in the hardcoded list (like `quick_recon`, `nmap`, `nikto`, etc.):

#### Phase 1: Tool Announcement
```
tool: quick_recon
```
Shows just the tool name, no parameters displayed initially.

#### Phase 2: Parameter Display (via metadata event)
```
├─ target: testphp.vulnweb.com
├─ scan_type: comprehensive
└─ timeout: 300
```
Parameters come from subsequent `metadata` event emitted by `_emit_generic_tool_params` in the ReactBridgeHandler.

**Implementation:** Unknown tools fall through to the `default` case in `StreamDisplay.tsx` which shows only the tool name. The `ToolEventEmitter` then calls `_emit_generic_tool_params()` which emits a `metadata` event with the parameters.

## Complete Event Sequence for Tool Execution

### 1. Step Header (if new step)
```
[STEP 2/10] ────────────────────────────────────────
```

### 2. Reasoning (if agent is thinking)
```
reasoning
Based on the previous scan results, I need to perform...
```

### 3. Tool Start
```
tool: quick_recon
```

### 4. Tool Parameters (for unknown tools, via metadata)
```
├─ target: testphp.vulnweb.com
└─ depth: full
```

### 5. Thinking Animation (while tool executes)
```
⠋ Executing [3s]
```

### 6. Command Events (for shell tools)
```
⎿ nmap -sV -sC target.com
```

### 7. Output Events
```
output
  Quick Reconnaissance Results for testphp.vulnweb.com
  ============================================================
  
  ✓ DNS Resolution: testphp.vulnweb.com → 44.228.249.3
  ...
```

## Special Event Types

### Swarm Operations
```
[SWARM] Multi-Agent Operation Starting
Agents (3):
  • Security Scanner Agent
  • Vulnerability Analyst Agent  
  • Report Generator Agent
Task: Comprehensive security assessment...

[HANDOFF] Agent Handoff
Security Scanner Agent → Vulnerability Analyst Agent
Message: Found 5 potential vulnerabilities, analyzing...

[SWARM] Operation Complete
Final Agent: Report Generator Agent
Total Handoffs: 2
```

### User Handoffs
```
AGENT REQUESTING USER INPUT
┌─────────────────────────────────────────────┐
│ Please confirm if you want to proceed with  │
│ the SQL injection test on the login form.   │
└─────────────────────────────────────────────┘
Please provide your response in the input below:
```

### Error Display
```
[ERROR]
  Connection timeout when accessing target.com:443
```

### SDK Native Events

#### Model Invocation
```
model invocation started
Model: us.anthropic.claude-sonnet-4-20250514-v1:0
```

#### Tool Invocation (SDK Format)
```
tool: http_request
├─ method: POST
├─ url: https://api.example.com/data
├─ headers: {"Content-Type": "application/json"}
└─ body: {"query": "test"}
```

#### Metrics Updates
```
Tokens: 1250 in / 890 out | Cost: $0.0125
```

## Animation States

The ThinkingIndicator component shows different contexts:

- **Analyzing**: `⠋ Analyzing [5s]` 
- **Executing**: `⠋ Executing [12s]`
- **Waiting**: `⠋ Waiting for response [3s]`
- **Initializing**: `⠋ Initializing [2s]`
- **Preparing**: `⠋ Preparing tools [1s]`

**Animation Implementation:** Uses `ink-spinner` with automatic timing updates. No static `startTime` props are passed to prevent frozen animations.

## Key Design Principles

1. **No Hardcoding for New Tools**: Unknown tools get generic display + metadata events
2. **Tree Structure**: Parameters use `├─` and `└─` for visual hierarchy  
3. **Content Truncation**: Long values truncated at 50 chars with `...`
4. **Event-Driven**: Everything comes from backend events, no frontend assumptions
5. **Consistent Timing**: All animations update every second
6. **Clean Commands**: Shell commands parsed from JSON to show clean text
7. **Upstream Event Flow**: Follow the ReactBridgeHandler → ToolEventEmitter → StreamDisplay chain

## Tool Categories

### Core Tools (Hardcoded Formatters)
- `mem0_memory`, `shell`, `http_request`, `swarm`, `python_repl`
- `report_generator`, `file_write`, `editor`
- `think`, `load_tool`, `stop`, `handoff_to_agent`

### Security Tools (Generic Display)
- `nmap`, `nikto`, `sqlmap`, `gobuster`, `metasploit`
- `tcpdump`, `netcat`, `curl` (when not via shell)

### Custom Tools (Generic Display)  
- `quick_recon`, `identify_technology`
- Any dynamically loaded tools via `load_tool`

### SDK Tools (Native Event Handling)
- `model_invocation_start`, `tool_invocation_start/end`
- `content_block_delta`, `reasoning_delta`
- `metrics_update`, `event_loop_cycle_start`

## File Structure

```
src/modules/interfaces/react/src/components/
├─ StreamDisplay.tsx           # Main display component
├─ ThinkingIndicator.tsx      # Animation component
└─ SwarmDisplay.tsx           # Swarm operation display

src/modules/handlers/react/
├─ react_bridge_handler.py    # Event emission from SDK
└─ tool_emitters.py          # Tool-specific event emission

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