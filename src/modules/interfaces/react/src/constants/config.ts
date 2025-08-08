/**
 * Configuration constants - centralized defaults and limits
 */

// Network defaults
export const NETWORK_DEFAULTS = {
  LANGFUSE_HOST: 'http://localhost:3000',
  LANGFUSE_DOCKER_HOST: 'http://langfuse-web:3000',
  OLLAMA_HOST: 'http://localhost:11434',
  LANGFUSE_PORT: 3000,
  OLLAMA_PORT: 11434,
} as const;

// Timeouts (in milliseconds)
export const TIMEOUTS = {
  CONTAINER_STARTUP: 300000, // 5 minutes
  HEALTH_CHECK_PRODUCTION: 30000, // 30 seconds
  HEALTH_CHECK_DEVELOPMENT: 10000, // 10 seconds
  OPERATION_DEFAULT: 60000, // 1 minute
  OPERATION_DEVELOPMENT: 30000, // 30 seconds
  RETRY_MAX_DELAY: 30000, // 30 seconds
  MONITORING_PERIOD: 5000, // 5 seconds
  CONFIG_SAVE_DEBOUNCE: 3000, // 3 seconds
  CONTAINER_WAIT: 5000, // 5 seconds
} as const;

// Limits
export const LIMITS = {
  MAX_STEPS_DEFAULT: 100,
  MAX_ITERATIONS_DEFAULT: 100,
  MAX_SWARM_HANDOFFS: 20,
  MAX_SWARM_ITERATIONS: 20,
  MAX_RETRY_ATTEMPTS: 3,
  MAX_LOG_LINES: 1000,
  MAX_EVENTS_BUFFER: 10000,
} as const;

// Display limits
export const DISPLAY_LIMITS = {
  TRUNCATE_SHORT: 50,
  TRUNCATE_MEDIUM: 80,
  TRUNCATE_LONG: 100,
  TRUNCATE_EXTENDED: 200,
  CODE_PREVIEW_LINES: 8,
  TOOL_INPUT_MAX_KEYS: 4,
  TOOL_INPUT_PREVIEW_KEYS: 3,
} as const;

// Token pricing (per million tokens)
export const TOKEN_PRICING = {
  CLAUDE_SONNET_INPUT: 3.0,
  CLAUDE_SONNET_OUTPUT: 15.0,
  GPT4_INPUT: 10.0,
  GPT4_OUTPUT: 30.0,
} as const;

// File paths
export const FILE_PATHS = {
  CONFIG_DIR: '.cyberautoagent',
  CONFIG_FILE: 'config.json',
  SESSION_FILE: 'session.json',
  MEMORY_DB: 'memory.db',
  OUTPUTS_DIR: 'outputs',
  LOGS_DIR: 'logs',
} as const;

// Environment detection
export const ENV_DETECTION = {
  IS_DOCKER: process.env.DOCKER_CONTAINER === 'true',
  IS_PRODUCTION: process.env.NODE_ENV === 'production',
  IS_DEVELOPMENT: process.env.NODE_ENV === 'development',
  IS_TEST: process.env.NODE_ENV === 'test',
} as const;

// Default model settings
export const MODEL_DEFAULTS = {
  BEDROCK_MODEL: 'us.anthropic.claude-sonnet-4-20250514-v1:0',
  BEDROCK_REGION: 'us-east-1',
  OPENAI_MODEL: 'gpt-4',
  OLLAMA_MODEL: 'llama2',
  TEMPERATURE: 0.7,
  MAX_TOKENS: 4096,
} as const;

// Regex patterns
export const PATTERNS = {
  LOCALHOST: /localhost|127\.0\.0\.1/i,
  URL: /^https?:\/\//i,
  IP_ADDRESS: /^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$/,
  PORT: /:\d{1,5}$/,
  UUID: /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i,
} as const;

// Event types for consistency
export const EVENT_TYPES = {
  // Core events
  STEP_HEADER: 'step_header',
  REASONING: 'reasoning',
  THINKING: 'thinking',
  THINKING_END: 'thinking_end',
  TOOL_START: 'tool_start',
  TOOL_END: 'tool_end',
  OUTPUT: 'output',
  ERROR: 'error',
  METADATA: 'metadata',
  DIVIDER: 'divider',
  
  // Swarm events
  SWARM_START: 'swarm_start',
  SWARM_HANDOFF: 'swarm_handoff',
  SWARM_COMPLETE: 'swarm_complete',
  
  // User interaction
  USER_HANDOFF: 'user_handoff',
  USER_INPUT: 'user_input',
  
  // Metrics
  METRICS_UPDATE: 'metrics_update',
  EVALUATION_COMPLETE: 'evaluation_complete',
  
  // SDK events
  MODEL_INVOCATION_START: 'model_invocation_start',
  MODEL_STREAM_DELTA: 'model_stream_delta',
  REASONING_DELTA: 'reasoning_delta',
  TOOL_INVOCATION_START: 'tool_invocation_start',
  TOOL_INVOCATION_END: 'tool_invocation_end',
  EVENT_LOOP_CYCLE_START: 'event_loop_cycle_start',
  CONTENT_BLOCK_DELTA: 'content_block_delta',
} as const;

// Status codes
export const STATUS = {
  SUCCESS: 'success',
  ERROR: 'error',
  WARNING: 'warning',
  INFO: 'info',
  PENDING: 'pending',
  RUNNING: 'running',
  COMPLETED: 'completed',
  FAILED: 'failed',
  CANCELLED: 'cancelled',
} as const;

// Operation states
export const OPERATION_STATES = {
  IDLE: 'idle',
  INITIALIZING: 'initializing',
  RUNNING: 'running',
  PAUSED: 'paused',
  STOPPING: 'stopping',
  COMPLETED: 'completed',
  ERROR: 'error',
} as const;