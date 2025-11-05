/**
 * Docker Execution Service Adapter
 * 
 * Adapts the existing DirectDockerService and ContainerManager to implement the unified 
 * ExecutionService interface. Handles both single-container and full-stack modes.
 */

import { EventEmitter } from 'events';
import * as path from 'path';
import * as fs from 'fs/promises';
import * as fsSync from 'fs';
import { 
  ExecutionService, 
  ExecutionMode, 
  ValidationResult, 
  ExecutionHandle, 
  ExecutionResult, 
  ExecutionCapabilities 
} from './ExecutionService.js';
import { DirectDockerService } from './DirectDockerService.js';
import { ContainerManager } from './ContainerManager.js';
import { Config } from '../contexts/ConfigContext.js';
import { AssessmentParams } from '../types/Assessment.js';
import { createLogger } from '../utils/logger.js';

const logger = createLogger('DockerExecutionServiceAdapter');

/**
 * Adapter that wraps DirectDockerService and ContainerManager to implement ExecutionService interface
 */
export class DockerExecutionServiceAdapter extends EventEmitter implements ExecutionService {
  private dockerService: DirectDockerService;
  private containerManager: ContainerManager;
  private mode: ExecutionMode;
  private activeHandle?: ExecutionHandle;
  private containerProgressHandler: ((message: string) => void) | null = null;

  constructor(mode: ExecutionMode) {
    super();
    // Allow multiple UI subscribers (Terminal, useOperationManager, etc.)
    // without triggering noisy warnings. We still properly clean up listeners.
    this.setMaxListeners(25);
    if (mode !== ExecutionMode.DOCKER_SINGLE && mode !== ExecutionMode.DOCKER_STACK) {
      throw new Error(`Invalid Docker mode: ${mode}`);
    }
    
    this.mode = mode;
    this.dockerService = new DirectDockerService();
    this.containerManager = ContainerManager.getInstance();
    
    // Forward events from the underlying service
    this.dockerService.on('started', () => this.emit('started'));
    this.dockerService.on('event', (event) => this.emit('event', event));
    this.dockerService.on('complete', () => this.handleComplete());
    this.dockerService.on('stopped', () => this.emit('stopped'));
    this.dockerService.on('error', (error) => this.emit('error', error));
    
    // Forward container manager progress with stable reference for cleanup
    this.containerProgressHandler = (message: string) => this.emit('progress', message);
    this.containerManager.on('progress', this.containerProgressHandler);

    // Fallback kill-switch: if UI emits 'stop' before handle is returned, forward to service
    this.on('stop', async () => {
      try {
        await this.dockerService.stop();
      } catch {}
    });
  }

  getMode(): ExecutionMode {
    return this.mode;
  }

  getCapabilities(): ExecutionCapabilities {
    return {
      canExecute: true,
      supportsStreaming: true,
      supportsParallel: true, // Docker containers can run in parallel
      maxConcurrent: 5, // Reasonable limit for container resources
      requirements: [
        'Docker Engine running',
        'Docker Compose (for full-stack mode)',
        'Network access for model API calls',
        'Sufficient disk space for container images',
        'Sufficient memory for container execution'
      ]
    };
  }

  async isSupported(config: Config): Promise<boolean> {
    try {
      // Quick check if Docker is available
      return await DirectDockerService.checkDocker();
    } catch {
      return false;
    }
  }

