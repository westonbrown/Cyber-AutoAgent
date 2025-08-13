/**
 * Unified Execution Service Interface
 * 
 * Provides a unified interface for all execution modes (Python CLI, Docker single-container, 
 * Docker full-stack) following modern CLI application patterns.
 * 
 * Key Design Principles:
 * - Configuration-driven execution (no runtime mode detection)
 * - Consistent interface across all execution types
 * - Pre-execution validation guarantees
 * - Unified event handling and lifecycle management
 */

import { EventEmitter } from 'events';
import { Config } from '../contexts/ConfigContext.js';
import { AssessmentParams } from '../types/Assessment.js';

/**
 * Execution modes available in the system
 */
export enum ExecutionMode {
  /** Direct Python execution in virtual environment */
  PYTHON_CLI = 'python-cli',
  /** Single Docker container execution */
  DOCKER_SINGLE = 'docker-single', 
  /** Full Docker stack with observability services */
  DOCKER_STACK = 'docker-stack'
}

/**
 * Result of execution environment validation
 */
export interface ValidationResult {
  /** Whether the execution environment is valid and ready */
  valid: boolean;
  /** Human-readable error message if validation failed */
  error?: string;
  /** Specific issues found during validation */
  issues: ValidationIssue[];
  /** Warnings that don't prevent execution but should be noted */
  warnings: string[];
}

/**
 * Specific validation issue
 */
export interface ValidationIssue {
  /** Type of validation that failed */
  type: 'python' | 'docker' | 'credentials' | 'network' | 'filesystem' | 'config';
  /** Severity of the issue */
  severity: 'error' | 'warning';
  /** Human-readable description */
  message: string;
  /** Suggested resolution if available */
  suggestion?: string;
}

/**
 * Handle for an ongoing execution
 */
export interface ExecutionHandle {
  /** Unique identifier for this execution */
  id: string;
  /** Process ID if available */
  pid?: number;
  /** Promise that resolves when execution completes */
  result: Promise<ExecutionResult>;
  /** Stop the execution */
  stop(): Promise<void>;
  /** Check if execution is still active */
  isActive(): boolean;
}

/**
 * Result of execution
 */
export interface ExecutionResult {
  /** Whether execution completed successfully */
  success: boolean;
  /** Exit code if available */
  exitCode?: number;
  /** Error message if execution failed */
  error?: string;
  /** Duration of execution in milliseconds */
  durationMs: number;
  /** Number of steps executed */
  stepsExecuted?: number;
  /** Findings or evidence count */
  findingsCount?: number;
}

/**
 * Execution service capabilities
 */
export interface ExecutionCapabilities {
  /** Whether this service can execute assessments */
  canExecute: boolean;
  /** Whether this service supports real-time streaming */
  supportsStreaming: boolean;
  /** Whether this service supports parallel execution */
  supportsParallel: boolean;
  /** Maximum concurrent executions supported */
  maxConcurrent: number;
  /** Required system resources */
  requirements: string[];
}

/**
 * Unified Execution Service Interface
 * 
 * All execution services (Python, Docker) must implement this interface
 * to ensure consistent behavior and lifecycle management.
 */
export interface ExecutionService extends EventEmitter {
  /**
   * Get the execution mode this service handles
   */
  getMode(): ExecutionMode;

  /**
   * Get service capabilities
   */
  getCapabilities(): ExecutionCapabilities;

  /**
   * Validate that this execution environment is ready
   * This must be called before execute() and should be fast (<1s)
   * 
   * @param config - User configuration
   * @returns Validation result with any issues found
   */
  validate(config: Config): Promise<ValidationResult>;

  /**
   * Execute an assessment using this service
   * validate() should be called first to ensure environment is ready
   * 
   * @param params - Assessment parameters
   * @param config - User configuration
   * @returns Execution handle for managing the running assessment
   */
  execute(params: AssessmentParams, config: Config): Promise<ExecutionHandle>;

  /**
   * Check if this service can handle the given configuration
   * This is a quick availability check, not full validation
   * 
   * @param config - User configuration
   * @returns Whether this service supports the configuration
   */
  isSupported(config: Config): Promise<boolean>;

  /**
   * Setup the execution environment if needed
   * Only called when validation indicates setup is required
   * 
   * @param config - User configuration
   * @param onProgress - Progress callback
   */
  setup?(config: Config, onProgress?: (message: string) => void): Promise<void>;

  /**
   * Cleanup resources and stop any active executions
   */
  cleanup(): void;

  /**
   * Get current status of the service
   */
  isActive(): boolean;
}

/**
 * Events emitted by ExecutionService implementations
 */
export interface ExecutionServiceEvents {
  /** Execution has started */
  'started': (handle: ExecutionHandle) => void;
  /** Structured event from the execution (same format for all services) */
  'event': (event: any) => void;
  /** Execution completed successfully */
  'complete': (result: ExecutionResult) => void;
  /** Execution stopped by user */
  'stopped': () => void;  
  /** Execution failed with error */
  'error': (error: Error) => void;
  /** Service setup progress */
  'progress': (message: string) => void;
}

/**
 * Configuration for execution service selection
 */
export interface ExecutionConfig {
  /** Preferred execution mode (user choice) */
  preferredMode?: ExecutionMode;
  /** Fallback modes to try if preferred fails validation */
  fallbackModes: ExecutionMode[];
  /** Whether to require user confirmation for fallback modes */
  requireConfirmationForFallback: boolean;
  /** Maximum time to wait for validation (ms) */
  validationTimeoutMs: number;
}

/**
 * Default execution configuration
 */
export const DEFAULT_EXECUTION_CONFIG: ExecutionConfig = {
  preferredMode: undefined, // Will be set based on user's deployment mode selection
  fallbackModes: [], // No fallbacks - enforce user's mode choice
  requireConfirmationForFallback: true,
  validationTimeoutMs: 30000  // Increased to 30s to handle slower Python environment checks
};