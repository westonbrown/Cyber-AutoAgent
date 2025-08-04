# Cyber-AutoAgent Interfaces

> Modern, event-driven interfaces for autonomous cybersecurity assessment tools

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.0+-blue.svg)](https://www.typescriptlang.org/)
[![Strands SDK](https://img.shields.io/badge/Strands-SDK%201.0.1-green.svg)](https://strandsagents.com/)

## Overview

This project provides professional-grade interfaces for cybersecurity assessment agents built on the Strands SDK. It features a React-based terminal UI that streams real-time agent operations, tool executions, and security findings in a clean, enterprise-ready format.

## Architecture

```mermaid
graph TB
    subgraph "Frontend Layer"
        A[Terminal UI<br/>React Ink + TypeScript]
        B[CLI Interface<br/>Python Click]
        C[Web Dashboard<br/>Future: Next.js]
    end
    
    subgraph "Event Bridge"
        D[Event Parser<br/>JSON + Delimiters]
        E[State Manager<br/>Zustand Store]
        F[Stream Handler<br/>Real-time Updates]
    end
    
    subgraph "Agent Layer"
        G[Strands Agent<br/>SDK Components]
        H[Tool Suite<br/>15 Security Tools]
        I[Event Handlers<br/>SDK Callbacks]
    end
    
    A --> D
    B --> D
    C --> D
    D --> E
    E --> F
    F --> G
    G --> H
    H --> I
    I --> D
```

## Quick Start

### Prerequisites
- **Node.js** 18.0+ and **Python** 3.11+
- **Docker** 24.0+ (for containerized execution)
- **TypeScript** 5.0+ and **React** 18+

### Installation
```bash
# Clone and setup
git clone <repository-url>
cd cyber-autoagent

# Backend setup
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -e .

# Frontend setup (Terminal UI)
cd src/modules/interfaces/react
npm install
npm run build
```

### Basic Usage
```bash
# Direct CLI execution
python src/cyberautoagent.py \
  --target example.com \
  --objective "Security assessment" \
  --provider bedrock

# React Terminal UI
cd src/modules/interfaces/react
npm start -- --target example.com --objective "Security assessment"
```

## Event System

### Event Flow Sequence

```mermaid
sequenceDiagram
    participant Agent as Strands Agent
    participant Handler as Event Handler
    participant Parser as Event Parser
    participant UI as Terminal UI
    
    Agent->>Handler: Tool execution starts
    Handler->>Parser: Emit JSON event
    Note over Parser: __CYBER_EVENT__{"type":"tool_start"}__CYBER_EVENT_END__
    Parser->>UI: Parsed event object
    UI->>UI: Update component state
    
    Agent->>Handler: Tool output stream
    Handler->>Parser: Emit output event
    Parser->>UI: Streaming data
    UI->>UI: Display real-time output
    
    Agent->>Handler: Tool completion
    Handler->>Parser: Emit completion event
    Parser->>UI: Final results
    UI->>UI: Update metrics & progress
```

### Event Types

```typescript
interface CyberEvent {
  type: 'step_header' | 'reasoning' | 'tool_start' | 'tool_output' | 
        'error' | 'metrics_update' | 'user_handoff' | 'completion';
  timestamp: string;
  data: EventData;
}
```

### State Management Flow

```mermaid
flowchart LR
    A[Raw Event Stream] --> B[Event Parser]
    B --> C{Event Type?}
    
    C -->|reasoning| D[Reasoning Buffer]
    C -->|tool_start| E[Tool State]
    C -->|tool_output| F[Output Display]
    C -->|metrics| G[Performance Metrics]
    
    D --> H[Aggregated Reasoning]
    E --> I[Tool Execution UI]
    F --> J[Live Output Stream]
    G --> K[Cost & Performance]
    
    H --> L[React State Update]
    I --> L
    J --> L
    K --> L
    
    L --> M[UI Re-render]
```

## Interface Types

### Terminal UI (Production Ready)
**Stack**: React Ink, TypeScript, Zustand

Features:
- Real-time agent reasoning display
- Tool execution with argument preview
- Professional security assessment workflows  
- Metrics tracking (tokens, costs, performance)
- Multi-theme support

**Key Components**:
```typescript
interface TerminalComponents {
  App: 'Main orchestrator with global state';
  StreamDisplay: 'Real-time event renderer';
  MetricsPanel: 'Performance monitoring';
  ToolDisplay: 'Tool execution visualization';
}
```

### CLI Interface (Core)
**Stack**: Python Click, Rich formatting

Features:
- Direct agent execution
- Scriptable operations for automation
- CI/CD pipeline integration
- JSON output modes

## Tool Integration

### Supported Tools (15 total)

The interface provides complete transparency for all security tools:

```mermaid
mindmap
  root((Security Tools))
    SDK Built-in
      shell
      http_request
      python_repl
      editor
      swarm
      think
      load_tool
      stop
    Cybersecurity
      mem0_memory
      handoff_to_user
      report_generator
    Custom Extensions
      vulnerability_scanner
      evidence_collector
```

### Tool Display Pattern

All tools follow a consistent visualization:

```
reasoning
[Agent's decision-making process]

[STEP N/M] operation_id • duration ────────────────

tool: tool_name
[tool-specific parameters and preview]

(●) duration Executing...

output (metadata)
[tool execution results and findings]

──────────────────────────────────────────────────
```

## Development Guide

### Project Structure
```
src/modules/interfaces/
├── react/                  # Terminal UI components
│   ├── src/components/     # React components
│   ├── src/hooks/         # Custom hooks
│   ├── src/types/         # TypeScript definitions
│   └── src/utils/         # Utility functions
├── cli/                   # Native CLI interface
└── shared/                # Common interface utilities
```

### Event Handler Development

```python
from strands.handlers import PrintingCallbackHandler

class CustomInterfaceHandler(PrintingCallbackHandler):
    """Extends SDK handler for UI integration"""
    
    def __call__(self, **kwargs):
        # Process SDK callbacks
        event = self.transform_event(kwargs)
        self.emit_to_ui(event)
    
    def emit_to_ui(self, event: Dict[str, Any]) -> None:
        """Emit structured event for UI consumption"""
        event_json = json.dumps(event)
        print(f"__CYBER_EVENT__{event_json}__CYBER_EVENT_END__")
```

### Component Development

```typescript
import React from 'react';
import { Box, Text } from 'ink';

export const ToolDisplay: React.FC<{execution: ToolExecution}> = ({ 
  execution 
}) => (
  <Box flexDirection="column" marginY={1}>
    <Text color="cyan">tool: {execution.toolName}</Text>
    {execution.parameters && (
      <Box marginLeft={2}>
        <Text color="gray">
          {Object.entries(execution.parameters)
            .map(([k, v]) => `${k}: ${v}`)
            .join(' | ')}
        </Text>
      </Box>
    )}
    {execution.output && (
      <Text color="white">{execution.output}</Text>
    )}
  </Box>
);
```

### Testing Framework

```bash
# Component tests
npm test

# Integration tests  
npm run test:integration

# End-to-end tests
npm run test:e2e
```

## Configuration

### Multi-Layer Config System

```mermaid
graph TD
    A[CLI Arguments] --> E[Final Config]
    B[Environment Variables] --> E
    C[User Config ~/.cyber-autoagent/] --> E
    D[System Defaults] --> E
    
    E --> F[Agent Initialization]
    E --> G[UI Configuration]
    E --> H[Tool Settings]
```

### Environment Variables
```bash
# Model configuration
export AWS_REGION=us-east-1
export AWS_ACCESS_KEY_ID=your_key
export OPENAI_API_KEY=your_key

# Interface settings  
export __REACT_INK__=true
export CYBER_THEME=professional
export CYBER_LOG_LEVEL=info
```

## Security Considerations

### Interface Security Model
- **Input Validation**: All user inputs validated against strict schemas
- **Command Injection Prevention**: Parameterized commands and sanitization
- **Audit Logging**: Complete operation and tool execution logs
- **Access Control**: Role-based permissions for sensitive operations

### Compliance Features
- **Data Classification**: Automatic evidence categorization
- **Retention Policies**: Configurable data lifecycle management  
- **Audit Trails**: Comprehensive security event logging
- **Privacy Controls**: GDPR and data protection compliance

## Performance & Scalability

### Optimization Strategies
- **Event Processing**: Debounced updates prevent UI thrashing
- **Memory Management**: Automatic cleanup and buffer limits
- **Connection Pooling**: Efficient AI provider API usage
- **Caching**: Configuration and frequently accessed data

### Monitoring
```typescript
interface PerformanceMetrics {
  eventThroughput: number;     // Events/second
  memoryUtilization: number;   // MB used
  responseLatency: number;     // Average response time
  concurrentOps: number;       // Active operations
}
```

## Contributing

### Development Workflow
1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/amazing-feature`)
3. **Implement** with comprehensive tests
4. **Ensure** all tests pass (`npm test && python -m pytest`)
5. **Submit** a pull request

### Code Standards
- **TypeScript**: Strict mode with comprehensive type coverage
- **Python**: Type hints, docstrings, and PEP 8 compliance
- **Testing**: >90% code coverage for new features
- **Security**: Security review required for all interface changes

### Issue Templates
- **Bug Report**: Detailed reproduction steps and environment info
- **Feature Request**: Clear use case and implementation approach
- **Security Issue**: Private disclosure process for vulnerabilities

## Roadmap

### Near Term (3-6 months)
- **WebSocket Integration**: Real-time bidirectional communication
- **Plugin System**: Custom tool and interface extensions
- **Enhanced Accessibility**: Screen reader and keyboard navigation
- **Performance Optimization**: Faster event processing and rendering

### Medium Term (6-12 months)  
- **Web Dashboard**: Modern browser-based interface
- **Collaboration Features**: Multi-user assessment support
- **Advanced Visualization**: Network topology and attack path diagrams
- **API Documentation**: Comprehensive REST API for integrations

### Long Term (12+ months)
- **Mobile Support**: Responsive interfaces for mobile devices
- **Cloud Native**: Kubernetes operators and cloud deployments
- **AI Enhancement**: ML-powered assessment optimization
- **Ecosystem Integration**: SIEM, SOAR, and security platform connectors

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

- **Documentation**: [docs/](docs/)
- **Issues**: [GitHub Issues](https://github.com/your-org/cyber-autoagent/issues)
- **Discussions**: [GitHub Discussions](https://github.com/your-org/cyber-autoagent/discussions)
- **Security**: [SECURITY.md](SECURITY.md) for vulnerability reports

---

**Built with** ❤️ **for the cybersecurity community**