  async validate(config: Config): Promise<ValidationResult> {
    const issues: any[] = [];
    const warnings: string[] = [];

    try {
      // Check Docker availability
      const dockerAvailable = await DirectDockerService.checkDocker();
      if (!dockerAvailable) {
        issues.push({
          type: 'docker',
          severity: 'error',
          message: 'Docker Engine is not running',
          suggestion: 'Start Docker Desktop or Docker daemon'
        });
        
        // If Docker isn't available, no point checking other things
        return {
          valid: false,
          error: 'Docker Engine is not available',
          issues,
          warnings
        };
      }

      // Check container status
      const containerStatus = await this.containerManager.checkContainerStatus();
      
      if (this.mode === ExecutionMode.DOCKER_STACK) {
        const fullStackStatus = containerStatus.requiredContainers['full-stack'];
        if (fullStackStatus.missing.length > 0) {
          warnings.push(`${fullStackStatus.missing.length} containers need to be created for full-stack mode`);
        }
        if (fullStackStatus.needsRestart.length > 0) {
          warnings.push(`${fullStackStatus.needsRestart.length} containers need to be restarted`);
        }
      } else {
        const singleStatus = containerStatus.requiredContainers['single-container'];
        if (singleStatus.missing.length > 0) {
          warnings.push('Container will be created for single-container mode');
        }
        if (singleStatus.needsRestart.length > 0) {
          warnings.push('Container needs to be restarted');
        }
      }

      // Check model provider credentials (same as Python service)
      if (config.modelProvider === 'bedrock') {
        if (!config.awsAccessKeyId && !config.awsBearerToken) {
          issues.push({
            type: 'credentials',
            severity: 'error',
            message: 'AWS credentials required for Bedrock model provider',
            suggestion: 'Configure AWS credentials in settings'
          });
        }
      } else if (config.modelProvider === 'ollama') {
        if (!config.ollamaHost) {
          warnings.push('Using default Ollama host (localhost:11434)');
        }
      }

      // Check Docker image availability
      try {
        const { exec } = await import('node:child_process');
        const { promisify } = await import('node:util');
        const execAsync = promisify(exec);
        await execAsync('docker image inspect cyber-autoagent:latest');
        logger.info('Docker image validation: SUCCESS');
      } catch (error) {
        logger.error('Docker image validation: FAILED', error);
        // In development, this should be a warning, not an error
        const isDevelopment = process.env.NODE_ENV === 'development' || process.env.DEV === 'true';
        if (isDevelopment) {
          warnings.push('Docker image cyber-autoagent:latest not found. Build with: docker build -t cyber-autoagent:latest .');
        } else {
          issues.push({
            type: 'docker',
            severity: 'error',
            message: 'Cyber-AutoAgent Docker image not found',
            suggestion: 'Build the Docker image or pull from registry'
          });
        }
      }

      // Check filesystem permissions for volume mounts
      try {
        // Resolve output directory relative to project root if it's a relative path
        let outputDir = config.outputDir || './outputs';
        logger.info('Docker validation: checking filesystem permissions', { outputDir });
        
        if (!path.isAbsolute(outputDir)) {
          // For Docker mode, find project root by searching for pyproject.toml
          let currentDir = path.dirname(new URL(import.meta.url).pathname);
          logger.info('Docker validation: starting path resolution', { currentDir });
          
          while (currentDir !== path.dirname(currentDir)) {
            const pyprojectPath = path.join(currentDir, 'pyproject.toml');
            if (fsSync.existsSync(pyprojectPath)) {
              outputDir = path.resolve(currentDir, outputDir);
              logger.info('Docker validation: resolved output dir', { outputDir });
              break;
            }
            currentDir = path.dirname(currentDir);
          }
        }
        
        // Ensure output directory exists
        await fs.mkdir(outputDir, { recursive: true });
        
        const testFile = path.join(outputDir, `.test-${Date.now()}`);
        await fs.writeFile(testFile, 'test');
        await fs.unlink(testFile);
        logger.info('Docker validation: filesystem test SUCCESS');
      } catch (error) {
        logger.error('Docker validation: filesystem test FAILED', error);
        issues.push({
          type: 'filesystem',
          severity: 'error',
          message: 'Cannot write to output directory',
          suggestion: 'Check output directory permissions'
        });
      }

      // Check network connectivity (basic check)
      if (config.modelProvider === 'bedrock') {
        // AWS connectivity is verified during actual execution
        warnings.push('Ensure network access to AWS Bedrock endpoints');
      }

      const hasErrors = issues.some(issue => issue.severity === 'error');
      
      return {
        valid: !hasErrors,
        error: hasErrors ? 'Docker execution environment validation failed' : undefined,
        issues,
        warnings
      };

    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      return {
        valid: false,
        error: `Validation error: ${errorMsg}`,
        issues: [{
          type: 'docker',
          severity: 'error',
          message: errorMsg
        }],
        warnings
      };
    }
  }

