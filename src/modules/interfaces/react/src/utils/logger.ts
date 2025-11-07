/**
 * Production-Grade Structured Logging System
 * Provides configurable logging with levels, structured output, and environment-aware formatting
 */

import { getEnvironmentConfig } from '../config/environment.js';

export type LogLevel = 'debug' | 'info' | 'warn' | 'error';

export interface LogEntry {
  timestamp: string;
  level: LogLevel;
  message: string;
  component?: string;
  operation?: string;
  sessionId?: string;
  error?: Error;
  metadata?: Record<string, any>;
}

export interface LoggerConfig {
  level: LogLevel;
  structured: boolean;
  component?: string;
  operation?: string;
  sessionId?: string;
}

/**
 * Production-ready logger with structured output and level filtering
 */
// Global safety limits for log payload sizes
const MAX_LOG_CHARS_DEFAULT = 2000; // hard cap for any string field
const REDACT_KEYS = ['token', 'secret', 'password', 'bearer', 'apikey', 'api_key', 'accesskey', 'access_key', 'awsBearerToken'];

function isLikelySecretKey(k: string): boolean {
  const key = k.toLowerCase();
  return REDACT_KEYS.some(s => key.includes(s));
}

function truncateString(str: string, max: number): string {
  if (typeof str !== 'string') return str as unknown as string;
  if (str.length <= max) return str;
  const omitted = str.length - max;
  return str.slice(0, max) + `...(truncated ${omitted} chars)`;
}

function sanitizeValue(val: any, max: number, keyHint?: string): any {
  try {
    if (val == null) return val;
    if (typeof val === 'string') {
      // Redact secrets by key hint
      if (keyHint && isLikelySecretKey(keyHint)) return '***redacted***';
      return truncateString(val, max);
    }
    if (Array.isArray(val)) {
      return val.map(v => sanitizeValue(v, max));
    }
    if (typeof val === 'object') {
      const out: Record<string, any> = {};
      for (const [k, v] of Object.entries(val)) {
        out[k] = sanitizeValue(v, max, k);
      }
      return out;
    }
    return val;
  } catch {
    return val;
  }
}

function sanitizeEntry(entry: LogEntry, max: number): LogEntry {
  const safeMsg = truncateString(entry.message ?? '', max);
  const safeError = entry.error
    ? {
        name: entry.error.name,
        message: truncateString(entry.error.message ?? '', max),
        stack: entry.error.stack ? truncateString(entry.error.stack, max) : undefined
      }
    : undefined;
  const safeMeta = entry.metadata ? sanitizeValue(entry.metadata, max) : undefined;
  return {
    ...entry,
    message: safeMsg,
    ...(safeError && { error: new Error(safeError.message) }),
    ...(safeMeta && { metadata: safeMeta })
  };
}

export class Logger {
  private config: LoggerConfig;
  private static readonly levelPriority: Record<LogLevel, number> = {
    debug: 0,
    info: 1,
    warn: 2,
    error: 3
  };

  constructor(config?: Partial<LoggerConfig>) {
    const envConfig = getEnvironmentConfig();
    this.config = {
      level: envConfig.logging.level,
      structured: envConfig.logging.structured,
      ...config
    };
  }

  /**
   * Create a child logger with additional context
   */
  child(context: { component?: string; operation?: string; sessionId?: string }): Logger {
    return new Logger({
      ...this.config,
      ...context
    });
  }

  /**
   * Log debug message
   */
  debug(message: string, metadata?: Record<string, any>): void {
    this.log('debug', message, metadata);
  }

  /**
   * Log info message
   */
  info(message: string, metadata?: Record<string, any>): void {
    this.log('info', message, metadata);
  }

  /**
   * Log warning message
   */
  warn(message: string, metadata?: Record<string, any>): void {
    this.log('warn', message, metadata);
  }

  /**
   * Log error message
   */
  error(message: string, error?: Error, metadata?: Record<string, any>): void {
    this.log('error', message, { ...metadata, error });
  }

  /**
   * Core logging method
   */
  private log(level: LogLevel, message: string, metadata?: Record<string, any>): void {
    // Filter out logs below configured level
    if (Logger.levelPriority[level] < Logger.levelPriority[this.config.level]) {
      return;
    }

    // In React Ink environment, suppress all non-error logs unless explicitly debugging
    // Check environment variables dynamically to support runtime flag changes
    const isReactInk = process.env.REACT_INK === 'true' || process.stdout.isTTY;
    const isDebugMode = !!(process.env.DEBUG || process.env.CYBER_DEBUG);
    const isTestMode = process.env.NODE_ENV === 'test' || process.env.CYBER_TEST_MODE === 'true';

    if (isReactInk && level !== 'error' && !isDebugMode && !isTestMode) {
      // Completely suppress info/debug logs in production UI
      return;
    }

    const entry: LogEntry = {
      timestamp: new Date().toISOString(),
      level,
      message,
      component: this.config.component,
      operation: this.config.operation,
      sessionId: this.config.sessionId,
      ...metadata
    };

    // Apply safety truncation/redaction
    const max = Number(process.env.CYBER_MAX_LOG_CHARS || MAX_LOG_CHARS_DEFAULT);
    const safeEntry = sanitizeEntry(entry, isFinite(max) && max > 0 ? max : MAX_LOG_CHARS_DEFAULT);

    if (this.config.structured) {
      this.outputStructured(safeEntry);
    } else {
      this.outputSimple(safeEntry);
    }
  }

  /**
   * Output structured JSON logs (production)
   */
  private outputStructured(entry: LogEntry): void {
    const output = {
      timestamp: entry.timestamp,
      level: entry.level,
      message: entry.message,
      ...(entry.component && { component: entry.component }),
      ...(entry.operation && { operation: entry.operation }),
      ...(entry.sessionId && { sessionId: entry.sessionId }),
      ...(entry.error && { 
        error: {
          name: entry.error.name,
          message: entry.error.message,
          stack: entry.error.stack
        }
      }),
      ...(entry.metadata && { metadata: entry.metadata })
    };

    console.log(JSON.stringify(output));
  }

  /**
   * Output human-readable logs (development)
   */
  private outputSimple(entry: LogEntry): void {
    const timestamp = entry.timestamp.split('T')[1].split('.')[0];
    const level = entry.level.toUpperCase().padEnd(5);
    const component = entry.component ? `[${entry.component}] ` : '';
    const operation = entry.operation ? `{${entry.operation}} ` : '';
    
    let output = `${timestamp} ${level} ${component}${operation}${entry.message}`;
    
    if (entry.error) {
      output += `\nError: ${entry.error.message}`;
      if (entry.error.stack) {
        output += `\nStack: ${entry.error.stack}`;
      }
    }
    
    if (entry.metadata && Object.keys(entry.metadata).length > 0) {
      output += `\nMetadata: ${JSON.stringify(entry.metadata, null, 2)}`;
    }

    // Use appropriate console method based on level
    switch (entry.level) {
      case 'debug':
        console.debug(output);
        break;
      case 'info':
        console.info(output);
        break;
      case 'warn':
        console.warn(output);
        break;
      case 'error':
        console.error(output);
        break;
    }
  }
}

/**
 * Default logger instance
 */
export const logger = new Logger();

/**
 * Create component-specific logger
 */
export function createLogger(component: string): Logger {
  return logger.child({ component });
}

/**
 * Create operation-specific logger
 */
export function createOperationLogger(operation: string, sessionId?: string): Logger {
  return logger.child({ operation, sessionId });
}