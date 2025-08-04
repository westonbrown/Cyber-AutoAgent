/**
 * Cyber-AutoAgent Event System - SDK-Aligned Type Definitions
 * 
 * Defines the complete event architecture for real-time streaming communication
 * between the Strands SDK-powered Python backend and React Ink frontend. Provides
 * type-safe interfaces aligned with SDK's native event system and streaming patterns.
 * 
 * Event Architecture:
 * - Native integration with Strands SDK event loop and streaming system
 * - Real-time streaming via SDK's callback handlers and hook system
 * - Type-safe event handling with SDK-compatible discriminated unions
 * - Comprehensive metadata and context preservation using SDK's telemetry
 * - Built-in support for SDK's reasoning, tool execution, and metrics events
 * 
 * Event Categories:
 * - SDK Native Events: model invocations, tool executions, event loop cycles
 * - Streaming Events: content deltas, reasoning streams, performance metrics
 * - Hook Events: before/after invocation patterns from SDK hook system
 * - Legacy Events: backward compatibility with existing React interface
 * - Telemetry Events: cost tracking, performance monitoring, trace correlation
 * 
 * @author Cyber-AutoAgent Team
 * @version 0.2.0 - SDK-Aligned
 * @since 2025-08-02
 */

/**
 * Base Event Interface - Foundation for All Stream Events
 * 
 * Provides the core structure shared by all event types in the system
 * with essential metadata for tracking, correlation, and debugging.
 * Enhanced with SDK-compatible tracing and context preservation.
 */
export interface BaseEvent {
  /** Unique event identifier for correlation and deduplication */
  id: string;
  /** ISO 8601 timestamp of event generation */
  timestamp: string;
  /** Discriminator for event type classification */
  type: EventType;
  /** Session identifier for grouping related events */
  sessionId: string;
  /** Optional trace ID for SDK trace correlation */
  traceId?: string;
  /** Optional span ID for OpenTelemetry integration */
  spanId?: string;
  /** SDK event loop cycle ID if applicable */
  cycleId?: string;
}

/**
 * Event Type Enumeration - Comprehensive Event Classification System
 * 
 * Defines all possible event types in the Cyber-AutoAgent system with
 * consistent naming conventions and logical grouping for efficient
 * event handling and UI rendering.
 */
export enum EventType {
  // =============================================================================
  // SDK NATIVE EVENTS - Strands SDK core event system
  // =============================================================================
  /** SDK model invocation started */
  MODEL_INVOCATION_START = 'model_invocation_start',
  /** SDK model invocation completed */
  MODEL_INVOCATION_END = 'model_invocation_end',
  /** SDK model streaming started */
  MODEL_STREAM_START = 'model_stream_start',
  /** SDK model streaming delta content */
  MODEL_STREAM_DELTA = 'model_stream_delta', 
  /** SDK model streaming completed */
  MODEL_STREAM_END = 'model_stream_end',
  /** SDK tool invocation started */
  TOOL_INVOCATION_START = 'tool_invocation_start',
  /** SDK tool invocation completed */
  TOOL_INVOCATION_END = 'tool_invocation_end',
  /** SDK event loop cycle started */
  EVENT_LOOP_CYCLE_START = 'event_loop_cycle_start',
  /** SDK event loop cycle completed */
  EVENT_LOOP_CYCLE_END = 'event_loop_cycle_end',
  /** SDK message added to conversation */
  MESSAGE_ADDED = 'message_added',
  /** SDK agent initialized */
  AGENT_INITIALIZED = 'agent_initialized',
  
  // =============================================================================
  // LEGACY TOOL EXECUTION EVENTS - Backward compatibility
  // =============================================================================
  /** Tool execution initiated with parameters */
  TOOL_START = 'tool_start',
  /** Tool execution producing output or progress */
  TOOL_OUTPUT = 'tool_output',
  /** Tool execution completed successfully */
  TOOL_END = 'tool_end',
  /** Tool execution encountered error */
  TOOL_ERROR = 'tool_error',
  
