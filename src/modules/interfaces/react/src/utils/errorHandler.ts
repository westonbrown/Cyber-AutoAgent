/**
 * Centralized error handling utilities
 */

import { logger } from './logger.js';

export enum ErrorSeverity {
  LOW = 'low',
  MEDIUM = 'medium',
  HIGH = 'high',
  CRITICAL = 'critical',
}

export enum ErrorCategory {
  NETWORK = 'network',
  CONFIGURATION = 'configuration',
  EXECUTION = 'execution',
  VALIDATION = 'validation',
  PERMISSION = 'permission',
  RESOURCE = 'resource',
  TIMEOUT = 'timeout',
  UNKNOWN = 'unknown',
}

export interface ErrorContext {
  operation?: string;
  target?: string;
  tool?: string;
  step?: number;
  module?: string;
  userId?: string;
  sessionId?: string;
  metadata?: Record<string, unknown>;
}

export class CyberAgentError extends Error {
  public readonly severity: ErrorSeverity;
  public readonly category: ErrorCategory;
  public readonly context?: ErrorContext;
  public readonly timestamp: Date;
  public readonly recoverable: boolean;

  constructor(
    message: string,
    options?: {
      severity?: ErrorSeverity;
      category?: ErrorCategory;
      context?: ErrorContext;
      recoverable?: boolean;
      cause?: Error;
    }
  ) {
    super(message);
    this.name = 'CyberAgentError';
    this.severity = options?.severity || ErrorSeverity.MEDIUM;
    this.category = options?.category || ErrorCategory.UNKNOWN;
    this.context = options?.context;
    this.timestamp = new Date();
    this.recoverable = options?.recoverable ?? true;
    
    if (options?.cause) {
      this.cause = options.cause;
    }

    // Maintain proper stack trace for where our error was thrown
    if (Error.captureStackTrace) {
      Error.captureStackTrace(this, CyberAgentError);
    }
  }

  toJSON() {
    return {
      name: this.name,
      message: this.message,
      severity: this.severity,
      category: this.category,
      context: this.context,
      timestamp: this.timestamp.toISOString(),
      recoverable: this.recoverable,
      stack: this.stack,
      cause: this.cause,
    };
  }
}

/**
 * Global error handler for uncaught errors
 */
export const handleError = (
  error: Error | CyberAgentError,
  context?: ErrorContext
): void => {
  // Determine severity based on error type
  const severity = error instanceof CyberAgentError 
    ? error.severity 
    : ErrorSeverity.HIGH;

  // Log error with appropriate level
  switch (severity) {
    case ErrorSeverity.CRITICAL:
      logger.error('Critical error occurred', error, context as Record<string, any>);
      break;
    case ErrorSeverity.HIGH:
      logger.error('Error occurred', error, context as Record<string, any>);
      break;
    case ErrorSeverity.MEDIUM:
      logger.warn('Warning: Error occurred', context as Record<string, any>);
      break;
    case ErrorSeverity.LOW:
      logger.info('Minor error occurred', context as Record<string, any>);
      break;
  }

  // Report to monitoring service if configured
  if (process.env.ENABLE_ERROR_REPORTING === 'true') {
    reportErrorToMonitoring(error, context);
  }
  
  // Store context in error if it's a CyberAgentError
  if (error instanceof CyberAgentError && context && !error.context) {
    (error as any).context = context;
  }
};

/**
 * Report error to monitoring service (placeholder)
 */
const reportErrorToMonitoring = (
  error: Error | CyberAgentError,
  context?: ErrorContext
): void => {
  // This would integrate with services like Sentry, Datadog, etc.
  // For now, just log that we would report it
  if (process.env.NODE_ENV === 'production') {
    logger.debug('Would report error to monitoring service', {
      message: error.message,
      context,
    });
  }
};

/**
 * Wrap async functions with error handling
 */
export const withErrorHandling = <T extends (...args: any[]) => Promise<any>>(
  fn: T,
  context?: ErrorContext
): T => {
  return (async (...args: Parameters<T>) => {
    try {
      return await fn(...args);
    } catch (error) {
      handleError(error as Error, context);
      throw error;
    }
  }) as T;
};

/**
 * Create error with context
 */
export const createError = (
  message: string,
  category: ErrorCategory,
  context?: ErrorContext
): CyberAgentError => {
  return new CyberAgentError(message, {
    category,
    context,
    severity: ErrorSeverity.MEDIUM,
  });
};

/**
 * Common error factories
 */
export const Errors = {
  network: (message: string, context?: ErrorContext) =>
    new CyberAgentError(message, {
      category: ErrorCategory.NETWORK,
      severity: ErrorSeverity.HIGH,
      context,
      recoverable: true,
    }),

  configuration: (message: string, context?: ErrorContext) =>
    new CyberAgentError(message, {
      category: ErrorCategory.CONFIGURATION,
      severity: ErrorSeverity.HIGH,
      context,
      recoverable: false,
    }),

  timeout: (message: string, context?: ErrorContext) =>
    new CyberAgentError(message, {
      category: ErrorCategory.TIMEOUT,
      severity: ErrorSeverity.MEDIUM,
      context,
      recoverable: true,
    }),

  validation: (message: string, context?: ErrorContext) =>
    new CyberAgentError(message, {
      category: ErrorCategory.VALIDATION,
      severity: ErrorSeverity.LOW,
      context,
      recoverable: false,
    }),

  permission: (message: string, context?: ErrorContext) =>
    new CyberAgentError(message, {
      category: ErrorCategory.PERMISSION,
      severity: ErrorSeverity.CRITICAL,
      context,
      recoverable: false,
    }),

  execution: (message: string, context?: ErrorContext) =>
    new CyberAgentError(message, {
      category: ErrorCategory.EXECUTION,
      severity: ErrorSeverity.HIGH,
      context,
      recoverable: true,
    }),
};