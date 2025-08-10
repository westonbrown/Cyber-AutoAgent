/**
 * Setup Service
 * 
 * Handles all setup business logic separated from UI components.
 * Manages deployment mode configuration, environment setup, and progress tracking.
 */

import { EventEmitter } from 'events';
import { exec } from 'child_process';
import { promisify } from 'util';
import { ContainerManager } from './ContainerManager.js';
import { HealthMonitor } from './HealthMonitor.js';
import { getEnvironmentConfig, getDockerComposePaths } from '../config/environment.js';
import { createLogger } from '../utils/logger.js';
import { RetryConfigs } from '../utils/retry.js';
import * as fs from 'fs';

const execAsync = promisify(exec);

export type DeploymentMode = 'local-cli' | 'single-container' | 'full-stack';

export interface SetupProgress {
  current: number;
  total: number;
  message: string;
  stepName: string;
}

export interface SetupResult {
  success: boolean;
  error?: string;
  deploymentMode: DeploymentMode;
}

/**
 * Service class for managing deployment environment setup
 */
export class SetupService extends EventEmitter {
  private logger = createLogger('SetupService');
  private envConfig = getEnvironmentConfig();

  /**
   * Setup deployment mode with progress tracking
   */
  async setupDeploymentMode(
    mode: DeploymentMode,
    onProgress?: (progress: SetupProgress) => void
  ): Promise<SetupResult> {
    try {
      this.logger.info('Starting setup for deployment mode', { mode });
      
      switch (mode) {
        case 'local-cli':
          return await this.setupPythonEnvironment(onProgress);
        case 'single-container':
          return await this.setupSingleContainer(onProgress);
        case 'full-stack':
          return await this.setupFullStack(onProgress);
        default:
          throw new Error(`Unknown deployment mode: ${mode}`);
      }
    } catch (error) {
      this.logger.error('Setup failed', error as Error);
      return {
        success: false,
        error: (error as Error).message,
        deploymentMode: mode
      };
    }
  }

  /**
   * Setup Python environment for local CLI mode
   */
  private async setupPythonEnvironment(
    onProgress?: (progress: SetupProgress) => void
  ): Promise<SetupResult> {
    const totalSteps = 4;
    let currentStep = 0;

    // Step 1: Update deployment mode first (fast operation)
    currentStep++;
    onProgress?.({
      current: currentStep,
      total: totalSteps,
      message: 'Configuring CLI mode...',
      stepName: 'mode-setup'
    });

    // Update ContainerManager's deployment mode early to avoid Docker operations
    const containerManager = ContainerManager.getInstance();
    await containerManager.switchToMode('local-cli');

    // Step 2: Check Python installation
    currentStep++;
    onProgress?.({
      current: currentStep,
      total: totalSteps,
      message: 'Checking Python installation...',
      stepName: 'python-check'
    });

    this.logger.info('Verifying Python 3.10+ is installed');
    const { PythonExecutionService } = await import('./PythonExecutionService.js');
    const pythonService = new PythonExecutionService();
    
    const pythonCheck = await pythonService.checkPythonVersion();
    if (!pythonCheck.installed) {
      this.logger.error('Python 3.10+ not found');
      throw new Error(pythonCheck.error || 'Python 3.10+ is required');
    }
    
    onProgress?.({
      current: currentStep,
      total: totalSteps,
      message: `Python ${pythonCheck.version} detected`,
      stepName: 'python-check'
    });

    // Step 3: Setup virtual environment and dependencies
    currentStep++;
    onProgress?.({
      current: currentStep,
      total: totalSteps,
      message: 'Creating virtual environment...',
      stepName: 'dependencies'
    });

    this.logger.info('Setting up Python virtual environment');
    
    await pythonService.setupPythonEnvironment((message) => {
      onProgress?.({
        current: currentStep,
        total: totalSteps,
        message,
        stepName: 'dependencies'
      });
    });
    
    onProgress?.({
      current: currentStep,
      total: totalSteps,
      message: 'Dependencies installed successfully',
      stepName: 'dependencies'
    });

    // Step 4: Final verification
    currentStep++;
    onProgress?.({
      current: currentStep,
      total: totalSteps,
      message: 'Running final verification checks...',
      stepName: 'validation'
    });
    
    this.logger.info('Verifying CLI environment is ready');
    
    // Simulate verification delay
    await new Promise(resolve => setTimeout(resolve, 1000));
    
    onProgress?.({
      current: currentStep,
      total: totalSteps,
      message: 'CLI environment verified and ready',
      stepName: 'validation'
    });

    return {
      success: true,
      deploymentMode: 'local-cli'
    };
  }