  // =============================================================================
  // ASSESSMENT WORKFLOW EVENTS - Python backend event system
  // =============================================================================
  /** Assessment step initiated with metadata */
  STEP_START = 'step_start',
  /** Single command execution */
  COMMAND = 'command',
  /** Multiple command batch execution */
  COMMAND_ARRAY = 'command_array',
  /** Command or tool output */
  OUTPUT = 'output',
  /** Status update with level classification */
  STATUS = 'status',
  /** Assessment section banner display */
  BANNER = 'banner',
  /** Assessment section grouping */
  SECTION = 'section',
  /** AI reasoning and thought process */
  REASONING = 'reasoning',
  
  // =============================================================================
  // SPECIALIZED TOOL EVENTS - Specific security assessment tools
  // =============================================================================
  /** Shell command execution initiated */
  SHELL_COMMAND = 'shell_command',
  /** Shell command output streaming */
  SHELL_OUTPUT = 'shell_output',
  /** Shell command error output */
  SHELL_ERROR = 'shell_error',
  
  // =============================================================================
  // MULTI-AGENT COORDINATION EVENTS - Swarm intelligence system
  // =============================================================================
  /** Multi-agent swarm session initiated */
  SWARM_START = 'swarm_start',
  /** Individual agent activity */
  SWARM_AGENT = 'swarm_agent',
  /** Agent handoff with context transfer */
  SWARM_HANDOFF = 'swarm_handoff',
  /** Multi-agent swarm session completed */
  SWARM_END = 'swarm_end',
  
  // =============================================================================
  // NETWORK COMMUNICATION EVENTS - HTTP/API assessment tools
  // =============================================================================
  /** HTTP request initiated */
  HTTP_REQUEST = 'http_request',
  /** HTTP response received */
  HTTP_RESPONSE = 'http_response',
  
  // =============================================================================
  // MEMORY SYSTEM EVENTS - Knowledge management and persistence
  // =============================================================================
  /** Memory storage operation */
  MEMORY_STORE = 'memory_store',
  /** Memory retrieval operation */
  MEMORY_RETRIEVE = 'memory_retrieve',
  /** Memory search query */
  MEMORY_SEARCH = 'memory_search',
  
  // =============================================================================
  // SDK STREAMING EVENTS - Real-time content and reasoning streams
  // =============================================================================
  /** SDK content block started */
  CONTENT_BLOCK_START = 'content_block_start',
  /** SDK content block delta update */
  CONTENT_BLOCK_DELTA = 'content_block_delta',
  /** SDK content block completed */
  CONTENT_BLOCK_STOP = 'content_block_stop',
  /** SDK reasoning content started */
  REASONING_START = 'reasoning_start',
  /** SDK reasoning content delta */
  REASONING_DELTA = 'reasoning_delta',
  /** SDK reasoning content completed */
  REASONING_END = 'reasoning_end',
  
  // =============================================================================
  // SDK TELEMETRY EVENTS - Performance monitoring and cost tracking
  // =============================================================================
  /** SDK metrics update */
  METRICS_UPDATE = 'metrics_update',
  /** SDK usage/cost update */
  USAGE_UPDATE = 'usage_update',
  /** SDK trace started */
  TRACE_START = 'trace_start',
  /** SDK trace ended */
  TRACE_END = 'trace_end',
  
  // =============================================================================
  // LEGACY AI REASONING EVENTS - Backward compatibility
  // =============================================================================
  /** AI thinking process initiated */
  THINK_START = 'think_start',
  /** AI thinking progress update */
  THINK_PROGRESS = 'think_progress',
  /** AI thinking process completed */
  THINK_END = 'think_end',
  
  // =============================================================================
  // DEVELOPMENT TOOL EVENTS - Code execution and file operations
  // =============================================================================
  /** Python REPL code execution */
  PYTHON_REPL = 'python_repl',
  /** Python execution output */
  PYTHON_OUTPUT = 'python_output',
  /** File editor opened */
  EDITOR_OPEN = 'editor_open',
  /** File editor saved changes */
  EDITOR_SAVE = 'editor_save',
  
  // =============================================================================
  // SYSTEM STATUS EVENTS - Infrastructure and health monitoring
  // =============================================================================
  /** System status information */
  SYSTEM_STATUS = 'system_status',
  /** System error encountered */
  SYSTEM_ERROR = 'system_error',
  /** System warning issued */
  SYSTEM_WARNING = 'system_warning',
  
