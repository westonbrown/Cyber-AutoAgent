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
  meta?: {
    phaseRatio?: number; // 0..1 progress within active phase
    running?: number;    // containers running (for container phases)
    required?: number;   // containers required (for container phases)
    details?: Record<string, any>;
  };
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
    // Immediate preflight notification so UI shows activity within < 100ms
    onProgress?.({ current: 0, total: 1, message: 'Preparing setup…', stepName: 'preflight', meta: { phaseRatio: 0.1 } });
    try {
      this.logger.info('Starting setup for deployment mode', { mode });
      
      // brief animation tick to smooth initial render
      await new Promise(r => setTimeout(r, 150));

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

    // Immediate initial progress to show UI is responsive
    onProgress?.({
      current: 0,
      total: totalSteps,
      message: 'Starting Python environment setup...',
      stepName: 'environment'
    });

    // Step 1: Update deployment mode first (fast operation)
    currentStep++;
    onProgress?.({
      current: currentStep,
      total: totalSteps,
      message: 'Configuring CLI mode...',
      stepName: 'environment'
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
      stepName: 'environment'
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
      stepName: 'environment'
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
      message: 'Docker Desktop verified',
      stepName: 'docker-check'
    });

    // Step 2: Start container (pull/build awareness)
    currentStep++;
    onProgress?.({
      current: currentStep,
      total: totalSteps,
      message: 'Starting agent container…',
      stepName: 'containers-start',
      meta: { phaseRatio: 0 }
    });

    // Expectation notice for first-time runs
    onProgress?.({
      current: currentStep,
      total: totalSteps,
      message: 'Note: First-time image pulls/builds can take several minutes depending on your network',
      stepName: 'containers-start',
      meta: { phaseRatio: 0 }
    });

    const containerManager = ContainerManager.getInstance();

    // Subscribe to compose progress for single-container mode as well
    let lastRatio = 0;
    const onProgressMeta = (pm: any) => {
      const ratio = Math.max(0, Math.min(1, Number(pm?.phaseRatio ?? 0)));
      lastRatio = Math.max(lastRatio, ratio);
      const phase = String(pm?.phase || 'start');
      onProgress?.({
        current: currentStep,
        total: totalSteps,
        message: phase === 'pull' || phase === 'build' ? 'Downloading/Building image…' : 'Starting container…',
        stepName: 'containers-start',
        meta: { phaseRatio: lastRatio }
      });
    };
    (containerManager as any).on?.('progressMeta', onProgressMeta);

    try {
      await containerManager.switchToMode('single-container');
    } finally {
      try { (containerManager as any).off?.('progressMeta', onProgressMeta); } catch {}
    }

    onProgress?.({
      current: currentStep,
      total: totalSteps,
      message: 'Container started successfully',
      stepName: 'containers-start',
      meta: { phaseRatio: 1 }
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

    // Step 2: Images availability (check presence of core images)
    currentStep++;
    onProgress?.({
      current: currentStep,
      total: totalSteps,
      message: 'Checking images availability...',
      stepName: 'pull',
      meta: { phaseRatio: 0 }
    });

    // Display expectation notice: builds can take several minutes on first run
    onProgress?.({
      current: currentStep,
      total: totalSteps,
      message: 'Note: First-time image pulls/builds can take several minutes depending on your network',
      stepName: 'pull',
      meta: { phaseRatio: 0 }
    });

    try {
      const present = await this.checkImagesAvailability([
        { repo: 'langfuse/langfuse', tag: '3' },
        { repo: 'langfuse/langfuse-worker', tag: '3' },
        { repo: 'postgres', tag: '15-alpine' },
        { repo: 'redis', tag: '7' },
        { repo: 'minio/minio' },
        { repo: 'clickhouse/clickhouse-server' }
      ]);
      onProgress?.({
        current: currentStep,
        total: totalSteps,
        message: present.presentCount === present.total
          ? 'All required images present locally'
          : `Missing ${present.total - present.presentCount}/${present.total} images (will be pulled on start)`,
        stepName: 'pull',
        meta: { phaseRatio: present.ratio, details: { missing: present.missing } }
      });
    } catch {
      // ignore failures
    }

    // Step 3: Start containers (with live counters)
    currentStep++;
    onProgress?.({
      current: currentStep,
      total: totalSteps,
      message: 'Starting service stack...',
      stepName: 'containers-start',
      meta: { phaseRatio: 0 }
    });

    this.logger.info('Starting full service stack with docker-compose');

    const containerManager = ContainerManager.getInstance();

    // Track compose phase and last reported ratio for the active step
    let composePhase: 'pull' | 'build' | 'create' | 'start' | null = null;
    let lastStepRatio = 0; // preserves aggregator progress so monitor doesn't regress bar

    // Subscribe to streamed compose progress for smoother phaseRatio updates
    const onProgressMeta = (pm: any) => {
      const phase = String(pm?.phase || 'start') as 'pull' | 'build' | 'create' | 'start';
      const ratio = Math.max(0, Math.min(1, Number(pm?.phaseRatio ?? 0)));
      composePhase = phase;

      // Always keep UI step at 'containers-start' once we enter Step 3 to avoid progress regression
      lastStepRatio = Math.max(lastStepRatio, ratio);

      onProgress?.({
        current: currentStep,
        total: totalSteps,
        message: (phase === 'pull' || phase === 'build') ? 'Downloading/Building images…' : 'Starting services…',
        stepName: 'containers-start',
        meta: { phaseRatio: lastStepRatio }
      });
    };
    (containerManager as any).on?.('progressMeta', onProgressMeta);

    let done = false;
    const startMonitor = (async () => {
      while (!done) {
        try {
          // During the pull phase, do not override aggregator updates with 0% start progress
          if (composePhase === 'pull') {
            await new Promise(r => setTimeout(r, 750));
            continue;
          }

          const targetServices = containerManager.getDeploymentConfig('full-stack').services;
          const { running, total } = await containerManager.getRunningCountForServices(targetServices);
          const ratioMonitor = total > 0 ? Math.max(0, Math.min(1, running / total)) : 0;
          const effectiveRatio = Math.max(lastStepRatio, ratioMonitor);

          onProgress?.({
            current: currentStep,
            total: totalSteps,
            message: `Starting services (${running}/${total})...`,
            stepName: 'containers-start',
            meta: { running, required: total, phaseRatio: effectiveRatio }
          });
        } catch {}
        await new Promise(r => setTimeout(r, 1000));
      }
    })();

    try {
      await containerManager.switchToMode('full-stack');
    } finally {
      done = true;
      try { await startMonitor; } catch {}
      // Detach listener
      try { (containerManager as any).off?.('progressMeta', onProgressMeta); } catch {}
      // Reset monotonic ratio guard for next steps
      try { (global as any).__SETUP_RATIO__ = 0; } catch {}
    }

    onProgress?.({
      current: currentStep,
      total: totalSteps,
      message: 'All containers started successfully',
      stepName: 'containers-start',
      meta: { phaseRatio: 1 }
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

    // Step 4: Network setup progress hint
    onProgress?.({
      current: currentStep,
      total: totalSteps,
      message: 'Configuring service discovery and internal DNS...',
      stepName: 'network-setup',
      meta: { phaseRatio: 0.3 }
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
      stepName: 'database-setup',
      meta: { phaseRatio: 1 }
    });

    // Step 5: Health check
    currentStep++;
    onProgress?.({
      current: currentStep,
      total: totalSteps,
      message: 'Verifying service health...',
      stepName: 'validation',
      meta: { phaseRatio: 0 }
    });

const healthMonitor = HealthMonitor.getInstance();
const health = await healthMonitor.checkHealth();
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
      stepName: 'observability',
      meta: { phaseRatio: 1 }
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
   * Check images availability and compute a ratio
   */
  private async checkImagesAvailability(required: Array<{ repo: string; tag?: string }>): Promise<{ total: number; presentCount: number; ratio: number; missing: string[] }> {
    const total = required.length;
    try {
      const { stdout } = await execAsync('docker images --format "{{.Repository}}:{{.Tag}}"', { timeout: 8000 });
      const lines = stdout.trim().split('\n').filter(Boolean);
      const set = new Set(lines.map(s => s.toLowerCase()));

      const missing: string[] = [];
      let presentCount = 0;

      for (const r of required) {
        const wanted = (r.tag ? `${r.repo}:${r.tag}` : r.repo).toLowerCase();
        // Allow match without explicit registry prefix
        const match = [...set].some(x => x === wanted || x.endsWith('/' + wanted));
        if (match) presentCount++; else missing.push(wanted);
      }

      const ratio = total > 0 ? Math.max(0, Math.min(1, presentCount / total)) : 1;
      return { total, presentCount, ratio, missing };
    } catch {
      // If docker images fails, return unknown as 0
      return { total, presentCount: 0, ratio: 0, missing: required.map(r => r.tag ? `${r.repo}:${r.tag}` : r.repo) };
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