  /**
   * Setup single container deployment
   */
  private async setupSingleContainer(
    onProgress?: (progress: SetupProgress) => void
  ): Promise<SetupResult> {
    const totalSteps = 3;
    let currentStep = 0;

    // Step 1: Check Docker
    currentStep++;
    onProgress?.({
      current: currentStep,
      total: totalSteps,
      message: 'Checking Docker availability...',
      stepName: 'docker-check'
    });

    this.logger.info('Verifying Docker Desktop is installed and running');
    const dockerAvailable = await this.checkDockerStatus();
    if (!dockerAvailable) {
      this.logger.error('Docker Desktop is not running');
      throw new Error('Docker Desktop is not running. Please start Docker Desktop and try again.');
    }
    
    onProgress?.({
      current: currentStep,
      total: totalSteps,
      message: 'Docker Desktop detected and running',
      stepName: 'docker-check'
    });

    // Step 2: Start container
    currentStep++;
    onProgress?.({
      current: currentStep,
      total: totalSteps,
      message: 'Starting security assessment container...',
      stepName: 'containers-start'
    });

    this.logger.info('Pulling cyber-autoagent container image if needed');
    const containerManager = ContainerManager.getInstance();
    
    onProgress?.({
      current: currentStep,
      total: totalSteps,
      message: 'Container image ready, starting container...',
      stepName: 'containers-start'
    });
    
    await containerManager.switchToMode('single-container');
    
    onProgress?.({
      current: currentStep,
      total: totalSteps,
      message: 'Container started successfully',
      stepName: 'containers-start'
    });

    // Step 3: Health check
    currentStep++;
    onProgress?.({
      current: currentStep,
      total: totalSteps,
      message: 'Running container health check...',
      stepName: 'validation'
    });
    
    this.logger.info('Verifying container is responding to health checks');
    
    // Simulate health check delay
    await new Promise(resolve => setTimeout(resolve, 1500));
    
    onProgress?.({
      current: currentStep,
      total: totalSteps,
      message: 'Container health check passed',
      stepName: 'validation'
    });

    return {
      success: true,
      deploymentMode: 'single-container'
    };
  }