  // =============================================================================
  // CONNECTION MANAGEMENT EVENTS - Network and service connectivity
  // =============================================================================
  /** Connection established */
  CONNECTION_OPEN = 'connection_open',
  /** Connection terminated */
  CONNECTION_CLOSE = 'connection_close',
  /** Connection error occurred */
  CONNECTION_ERROR = 'connection_error',
  
  // =============================================================================
  // AGENT LIFECYCLE EVENTS - Assessment agent management
  // =============================================================================
  /** Security agent initiated */
  AGENT_START = 'agent_start',
  /** Agent communication message */
  AGENT_MESSAGE = 'agent_message',
  /** Security agent completed */
  AGENT_COMPLETE = 'agent_complete',
  
  // =============================================================================
  // USER INTERACTION EVENTS - Manual intervention and responses
  // =============================================================================
  /** User intervention required */
  USER_HANDOFF = 'user_handoff',
  /** User response provided */
  USER_RESPONSE = 'user_response',
}

// =============================================================================
// SDK NATIVE EVENT INTERFACE DEFINITIONS - Type-safe SDK event structures
// =============================================================================

/**
 * SDK Model Invocation Event Interface
 * 
 * Represents SDK model invocation lifecycle with comprehensive context
 * from the Strands SDK's event loop and streaming system.
 */
export interface SDKModelEvent extends BaseEvent {
  type: EventType.MODEL_INVOCATION_START | EventType.MODEL_INVOCATION_END | 
        EventType.MODEL_STREAM_START | EventType.MODEL_STREAM_DELTA | EventType.MODEL_STREAM_END;
  /** Model identifier from SDK config */
  modelId?: string;
  /** Messages being sent to model */
  messages?: any[];
  /** System prompt being used */
  systemPrompt?: string;
  /** Streaming delta content */
  delta?: string;
  /** Whether streaming is complete */
  isComplete?: boolean;
  /** Stop reason from model */
  stopReason?: string;
  /** SDK performance metrics */
  metrics?: {
    latencyMs?: number;
    inputTokens?: number;
    outputTokens?: number;
    totalTokens?: number;
  };
  /** Error information */
  error?: string;
}

/**
 * SDK Tool Invocation Event Interface
 * 
 * Represents SDK tool execution with native tool registry integration
 * and comprehensive execution context from hook system.
 */
export interface SDKToolEvent extends BaseEvent {
  type: EventType.TOOL_INVOCATION_START | EventType.TOOL_INVOCATION_END;
  /** Tool name from SDK registry */
  toolName: string;
  /** Tool input parameters */
  toolInput?: any;
  /** Tool execution result */
  toolResult?: any;
  /** SDK tool use ID for correlation */
  toolUseId?: string;
  /** Tool execution duration in milliseconds */
  duration?: number;
  /** Tool execution success status */
  success?: boolean;
  /** Error message if tool execution failed */
  error?: string;
  /** SDK invocation state context */
  invocationState?: Record<string, any>;
}

/**
 * SDK Event Loop Event Interface
 * 
 * Represents SDK event loop lifecycle with cycle tracking and metrics.
 */
export interface SDKEventLoopEvent extends BaseEvent {
  type: EventType.EVENT_LOOP_CYCLE_START | EventType.EVENT_LOOP_CYCLE_END;
  /** Event loop cycle number */
  cycleNumber?: number;
  /** Cycle duration in milliseconds */
  duration?: number;
  /** Number of tools executed in cycle */
  toolCallCount?: number;
  /** Messages processed in cycle */
  messageCount?: number;
}

/**
 * SDK Content Streaming Event Interface
 * 
 * Represents SDK's real-time content streaming with delta updates.
 */
export interface SDKContentEvent extends BaseEvent {
  type: EventType.CONTENT_BLOCK_START | EventType.CONTENT_BLOCK_DELTA | EventType.CONTENT_BLOCK_STOP |
        EventType.REASONING_START | EventType.REASONING_DELTA | EventType.REASONING_END;
  /** Content block index */
  contentBlockIndex?: number;
  /** Delta content update */
  delta?: string;
  /** Whether this is reasoning content */
  isReasoning?: boolean;
  /** Reasoning signature for verification */
  reasoningSignature?: string;
  /** Complete content when finished */
  content?: string;
}

