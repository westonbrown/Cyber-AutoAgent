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
 * SDK-aligned event definitions
 */

/**
 * Base Event Interface - Foundation for All Stream Events
 * 
 * Provides the core structure shared by all event types in the system
 * with essential metadata for tracking, correlation, and debugging.
 * Includes SDK-compatible tracing and context preservation.
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
  /** SDK reasoning content started */
  REASONING_START = 'reasoning_start',
  /** SDK reasoning content completed */
  REASONING_END = 'reasoning_end',
  
  // =============================================================================
  // SDK TELEMETRY EVENTS - Performance monitoring and cost tracking
  // =============================================================================
  /** SDK metrics update */
  METRICS_UPDATE = 'metrics_update',
  /** SDK usage/cost update */
  USAGE_UPDATE = 'usage_update',
  
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
  // HITL (Human-in-the-Loop) EVENTS - User intervention and feedback
  // =============================================================================
  /** Tool execution paused for human review */
  HITL_PAUSE_REQUESTED = 'hitl_pause_requested',
  /** User feedback submitted for pending tool */
  HITL_FEEDBACK_SUBMITTED = 'hitl_feedback_submitted',
  /** Agent interpretation of user feedback */
  HITL_AGENT_INTERPRETATION = 'hitl_agent_interpretation',
  /** Execution resumed after feedback processing */
  HITL_RESUME = 'hitl_resume',

}

// =============================================================================
// SDK NATIVE EVENT INTERFACE DEFINITIONS - Type-safe SDK event structures
// =============================================================================




/**
 * SDK Content Streaming Event Interface
 * 
 * Represents SDK's real-time content streaming with delta updates.
 */
export interface SDKContentEvent extends BaseEvent {
  type: EventType.REASONING_START | EventType.REASONING_END;
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
  type: EventType.METRICS_UPDATE | EventType.USAGE_UPDATE;
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
  type: EventType.AGENT_INITIALIZED;
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
  /** Visual emphasis level for UI rendering */
  emphasis?: 'high' | 'medium' | 'low';
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

// HITL (Human-in-the-Loop) events
export interface HITLEvent extends BaseEvent {
  type: EventType.HITL_PAUSE_REQUESTED | EventType.HITL_FEEDBACK_SUBMITTED | EventType.HITL_AGENT_INTERPRETATION | EventType.HITL_RESUME;
  /** Tool name being reviewed */
  tool_name?: string;
  /** Unique tool invocation ID */
  tool_id?: string;
  /** Tool parameters under review */
  parameters?: Record<string, any>;
  /** Confidence score (0-100) */
  confidence?: number;
  /** Reason for pause (e.g., "destructive_operation") */
  reason?: string;
  /** Feedback type (correction, suggestion, approval, rejection) */
  feedback_type?: string;
  /** Feedback content from user */
  content?: string;
  /** Agent's interpretation of feedback */
  interpretation?: string;
  /** Modified parameters after feedback */
  modified_parameters?: Record<string, any>;
  /** Whether interpretation awaits user approval */
  awaiting_approval?: boolean;
  /** Whether interpretation was approved */
  approved?: boolean;
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

// Simple event for displaying the final security report
export interface ReportContentEvent {
  type: 'report_content';
  content: string;
  id?: string;
  timestamp?: string;
}

/**
 * Termination Reason Event Interface
 * 
 * Event emitted when an operation terminates, indicating the reason
 * (e.g., step limit reached, stop tool invoked, network timeout, token limit)
 */
export interface TerminationReasonEvent {
  type: 'termination_reason';
  // Known reasons from backend + forward-compatible string type
  reason:
    | 'step_limit'
    | 'stop_tool'
    | 'network_timeout'
    | 'network_error'
    | 'timeout'
    | 'max_tokens'
    | 'rate_limited'
    | 'model_error';
  message: string;
  current_step?: number;
  max_steps?: number;
  id?: string;
  timestamp?: string;
}

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
  | SystemEvent
  | ConnectionEvent
  | AgentEvent
  | HITLEvent
  | PythonSystemEvent
  | ReportContentEvent
  | TerminationReasonEvent
  | { type: 'error'; error?: string; message?: string; [key: string]: any }
  | { type: 'output'; content?: string; [key: string]: any }
  | { type: 'metadata'; [key: string]: any };

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