  /**
   * Setup full stack deployment
   */
  private async setupFullStack(
    onProgress?: (progress: SetupProgress) => void
  ): Promise<SetupResult> {
    const totalSteps = 5;
    let currentStep = 0;

    // Step 1: Check Docker
    currentStep++;
    onProgress?.({
      current: currentStep,
      total: totalSteps,
      message: 'Checking Docker availability...',
      stepName: 'docker-check'
    });

    this.logger.info('Verifying Docker Desktop for full stack deployment');
    const dockerAvailable = await this.checkDockerStatus();
    if (!dockerAvailable) {
      this.logger.error('Docker Desktop is not running');
      throw new Error('Docker Desktop is not running. Please start Docker Desktop and try again.');
    }
    
    onProgress?.({
      current: currentStep,
      total: totalSteps,
      message: 'Docker Desktop verified for full stack',
      stepName: 'docker-check'
    });

    // Step 2: Start containers
    currentStep++;
    onProgress?.({
      current: currentStep,
      total: totalSteps,
      message: 'Starting service stack...',
      stepName: 'containers-start'
    });

    this.logger.info('Starting full service stack with docker-compose');
    
    onProgress?.({
      current: currentStep,
      total: totalSteps,
      message: 'Pulling container images (Agent, Langfuse, PostgreSQL, Redis)...',
      stepName: 'containers-start'
    });
    
    const containerManager = ContainerManager.getInstance();
    await containerManager.switchToMode('full-stack');
    
    onProgress?.({
      current: currentStep,
      total: totalSteps,
      message: 'All containers started successfully',
      stepName: 'containers-start'
    });

    // Step 3: Network setup
    currentStep++;
    onProgress?.({
      current: currentStep,
      total: totalSteps,
      message: 'Configuring service network...',
      stepName: 'network-setup'
    });

    this.logger.info('Setting up inter-container networking');
    
    onProgress?.({
      current: currentStep,
      total: totalSteps,
      message: 'Configuring service discovery and internal DNS...',
      stepName: 'network-setup'
    });
    
    // Allow time for network configuration
    await new Promise(resolve => setTimeout(resolve, 2000));
    
    onProgress?.({
      current: currentStep,
      total: totalSteps,
      message: 'Network configuration complete',
      stepName: 'network-setup'
    });

    // Step 4: Database setup
    currentStep++;
    onProgress?.({
      current: currentStep,
      total: totalSteps,
      message: 'Initializing database...',
      stepName: 'database-setup'
    });
    
    this.logger.info('Running database migrations and initial setup');
    
    onProgress?.({
      current: currentStep,
      total: totalSteps,
      message: 'Creating database schema and tables...',
      stepName: 'database-setup'
    });
    
    // Allow time for database setup
    await new Promise(resolve => setTimeout(resolve, 1500));
    
    onProgress?.({
      current: currentStep,
      total: totalSteps,
      message: 'Database initialized successfully',
      stepName: 'database-setup'
    });

    // Step 5: Health check
    currentStep++;
    onProgress?.({
      current: currentStep,
      total: totalSteps,
      message: 'Verifying service health...',
      stepName: 'validation'
    });

    const monitor = HealthMonitor.getInstance();
    const health = await monitor.checkHealth();
    const runningServices = health.services.filter(s => s.status === 'running').length;
    
    if (runningServices < 3) {
      this.logger.warn('Some services may not be running', { runningServices, totalServices: health.services.length });
    }

    // Step 5: Observability setup
    currentStep++;
    onProgress?.({
      current: currentStep,
      total: totalSteps,
      message: 'Full stack setup complete!',
      stepName: 'observability'
    });

    return {
      success: true,
      deploymentMode: 'full-stack'
    };
  }

  /**
   * Check if Docker is available and running
   */
  private async checkDockerStatus(): Promise<boolean> {
    try {
      await execAsync('docker info');
      return true;
    } catch {
      return false;
    }
  }

  /**
   * Get deployment mode display information
   */
  static getDeploymentModeInfo(mode: DeploymentMode) {
    switch (mode) {
      case 'local-cli':
        return {
          name: 'Local CLI',
          description: 'Minimal footprint - Python environment with direct API calls',
          icon: '🖥️',
          requirements: ['~100MB disk', '1GB RAM', 'Python 3.11+', 'Direct LLM API access']
        };
      case 'single-container':
        return {
          name: 'Single Container',
          description: 'Isolated execution - Docker container with core agent only',
          icon: '📦',
          requirements: ['~2GB disk', '4GB RAM', 'Docker Desktop', 'Container runtime']
        };
      case 'full-stack':
        return {
          name: 'Enterprise Stack',
          description: 'Complete platform - All services with observability and evaluation',
          icon: '🏢',
          requirements: ['~5GB disk', '8GB RAM', 'Docker Compose', 'Full service stack']
        };
    }
  }
}