/**
 * SDK Telemetry Event Interface
 * 
 * Represents SDK's built-in telemetry and metrics collection.
 */
export interface SDKTelemetryEvent extends BaseEvent {
  type: EventType.METRICS_UPDATE | EventType.USAGE_UPDATE | EventType.TRACE_START | EventType.TRACE_END;
  /** Performance metrics */
  metrics?: {
    latencyMs?: number;
    cycleCount?: number;
    toolCallCount?: number;
    eventLoopDuration?: number;
  };
  /** Token usage metrics */
  usage?: {
    inputTokens: number;
    outputTokens: number;
    totalTokens: number;
  };
  /** Cost tracking information */
  cost?: {
    totalCost?: number;
    modelCost?: number;
    toolCost?: number;
    currency?: string;
  };
  /** Trace information */
  trace?: {
    traceId: string;
    spanId?: string;
    parentSpanId?: string;
    operation?: string;
  };
}

/**
 * SDK Agent Lifecycle Event Interface
 * 
 * Represents SDK agent initialization and lifecycle events.
 */
export interface SDKAgentEvent extends BaseEvent {
  type: EventType.AGENT_INITIALIZED | EventType.MESSAGE_ADDED;
  /** Agent identifier */
  agentId?: string;
  /** Agent name or type */
  agentName?: string;
  /** Message content if MESSAGE_ADDED */
  message?: {
    role: string;
    content: any[];
  };
  /** Agent configuration summary */
  config?: {
    modelId?: string;
    provider?: string;
    toolCount?: number;
  };
}

// =============================================================================
// LEGACY EVENT INTERFACE DEFINITIONS - Backward compatibility
// =============================================================================

/**
 * Tool Execution Event Interface
 * 
 * Represents security assessment tool lifecycle events with comprehensive
 * metadata for execution tracking, performance monitoring, and error handling.
 */
export interface ToolEvent extends BaseEvent {
  type: EventType.TOOL_START | EventType.TOOL_END | EventType.TOOL_ERROR;
  /** Security tool name (e.g., 'nmap', 'sqlmap', 'burp') */
  tool: string;
  /** Tool execution arguments and parameters */
  arguments?: Record<string, any>;
  /** Tool execution result data */
  result?: any;
  /** Error message if tool execution failed */
  error?: string;
  /** Tool execution duration in milliseconds */
  duration?: number;
}

/**
 * Shell Command Execution Event Interface
 * 
 * Represents shell command execution events with output streaming support
 * and comprehensive error handling for system-level security assessments.
 */
export interface ShellEvent extends BaseEvent {
  type: EventType.SHELL_COMMAND | EventType.SHELL_OUTPUT | EventType.SHELL_ERROR;
  /** Shell command being executed */
  command?: string;
  /** Command output (stdout) */
  output?: string;
  /** Command error output (stderr) */
  error?: string;
  /** Process exit code */
  exitCode?: number;
  /** Whether output is being streamed in real-time */
  isStreaming?: boolean;
}

// Swarm events
export interface SwarmEvent extends BaseEvent {
  type: EventType.SWARM_START | EventType.SWARM_AGENT | EventType.SWARM_HANDOFF | EventType.SWARM_END;
  agentName?: string;
  agentId?: string;
  handoffTo?: string;
  handoffReason?: string;
  result?: any;
}

// HTTP events
export interface HttpEvent extends BaseEvent {
  type: EventType.HTTP_REQUEST | EventType.HTTP_RESPONSE;
  method?: string;
  url?: string;
  headers?: Record<string, string>;
  body?: any;
  statusCode?: number;
  responseTime?: number;
}

// Memory events
export interface MemoryEvent extends BaseEvent {
  type: EventType.MEMORY_STORE | EventType.MEMORY_RETRIEVE | EventType.MEMORY_SEARCH;
  operation: 'store' | 'retrieve' | 'search';
  key?: string;
  value?: any;
  results?: any[];
  query?: string;
}

// Think events
export interface ThinkEvent extends BaseEvent {
  type: EventType.THINK_START | EventType.THINK_PROGRESS | EventType.THINK_END;
  thought?: string;
  progress?: string;
  result?: {
    assessment?: string;
    confidence?: number;
    decision?: string;
    rationale?: string;
    next?: string;
  };
}

