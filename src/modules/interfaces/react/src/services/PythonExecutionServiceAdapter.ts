/**
 * Python Execution Service Adapter
 * 
 * Adapts the existing PythonExecutionService to implement the unified ExecutionService interface.
 * This allows the Python execution service to work with the new ExecutionServiceFactory
 * while maintaining backward compatibility.
 */

import { EventEmitter } from 'events';
import * as path from 'path';
import * as fs from 'fs/promises';
import { 
  ExecutionService, 
  ExecutionMode, 
  ValidationResult, 
  ExecutionHandle, 
  ExecutionResult, 
  ExecutionCapabilities 
} from './ExecutionService.js';
import { PythonExecutionService } from './PythonExecutionService.js';
import { Config } from '../contexts/ConfigContext.js';
import { AssessmentParams } from '../types/Assessment.js';
import { createLogger } from '../utils/logger.js';

const logger = createLogger('PythonExecutionServiceAdapter');

/**
 * Adapter that wraps PythonExecutionService to implement ExecutionService interface
 */
export class PythonExecutionServiceAdapter extends EventEmitter implements ExecutionService {
  private pythonService: PythonExecutionService;
  private activeHandle?: ExecutionHandle;

  constructor() {
    super();
    this.pythonService = new PythonExecutionService();
    
    // Forward events from the underlying service
    this.pythonService.on('started', () => this.emit('started'));
    this.pythonService.on('event', (event) => this.emit('event', event));
    this.pythonService.on('complete', () => this.handleComplete());
    this.pythonService.on('stopped', () => this.emit('stopped'));
    this.pythonService.on('error', (error) => this.emit('error', error));
    this.pythonService.on('progress', (message) => this.emit('progress', message));
  }

  getMode(): ExecutionMode {
    return ExecutionMode.PYTHON_CLI;
  }

  getCapabilities(): ExecutionCapabilities {
    return {
      canExecute: true,
      supportsStreaming: true,
      supportsParallel: false, // Python service creates new instances
      maxConcurrent: 1,
      requirements: [
        'Python 3.10+',
        'Virtual environment support',
        'Pip package manager',
        'Network access for model API calls'
      ]
    };
  }

  async isSupported(config: Config): Promise<boolean> {
    try {
      // Quick check if Python is available
      const pythonCheck = await this.pythonService.checkPythonVersion();
      return pythonCheck.installed;
    } catch (error) {
      logger.error('Python check failed:', error);
      return false;
    }
  }

  async validate(config: Config): Promise<ValidationResult> {
    const issues: any[] = [];
    const warnings: string[] = [];

    try {
      // Check Python version
      const pythonCheck = await this.pythonService.checkPythonVersion();
      if (!pythonCheck.installed) {
        issues.push({
          type: 'python',
          severity: 'error',
          message: pythonCheck.error || 'Python 3.10+ is required',
          suggestion: 'Install Python 3.10 or higher from https://python.org'
        });
      }

      // Check environment status
      const envStatus = await this.pythonService.checkEnvironmentStatus();
      
      if (!envStatus.venvValid) {
        if (envStatus.venvExists) {
          issues.push({
            type: 'python',
            severity: 'error',
            message: 'Virtual environment exists but is corrupted',
            suggestion: 'Delete .venv directory and run setup again'
          });
        } else {
          warnings.push('Virtual environment will be created during setup');
        }
      }

      if (!envStatus.dependenciesInstalled) {
        warnings.push('Python dependencies will be installed during setup');
      }

      if (!envStatus.packageInstalled) {
        warnings.push('Cyber-AutoAgent package will be installed during setup');
      }

      // Check model provider credentials
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

      // Check filesystem permissions
      try {
        // Resolve output directory relative to project root if it's a relative path
        let outputDir = config.outputDir || './outputs';
        if (!path.isAbsolute(outputDir)) {
          // Get project root from the Python service
          const projectRoot = (this.pythonService as any).projectRoot;
          if (projectRoot) {
            outputDir = path.resolve(projectRoot, outputDir);
          }
        }
        
        // Ensure output directory exists
        await fs.mkdir(outputDir, { recursive: true });
        
        const testFile = path.join(outputDir, `.test-${Date.now()}`);
        await fs.writeFile(testFile, 'test');
        await fs.unlink(testFile);
      } catch (error) {
        issues.push({
          type: 'filesystem',
          severity: 'error',
          message: 'Cannot write to output directory',
          suggestion: 'Check output directory permissions'
        });
      }

      const hasErrors = issues.some(issue => issue.severity === 'error');
      
      return {
        valid: !hasErrors,
        error: hasErrors ? 'Python execution environment validation failed' : undefined,
        issues,
        warnings
      };

    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      return {
        valid: false,
        error: `Validation error: ${errorMsg}`,
        issues: [{
          type: 'python',
          severity: 'error',
          message: errorMsg
        }],
        warnings
      };
    }
  }

  async execute(params: AssessmentParams, config: Config): Promise<ExecutionHandle> {
    if (this.activeHandle?.isActive()) {
      throw new Error('Python execution already active');
    }

    const startTime = Date.now();
    const handleId = `python-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;

    // Start the Python execution
    const executionPromise = this.pythonService.executeAssessment(params, config);

    const handle: ExecutionHandle = {
      id: handleId,
      pid: undefined, // PythonExecutionService manages PID internally
      result: executionPromise.then(() => ({
        success: true,
        durationMs: Date.now() - startTime,
        stepsExecuted: config.iterations,
        findingsCount: 0 // Findings are tracked in the output reports
      })).catch((error) => ({
        success: false,
        error: error instanceof Error ? error.message : String(error),
        durationMs: Date.now() - startTime
      })),
      stop: async () => {
        await this.pythonService.stop();
      },
      isActive: () => this.pythonService.isActive()
    };

    this.activeHandle = handle;
    
    // Execute in background
    executionPromise.catch((error) => {
      logger.error('Python execution failed:', error);
      this.emit('error', error);
    });

    return handle;
  }

  async setup(config: Config, onProgress?: (message: string) => void): Promise<void> {
    logger.info('Setting up Python execution environment');
    await this.pythonService.setupPythonEnvironment(onProgress);
  }

  async sendUserInput(input: string): Promise<void> {
    if (!this.pythonService) {
      throw new Error('Python service not initialized');
    }
    return this.pythonService.sendUserInput(input);
  }

  cleanup(): void {
    if (this.pythonService) {
      this.pythonService.cleanup();
    }
    this.removeAllListeners();
  }

  isActive(): boolean {
    return this.pythonService?.isActive() ?? false;
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

// Export the adapter as the main Python service
export { PythonExecutionServiceAdapter as PythonExecutionService };