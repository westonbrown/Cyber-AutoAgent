/**
 * Centralized logging service
 * Replaces direct console usage with environment-aware logging
 */

import { logger } from '../utils/logger.js';

export enum LogLevel {
  DEBUG = 0,
  INFO = 1,
  WARN = 2,
  ERROR = 3,
  NONE = 4,
}

export class LoggingService {
  private static instance: LoggingService;
  private logLevel: LogLevel;
  private isProduction: boolean;
  private logBuffer: Array<{ level: LogLevel; message: string; timestamp: Date }> = [];
  private maxBufferSize = 1000;

  private constructor() {
    this.isProduction = process.env.NODE_ENV === 'production';
    this.logLevel = this.getLogLevelFromEnv();
  }

  static getInstance(): LoggingService {
    if (!LoggingService.instance) {
      LoggingService.instance = new LoggingService();
    }
    return LoggingService.instance;
  }

  private getLogLevelFromEnv(): LogLevel {
    const envLevel = process.env.LOG_LEVEL?.toUpperCase();
    switch (envLevel) {
      case 'DEBUG':
        return LogLevel.DEBUG;
      case 'INFO':
        return LogLevel.INFO;
      case 'WARN':
        return LogLevel.WARN;
      case 'ERROR':
        return LogLevel.ERROR;
      case 'NONE':
        return LogLevel.NONE;
      default:
        return this.isProduction ? LogLevel.ERROR : LogLevel.INFO;
    }
  }

  private shouldLog(level: LogLevel): boolean {
    return level >= this.logLevel;
  }

  private addToBuffer(level: LogLevel, message: string): void {
    this.logBuffer.push({
      level,
      message,
      timestamp: new Date(),
    });

    // Keep buffer size limited
    if (this.logBuffer.length > this.maxBufferSize) {
      this.logBuffer.shift();
    }
  }

  debug(...args: any[]): void {
    const message = args.map(arg => 
      typeof arg === 'object' ? JSON.stringify(arg, null, 2) : String(arg)
    ).join(' ');

    this.addToBuffer(LogLevel.DEBUG, message);

    if (this.shouldLog(LogLevel.DEBUG)) {
      logger.debug(message);
    }
  }

  info(...args: any[]): void {
    const message = args.map(arg => 
      typeof arg === 'object' ? JSON.stringify(arg, null, 2) : String(arg)
    ).join(' ');

    this.addToBuffer(LogLevel.INFO, message);

    if (this.shouldLog(LogLevel.INFO)) {
      logger.info(message);
    }
  }

  warn(...args: any[]): void {
    const message = args.map(arg => 
      typeof arg === 'object' ? JSON.stringify(arg, null, 2) : String(arg)
    ).join(' ');

    this.addToBuffer(LogLevel.WARN, message);

    if (this.shouldLog(LogLevel.WARN)) {
      logger.warn(message);
    }
  }

  error(...args: any[]): void {
    const message = args.map(arg => {
      if (arg instanceof Error) {
        return `${arg.message}\n${arg.stack}`;
      }
      return typeof arg === 'object' ? JSON.stringify(arg, null, 2) : String(arg);
    }).join(' ');

    this.addToBuffer(LogLevel.ERROR, message);

    if (this.shouldLog(LogLevel.ERROR)) {
      logger.error(message);
    }
  }

  /**
   * Get recent logs from buffer
   */
  getRecentLogs(count: number = 100): Array<{ level: string; message: string; timestamp: string }> {
    return this.logBuffer
      .slice(-count)
      .map(log => ({
        level: LogLevel[log.level],
        message: log.message,
        timestamp: log.timestamp.toISOString(),
      }));
  }

  /**
   * Clear log buffer
   */
  clearBuffer(): void {
    this.logBuffer = [];
  }

  /**
   * Set log level dynamically
   */
  setLogLevel(level: LogLevel): void {
    this.logLevel = level;
  }

  /**
   * Create a child logger with context
   */
  createLogger(context: string) {
    return {
      debug: (...args: any[]) => this.debug(`[${context}]`, ...args),
      info: (...args: any[]) => this.info(`[${context}]`, ...args),
      warn: (...args: any[]) => this.warn(`[${context}]`, ...args),
      error: (...args: any[]) => this.error(`[${context}]`, ...args),
    };
  }
}

// Export singleton instance
export const loggingService = LoggingService.getInstance();

// Create context-aware loggers for different components
export const componentLoggers = {
  streamDisplay: loggingService.createLogger('StreamDisplay'),
  operationManager: loggingService.createLogger('OperationManager'),
  dockerService: loggingService.createLogger('DockerService'),
  pythonService: loggingService.createLogger('PythonService'),
  configContext: loggingService.createLogger('ConfigContext'),
  moduleContext: loggingService.createLogger('ModuleContext'),
  errorBoundary: loggingService.createLogger('ErrorBoundary'),
  healthMonitor: loggingService.createLogger('HealthMonitor'),
};

// Replace console in production
if (process.env.NODE_ENV === 'production') {
  console.log = loggingService.info.bind(loggingService);
  console.info = loggingService.info.bind(loggingService);
  console.warn = loggingService.warn.bind(loggingService);
  console.error = loggingService.error.bind(loggingService);
  console.debug = loggingService.debug.bind(loggingService);
}