// Python REPL events
export interface PythonEvent extends BaseEvent {
  type: EventType.PYTHON_REPL | EventType.PYTHON_OUTPUT;
  code?: string;
  output?: string;
  error?: string;
}

// Editor events
export interface EditorEvent extends BaseEvent {
  type: EventType.EDITOR_OPEN | EventType.EDITOR_SAVE;
  file?: string;
  content?: string;
  changes?: {
    added: number;
    removed: number;
  };
}

// System events
export interface SystemEvent extends BaseEvent {
  type: EventType.SYSTEM_STATUS | EventType.SYSTEM_ERROR | EventType.SYSTEM_WARNING;
  level: 'info' | 'warning' | 'error';
  message: string;
  details?: any;
}

// Connection events
export interface ConnectionEvent extends BaseEvent {
  type: EventType.CONNECTION_OPEN | EventType.CONNECTION_CLOSE | EventType.CONNECTION_ERROR;
  status: 'connected' | 'disconnected' | 'error';
  error?: string;
  reconnectAttempt?: number;
}

// Agent events
export interface AgentEvent extends BaseEvent {
  type: EventType.AGENT_START | EventType.AGENT_MESSAGE | EventType.AGENT_COMPLETE;
  agentName: string;
  message?: string;
  data?: any;
  status?: 'running' | 'completed' | 'failed';
  result?: any;
}

// User interaction events
export interface UserEvent extends BaseEvent {
  type: EventType.USER_HANDOFF | EventType.USER_RESPONSE;
  prompt?: string;
  response?: string;
  context?: any;
}

// Python event system events
export interface PythonSystemEvent extends BaseEvent {
  type: EventType.STEP_START | EventType.COMMAND | EventType.COMMAND_ARRAY | EventType.OUTPUT | EventType.STATUS | EventType.BANNER | EventType.SECTION | EventType.REASONING;
  content?: string | string[] | Record<string, any>;
  step?: number;
  total_steps?: number;
  tool_name?: string;
  level?: string;
  operation_id?: string;
}

// =============================================================================
// UNION TYPES AND UTILITY INTERFACES - Event system foundations
// =============================================================================

/**
 * StreamEvent Union Type - Discriminated Union of All Event Types
 * 
 * Comprehensive union type providing type-safe access to all possible
 * event types in the Cyber-AutoAgent system. Includes both SDK-native
 * events and legacy events for backward compatibility. Enables exhaustive 
 * pattern matching and compile-time validation of event handling logic.
 */
export type StreamEvent = 
  // SDK Native Events
  | SDKModelEvent
  | SDKToolEvent
  | SDKEventLoopEvent
  | SDKContentEvent
  | SDKTelemetryEvent
  | SDKAgentEvent
  
  // Legacy Events (backward compatibility)
  | ToolEvent
  | ShellEvent
  | SwarmEvent
  | HttpEvent
  | MemoryEvent
  | ThinkEvent
  | PythonEvent
  | EditorEvent
  | SystemEvent
  | ConnectionEvent
  | AgentEvent
  | UserEvent
  | PythonSystemEvent;

/**
 * Event Handler Function Type
 * 
 * Generic function type for type-safe event handling with optional
 * constraint to specific event subtypes for specialized handlers.
 * 
 * @template T - Event type constraint (defaults to all StreamEvent types)
 */
export type EventHandler<T extends StreamEvent = StreamEvent> = (event: T) => void;

/**
 * Event Filter Configuration Interface
 * 
 * Defines filtering criteria for event streams, enabling selective
 * event processing based on type, source, session, or time constraints.
 */
export interface EventFilter {
  /** Filter by specific event types */
  types?: EventType[];
  /** Filter by security tool names */
  tools?: string[];
  /** Filter by session identifier */
  sessionId?: string;
  /** Filter events since specific timestamp */
  since?: string;
}

/**
 * Event Statistics Interface
 * 
 * Provides comprehensive metrics and analytics for event stream
 * monitoring, performance analysis, and system health assessment.
 */
export interface EventStats {
  /** Total number of events processed */
  totalEvents: number;
  /** Event count breakdown by type */
  eventsByType: Record<EventType, number>;
  /** Total number of error events */
  errorCount: number;
  /** Average event processing latency in milliseconds */
  averageLatency: number;
}
