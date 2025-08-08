/**
 * Execution Service Factory
 * 
 * Centralized factory for creating and managing execution services.
 * Following industry-standard service registry patterns, this provides:
 * - Configuration-driven service selection
 * - Service capability validation
 * - Fallback mode handling
 * - Service lifecycle management
 */

import { 
  ExecutionService, 
  ExecutionMode, 
  ExecutionConfig, 
  ValidationResult,
  DEFAULT_EXECUTION_CONFIG 
} from './ExecutionService.js';
import { Config } from '../contexts/ConfigContext.js';
import { createLogger } from '../utils/logger.js';

const logger = createLogger('ExecutionServiceFactory');

/**
 * Result of service selection
 */
export interface ServiceSelectionResult {
  /** Selected execution service */
  service: ExecutionService;
  /** Mode that was selected */
  mode: ExecutionMode;
  /** Whether this was the preferred mode or a fallback */
  isPreferred: boolean;
  /** Validation result for the selected service */
  validation: ValidationResult;
  /** Services that were considered but rejected */
  rejected: { mode: ExecutionMode; reason: string }[];
}

/**
 * Factory for creating and selecting execution services
 */
export class ExecutionServiceFactory {
  private static services: Map<ExecutionMode, () => Promise<ExecutionService>> = new Map();
  private static initialized = false;

  /**
   * Initialize the factory with available services
   * This registers all execution service types
   */
  private static async initialize(): Promise<void> {
    if (this.initialized) return;

    // Register Python execution service
    this.services.set(ExecutionMode.PYTHON_CLI, async () => {
      const { PythonExecutionServiceAdapter } = await import('./PythonExecutionServiceAdapter.js');
      return new PythonExecutionServiceAdapter();
    });

    // Register Docker single-container service  
    this.services.set(ExecutionMode.DOCKER_SINGLE, async () => {
      const { DockerExecutionServiceAdapter } = await import('./DockerExecutionServiceAdapter.js');
      return new DockerExecutionServiceAdapter(ExecutionMode.DOCKER_SINGLE);
    });

    // Register Docker full-stack service
    this.services.set(ExecutionMode.DOCKER_STACK, async () => {
      const { DockerExecutionServiceAdapter } = await import('./DockerExecutionServiceAdapter.js');
      return new DockerExecutionServiceAdapter(ExecutionMode.DOCKER_STACK);
    });

    this.initialized = true;
    logger.info('ExecutionServiceFactory initialized with services:', Array.from(this.services.keys()));
  }

  /**
   * Select the best execution service for the given configuration
   * 
   * @param config - User configuration
   * @param executionConfig - Execution preferences
   * @returns Service selection result
   */
  static async selectService(
    config: Config, 
    executionConfig: ExecutionConfig = DEFAULT_EXECUTION_CONFIG
  ): Promise<ServiceSelectionResult> {
    await this.initialize();

    const rejected: { mode: ExecutionMode; reason: string }[] = [];
    
    // Determine mode preference order
    const modesToTry = this.getModesToTry(config, executionConfig);
    
    logger.info('Selecting execution service from modes:', modesToTry);

    // Try each mode in preference order
    for (let i = 0; i < modesToTry.length; i++) {
      const mode = modesToTry[i];
      const isPreferred = i === 0 && executionConfig.preferredMode === mode;

      try {
        logger.info(`Trying execution service: ${mode} (attempt ${i + 1}/${modesToTry.length})`);
        const service = await this.createService(mode);
        
        // Quick capability check
        const isSupported = await service.isSupported(config);
        logger.info(`Service ${mode} support check: ${isSupported}`);
        if (!isSupported) {
          rejected.push({ mode, reason: 'Service does not support current configuration' });
          service.cleanup();
          continue;
        }

        // Full validation
        logger.info(`Validating service: ${mode}`);
        const validation = await this.validateWithTimeout(service, config, executionConfig.validationTimeoutMs);
        logger.info(`Service ${mode} validation result: ${validation.valid} ${validation.error ? `(${validation.error})` : ''}`);
        
        if (validation.valid) {
          logger.info(`Selected execution service: ${mode} (preferred: ${isPreferred})`);
          return {
            service,
            mode,
            isPreferred,
            validation,
            rejected
          };
        } else {
          rejected.push({ mode, reason: validation.error || 'Validation failed' });
          service.cleanup();
        }

      } catch (error) {
        const errorMsg = error instanceof Error ? error.message : String(error);
        rejected.push({ mode, reason: `Service creation failed: ${errorMsg}` });
        logger.warn(`Failed to create service for mode ${mode}:`, { error: errorMsg });
      }
    }

    // No service could be selected
    const errorMsg = `No execution service available. Tried: ${modesToTry.join(', ')}`;
    logger.error(errorMsg, undefined, { rejected });
    throw new Error(errorMsg);
  }

