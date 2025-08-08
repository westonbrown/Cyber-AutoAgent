# Terminal Frontend Architecture

## Overview

The Cyber-AutoAgent terminal frontend provides a modern, React-based command-line interface that transforms traditional cybersecurity assessment execution into an interactive, real-time experience. Built with React Ink and TypeScript, it delivers professional-grade terminal UI components while maintaining full compatibility with standard CLI operations.

## Architecture Components

### Core Technologies

- **React Ink**: Terminal-based React renderer for building command-line interfaces
- **TypeScript**: Type-safe development with comprehensive interface definitions
- **Zustand**: Lightweight state management for terminal application state
- **Ink Components**: Specialized terminal UI components (spinners, progress bars, tables)

### Frontend Structure

```
src/modules/interfaces/react/
├── src/
│   ├── components/           # Reusable UI components
│   │   ├── AgentStatus.tsx   # Real-time agent execution status
│   │   ├── MetricsPanel.tsx  # Performance and cost metrics
│   │   ├── OutputViewer.tsx  # Tool output and reasoning display
│   │   └── ProgressBar.tsx   # Operation progress visualization
│   ├── hooks/               # Custom React hooks
│   │   ├── useAgentState.ts # Agent execution state management
│   │   ├── useMetrics.ts    # Metrics collection and display
│   │   └── useWebSocket.ts  # Real-time communication (future)
│   ├── stores/              # State management
│   │   ├── agentStore.ts    # Global agent state
│   │   └── configStore.ts   # Configuration management
│   ├── types/               # TypeScript definitions
│   │   ├── agent.ts         # Agent-related type definitions
│   │   ├── events.ts        # Event system types
│   │   └── metrics.ts       # Metrics and telemetry types
│   ├── utils/               # Utility functions
│   │   ├── eventParser.ts   # Parse backend events
│   │   ├── formatters.ts    # Data formatting utilities
│   │   └── validation.ts    # Input validation helpers
│   ├── App.tsx              # Main application component
│   └── index.ts             # Application entry point
├── package.json             # Dependencies and scripts
├── tsconfig.json           # TypeScript configuration
└── README.md               # Interface-specific documentation
```

## Event-Driven Communication

### Backend Integration

The terminal frontend operates through a sophisticated event-driven architecture that bridges Python backend operations with React components:

#### Event Flow

1. **Python Backend Events**: The Strands SDK and ReactBridgeHandler emit structured events
2. **Event Parsing**: Frontend parses JSON-formatted events from stdout
3. **State Updates**: Events trigger React state updates through Zustand stores
4. **UI Rendering**: Components re-render based on state changes

#### Event Types

```typescript
interface CyberEvent {
  type: 'tool_start' | 'tool_output' | 'reasoning' | 'metrics_update' | 'step_header';
  timestamp: string;
  data: EventData;
}

interface ToolStartEvent {
  type: 'tool_start';
  tool_name: string;
  tool_input: Record<string, any>;
}

interface MetricsUpdateEvent {
  type: 'metrics_update';
  metrics: {
    tokens: number;
    cost: number;
    duration: string;
    memoryOps: number;
    evidence: number;
  };
}
```

### Real-Time Updates

The frontend provides immediate visual feedback for all backend operations:

- **Tool Execution**: Live display of tool invocations with input parameters
- **Agent Reasoning**: Streaming display of agent thought processes
- **Progress Tracking**: Real-time step counters and operation timelines
- **Resource Monitoring**: Live metrics for tokens, costs, and memory operations

## User Interface Components

### Primary Display Areas

#### 1. Operation Header
- Target information and assessment objectives
- Operation ID and timing information
- Overall progress indicators

#### 2. Agent Reasoning Panel
- Streaming display of agent decision-making processes
- Confidence levels and strategic analysis
- Real-time thinking visualization

#### 3. Tool Execution Area
- Tool invocation notifications with parameters
- Live output streaming from security tools
- Error handling and status indicators

#### 4. Metrics Dashboard
- Token usage and API costs
- Memory operations counter
- Evidence collection statistics
- Performance timing metrics

#### 5. Status Bar
- Current operation step and remaining budget
- Agent state indicators
- System health status

### Interactive Elements

#### Command Interface
While primarily displaying automated operations, the frontend supports:
- **Configuration Management**: Interactive setup wizards
- **Operation Control**: Pause/resume capabilities (future enhancement)
- **Manual Intervention**: User input prompts when required

#### Visual Feedback Systems
- **Progress Bars**: Visual representation of operation completion
- **Status Indicators**: Color-coded system states (green/yellow/red)
- **Animation**: Subtle animations for active processes
- **Highlighting**: Important findings and critical information

## State Management

### Global State Architecture

The application uses Zustand for predictable state management:

```typescript
interface AgentState {
  // Operation State
  currentStep: number;
  maxSteps: number;
  operationId: string;
  status: 'idle' | 'running' | 'paused' | 'completed' | 'error';
  
  // Agent Information
  target: string;
  objective: string;
  provider: string;
  
  // Execution Data
  toolExecutions: ToolExecution[];
  reasoningSteps: ReasoningStep[];
  metrics: OperationMetrics;
  
  // UI State
  activeTab: string;
  showAdvanced: boolean;
  filterLevel: 'all' | 'critical' | 'high' | 'medium' | 'low';
}
```

### State Updates

State updates flow through well-defined actions:
- **Event-Driven Updates**: Backend events trigger state mutations
- **Immutable Operations**: All state changes maintain immutability
- **Selective Re-rendering**: Components subscribe only to relevant state slices

## Performance Considerations

### Optimization Strategies

#### 1. Efficient Rendering
- **React.memo**: Memoization of expensive components
- **useMemo/useCallback**: Preventing unnecessary re-computations
- **Virtual Scrolling**: Handling large output streams efficiently

#### 2. Memory Management
- **Event Buffer Limits**: Preventing memory leaks from large event streams
- **Cleanup Routines**: Proper cleanup of subscriptions and timers
- **Lazy Loading**: Components loaded only when needed

#### 3. Real-Time Performance
- **Debounced Updates**: Preventing UI thrashing from rapid events
- **Background Processing**: Non-blocking event parsing
- **Efficient State Updates**: Batched state changes where possible

## Configuration System

**ConfigContext** provides centralized configuration management:

- **Multi-provider Support**: AWS Bedrock, Ollama, LiteLLM
- **Persistent Storage**: `~/.cyber-autoagent/config.json`
- **Environment Integration**: Automatic env var loading
- **Real-time Updates**: Live configuration changes
- **Validation**: Comprehensive settings validation

**Features:**
- Model pricing configuration
- Docker execution settings  
- Observability with Langfuse
- Memory backend selection
- Assessment parameters