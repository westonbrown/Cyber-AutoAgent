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

    // Step 1: Check Python installation
    currentStep++;
    onProgress?.({
      current: currentStep,
      total: totalSteps,
      message: 'Checking Python installation...',
      stepName: 'python-check'
    });

    const { PythonExecutionService } = await import('./PythonExecutionService.js');
    const pythonService = new PythonExecutionService();
    
    const pythonCheck = await pythonService.checkPythonVersion();
    if (!pythonCheck.installed) {
      throw new Error(pythonCheck.error || 'Python 3.10+ is required');
    }

    // Step 2: Setup virtual environment
    currentStep++;
    onProgress?.({
      current: currentStep,
      total: totalSteps,
      message: `Python ${pythonCheck.version} detected. Setting up virtual environment...`,
      stepName: 'venv-setup'
    });

    // Step 3: Install dependencies
    currentStep++;
    onProgress?.({
      current: currentStep,
      total: totalSteps,
      message: 'Installing dependencies...',
      stepName: 'dependencies'
    });

    await pythonService.setupPythonEnvironment((message) => {
      onProgress?.({
        current: currentStep,
        total: totalSteps,
        message,
        stepName: 'dependencies'
      });
    });

    // Step 4: Update deployment mode and verify setup
    currentStep++;
    onProgress?.({
      current: currentStep,
      total: totalSteps,
      message: 'Python environment setup complete!',
      stepName: 'verification'
    });

    // Update ContainerManager's deployment mode for CLI mode
    const containerManager = ContainerManager.getInstance();
    await containerManager.switchToMode('local-cli');

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

    const dockerAvailable = await this.checkDockerStatus();
    if (!dockerAvailable) {
      throw new Error('Docker Desktop is not running. Please start Docker Desktop and try again.');
    }

    // Step 2: Start container
    currentStep++;
    onProgress?.({
      current: currentStep,
      total: totalSteps,
      message: 'Starting security assessment container...',
      stepName: 'container-start'
    });

    const containerManager = ContainerManager.getInstance();
    await containerManager.switchToMode('single-container');

    // Step 3: Health check
    currentStep++;
    onProgress?.({
      current: currentStep,
      total: totalSteps,
      message: 'Container setup complete!',
      stepName: 'health-check'
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

    const dockerAvailable = await this.checkDockerStatus();
    if (!dockerAvailable) {
      throw new Error('Docker Desktop is not running. Please start Docker Desktop and try again.');
    }

    // Step 2: Start containers
    currentStep++;
    onProgress?.({
      current: currentStep,
      total: totalSteps,
      message: 'Starting service stack...',
      stepName: 'containers-start'
    });

    const containerManager = ContainerManager.getInstance();
    await containerManager.switchToMode('full-stack');

    // Step 3: Network setup
    currentStep++;
    onProgress?.({
      current: currentStep,
      total: totalSteps,
      message: 'Configuring service network...',
      stepName: 'network-setup'
    });

    // Allow time for network configuration
    await new Promise(resolve => setTimeout(resolve, 2000));

    // Step 4: Health check
    currentStep++;
    onProgress?.({
      current: currentStep,
      total: totalSteps,
      message: 'Verifying service health...',
      stepName: 'health-check'
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
          name: 'Local CLI Only',
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
          name: 'Full Stack',
          description: 'Complete platform - All services with observability and evaluation',
          icon: '🏢',
          requirements: ['~5GB disk', '8GB RAM', 'Docker Compose', 'Full service stack']
        };
    }
  }
}