  /**
   * Create a service for a specific mode
   * 
   * @param mode - Execution mode
   * @returns Created service instance
   */
  static async createService(mode: ExecutionMode): Promise<ExecutionService> {
    await this.initialize();

    const serviceFactory = this.services.get(mode);
    if (!serviceFactory) {
      throw new Error(`No service registered for execution mode: ${mode}`);
    }

    return serviceFactory();
  }

  /**
   * Get all available execution modes
   */
  static async getAvailableModes(): Promise<ExecutionMode[]> {
    await this.initialize();
    return Array.from(this.services.keys());
  }

  /**
   * Check if a specific mode is available
   */
  static async isModeAvailable(mode: ExecutionMode): Promise<boolean> {
    await this.initialize();
    return this.services.has(mode);
  }

  /**
   * Get service capabilities for a mode without creating the service
   */
  static async getModeCapabilities(mode: ExecutionMode): Promise<string[]> {
    const service = await this.createService(mode);
    const capabilities = service.getCapabilities();
    service.cleanup();
    
    const caps = [];
    if (capabilities.canExecute) caps.push('execution');
    if (capabilities.supportsStreaming) caps.push('streaming');
    if (capabilities.supportsParallel) caps.push('parallel');
    
    return caps;
  }

  /**
   * Determine which modes to try in preference order
   */
  private static getModesToTry(config: Config, executionConfig: ExecutionConfig): ExecutionMode[] {
    const modes: ExecutionMode[] = [];

    // Add preferred mode first if specified
    if (executionConfig.preferredMode) {
      modes.push(executionConfig.preferredMode);
    }

    // Add fallback modes (avoiding duplicates)
    for (const fallbackMode of executionConfig.fallbackModes) {
      if (!modes.includes(fallbackMode)) {
        modes.push(fallbackMode);
      }
    }

    // If no modes specified, use default order based on configuration
    if (modes.length === 0) {
      modes.push(...this.getDefaultModeOrder(config));
    }

    return modes;
  }

  /**
   * Get default mode order based on configuration hints
   */
  private static getDefaultModeOrder(config: Config): ExecutionMode[] {
    // Respect explicit deployment mode configuration first
    if (config.deploymentMode) {
      switch (config.deploymentMode) {
        case 'local-cli':
          return [ExecutionMode.PYTHON_CLI, ExecutionMode.DOCKER_SINGLE, ExecutionMode.DOCKER_STACK];
        case 'single-container':
          return [ExecutionMode.DOCKER_SINGLE, ExecutionMode.PYTHON_CLI, ExecutionMode.DOCKER_STACK];
        case 'full-stack':
          return [ExecutionMode.DOCKER_STACK, ExecutionMode.DOCKER_SINGLE, ExecutionMode.PYTHON_CLI];
      }
    }
    
    // Fallback logic: If observability is enabled, prefer full-stack for better monitoring
    if (config.observability) {
      return [ExecutionMode.DOCKER_STACK, ExecutionMode.DOCKER_SINGLE, ExecutionMode.PYTHON_CLI];
    }

    // If simple assessment, prefer lighter modes
    return [ExecutionMode.PYTHON_CLI, ExecutionMode.DOCKER_SINGLE, ExecutionMode.DOCKER_STACK];
  }

  /**
   * Validate service with timeout
   */
  private static async validateWithTimeout(
    service: ExecutionService, 
    config: Config, 
    timeoutMs: number
  ): Promise<ValidationResult> {
    const timeoutPromise = new Promise<ValidationResult>((_, reject) => {
      setTimeout(() => reject(new Error('Validation timeout')), timeoutMs);
    });

    try {
      return await Promise.race([
        service.validate(config),
        timeoutPromise
      ]);
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      return {
        valid: false,
        error: `Validation failed: ${errorMsg}`,
        issues: [{
          type: 'config',
          severity: 'error',
          message: errorMsg
        }],
        warnings: []
      };
    }
  }

  /**
   * Cleanup factory and all created services
   * Called on application shutdown
   */
  static cleanup(): void {
    // Services are cleaned up individually when no longer needed
    // This just resets the factory state
    this.initialized = false;
    logger.info('ExecutionServiceFactory cleaned up');
  }
}