  async execute(params: AssessmentParams, config: Config): Promise<ExecutionHandle> {
    if (this.activeHandle?.isActive()) {
      throw new Error('Docker execution already active');
    }

    const startTime = Date.now();
    const handleId = `docker-${this.mode}-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;

    // Ensure container manager is in the correct mode
    const deploymentMode = this.mode === ExecutionMode.DOCKER_STACK ? 'full-stack' : 'single-container';
    await this.containerManager.switchToMode(deploymentMode);

    // Create a promise that resolves when the assessment actually completes
    // This waits for the 'complete' event from DirectDockerService, not just the exec start
    const resultPromise = new Promise<ExecutionResult>((resolve, reject) => {
      const completeHandler = () => {
        cleanup();
        resolve({
          success: true,
          durationMs: Date.now() - startTime,
          stepsExecuted: config.iterations,
          findingsCount: 0 // Findings are tracked in the output reports
        });
      };

      const errorHandler = (error: Error) => {
        cleanup();
        resolve({
          success: false,
          error: error instanceof Error ? error.message : String(error),
          durationMs: Date.now() - startTime
        });
      };

      const stoppedHandler = () => {
        cleanup();
        resolve({
          success: false,
          error: 'Assessment stopped before completion',
          durationMs: Date.now() - startTime
        });
      };

      const cleanup = () => {
        this.dockerService.removeListener('complete', completeHandler);
        this.dockerService.removeListener('error', errorHandler);
        this.dockerService.removeListener('stopped', stoppedHandler);
      };

      this.dockerService.once('complete', completeHandler);
      this.dockerService.once('error', errorHandler);
      this.dockerService.once('stopped', stoppedHandler);
    });

    // Start the Docker execution (returns immediately after starting container exec)
    const executionPromise = this.dockerService.executeAssessment(params, config);

    const handle: ExecutionHandle = {
      id: handleId,
      pid: undefined, // Docker manages container processes
      result: resultPromise,
      stop: async () => {
        await this.dockerService.stop();
      },
      isActive: () => this.dockerService.isAssessing()
    };

    this.activeHandle = handle;

    // Handle immediate execution errors
    executionPromise.catch((error) => {
      logger.error('Docker execution failed to start:', error);
      this.emit('error', error);
    });

    return handle;
  }

  async setup(config: Config, onProgress?: (message: string) => void): Promise<void> {
    logger.info(`Setting up Docker execution environment for ${this.mode} mode`);
    
    // Switch to appropriate deployment mode
    const deploymentMode = this.mode === ExecutionMode.DOCKER_STACK ? 'full-stack' : 'single-container';
    
    // Container manager handles setup progress via events
    if (onProgress) {
      const progressHandler = (message: string) => onProgress(message);
      this.containerManager.on('progress', progressHandler);
      
      try {
        await this.containerManager.switchToMode(deploymentMode);
      } finally {
        this.containerManager.removeListener('progress', progressHandler);
      }
    } else {
      await this.containerManager.switchToMode(deploymentMode);
    }
  }

  cleanup(): void {
    if (this.dockerService) {
      this.dockerService.cleanup();
    }
    // Note: ContainerManager is singleton, don't cleanup here
    if (this.containerProgressHandler) {
      try {
        this.containerManager.removeListener('progress', this.containerProgressHandler);
      } catch {}
      this.containerProgressHandler = null;
    }
    this.removeAllListeners();
  }

  isActive(): boolean {
    return this.dockerService?.isAssessing() ?? false;
  }

  private handleComplete(): void {
    if (this.activeHandle) {
      this.activeHandle = undefined;
    }
    this.emit('complete', {
      success: true,
      durationMs: 0 // Will be calculated by handle
    });
  }

  // EventEmitter is now inherited from the base class
}

// Export the adapter as the Docker service
export { DockerExecutionServiceAdapter as DockerExecutionService };