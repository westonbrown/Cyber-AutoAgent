/**
 * Production-Grade Error Recovery and Retry Logic
 * Implements exponential backoff, circuit breaker pattern, and configurable retry strategies
 */

import { logger } from './logger.js';

export interface RetryConfig {
  maxRetries: number;
  baseDelay: number;
  maxDelay: number;
  backoffFactor: number;
  jitter: boolean;
  retryCondition?: (error: Error) => boolean;
}

export interface CircuitBreakerConfig {
  failureThreshold: number;
  timeout: number;
  monitoringPeriod: number;
}

export type CircuitBreakerState = 'closed' | 'open' | 'half-open';

/**
 * Exponential backoff retry mechanism
 */
export class RetryManager {
  private config: RetryConfig;

  constructor(config: Partial<RetryConfig> = {}) {
    this.config = {
      maxRetries: 3,
      baseDelay: 1000,
      maxDelay: 30000,
      backoffFactor: 2,
      jitter: true,
      ...config
    };
  }

  /**
   * Execute function with retry logic
   */
  async execute<T>(
    operation: () => Promise<T>,
    context?: string
  ): Promise<T> {
    let lastError: Error;
    
    for (let attempt = 0; attempt <= this.config.maxRetries; attempt++) {
      try {
        if (attempt > 0) {
          const delay = this.calculateDelay(attempt);
          logger.debug(`Retrying operation after ${delay}ms`, {
            context,
            attempt,
            maxRetries: this.config.maxRetries
          });
          await this.sleep(delay);
        }

        const result = await operation();
        
        if (attempt > 0) {
          logger.info(`Operation succeeded after ${attempt} retries`, { context });
        }
        
        return result;
      } catch (error) {
        lastError = error as Error;
        
        // Check if we should retry this error
        if (this.config.retryCondition && !this.config.retryCondition(lastError)) {
          logger.debug('Error not retryable, failing immediately', {
            context,
            error: lastError.message
          });
          throw lastError;
        }

        logger.warn(`Operation failed, attempt ${attempt + 1}/${this.config.maxRetries + 1}`, {
          context,
          errorMessage: lastError.message,
          willRetry: attempt < this.config.maxRetries
        });

        if (attempt === this.config.maxRetries) {
          logger.error('Operation failed after all retries exhausted', lastError, {
            context,
            totalAttempts: attempt + 1
          });
          throw lastError;
        }
      }
    }

    throw lastError!;
  }

  /**
   * Calculate delay with exponential backoff and optional jitter
   */
  private calculateDelay(attempt: number): number {
    const exponentialDelay = Math.min(
      this.config.baseDelay * Math.pow(this.config.backoffFactor, attempt - 1),
      this.config.maxDelay
    );

    if (this.config.jitter) {
      // Add ±25% jitter to prevent thundering herd
      const jitterRange = exponentialDelay * 0.25;
      const jitter = (Math.random() - 0.5) * 2 * jitterRange;
      return Math.max(0, exponentialDelay + jitter);
    }

    return exponentialDelay;
  }

  private sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}

/**
 * Circuit breaker implementation for preventing cascade failures
 */
export class CircuitBreaker {
  private state: CircuitBreakerState = 'closed';
  private failureCount = 0;
  private lastFailureTime = 0;
  private config: CircuitBreakerConfig;

  constructor(config: Partial<CircuitBreakerConfig> = {}) {
    this.config = {
      failureThreshold: 5,
      timeout: 60000, // 1 minute
      monitoringPeriod: 10000, // 10 seconds
      ...config
    };
  }

  /**
   * Execute operation through circuit breaker
   */
  async execute<T>(
    operation: () => Promise<T>,
    context?: string
  ): Promise<T> {
    if (this.state === 'open') {
      if (Date.now() - this.lastFailureTime < this.config.timeout) {
        throw new Error(`Circuit breaker is OPEN for ${context || 'operation'}`);
      } else {
        this.state = 'half-open';
        logger.info('Circuit breaker transitioning to HALF-OPEN', { context });
      }
    }

    try {
      const result = await operation();
      
      if (this.state === 'half-open') {
        this.reset();
        logger.info('Circuit breaker reset to CLOSED after successful operation', { context });
      }
      
      return result;
    } catch (error) {
      this.recordFailure();
      
      if (this.state === 'half-open') {
        this.state = 'open';
        this.lastFailureTime = Date.now();
        logger.warn('Circuit breaker opened from HALF-OPEN state', { context });
      } else if (this.failureCount >= this.config.failureThreshold) {
        this.state = 'open';
        this.lastFailureTime = Date.now();
        logger.warn('Circuit breaker OPENED due to failure threshold', {
          context,
          failureCount: this.failureCount,
          threshold: this.config.failureThreshold
        });
      }
      
      throw error;
    }
  }

  private recordFailure(): void {
    this.failureCount++;
  }

  private reset(): void {
    this.failureCount = 0;
    this.state = 'closed';
  }

  getState(): CircuitBreakerState {
    return this.state;
  }

  getFailureCount(): number {
    return this.failureCount;
  }
}

/**
 * Predefined retry configurations for common operations
 */
export const RetryConfigs = {
  /**
   * Docker operations - aggressive retry for infrastructure
   */
  docker: new RetryManager({
    maxRetries: 3,
    baseDelay: 2000,
    maxDelay: 15000,
    backoffFactor: 2,
    jitter: true,
    retryCondition: (error) => {
      // Retry on network errors, container not ready, etc.
      const retryableErrors = [
        'ECONNREFUSED',
        'ENOTFOUND',
        'ETIMEDOUT',
        'container not found',
        'network not found'
      ];
      return retryableErrors.some(pattern => 
        error.message.toLowerCase().includes(pattern.toLowerCase())
      );
    }
  }),

  /**
   * Health checks - fast retry for monitoring
   */
  healthCheck: new RetryManager({
    maxRetries: 2,
    baseDelay: 500,
    maxDelay: 5000,
    backoffFactor: 2,
    jitter: false
  }),

  /**
   * Container lifecycle - balanced retry
   */
  container: new RetryManager({
    maxRetries: 5,
    baseDelay: 1000,
    maxDelay: 10000,
    backoffFactor: 1.5,
    jitter: true,
    retryCondition: (error) => {
      // Don't retry on permission errors or invalid parameters
      const nonRetryableErrors = [
        'permission denied',
        'invalid argument',
        'bad parameter'
      ];
      return !nonRetryableErrors.some(pattern =>
        error.message.toLowerCase().includes(pattern.toLowerCase())
      );
    }
  })
};

/**
 * Default circuit breakers for critical services
 */
export const CircuitBreakers = {
  docker: new CircuitBreaker({
    failureThreshold: 3,
    timeout: 30000, // 30 seconds
    monitoringPeriod: 5000
  }),

  healthMonitor: new CircuitBreaker({
    failureThreshold: 5,
    timeout: 60000, // 1 minute
    monitoringPeriod: 10000
  })
};