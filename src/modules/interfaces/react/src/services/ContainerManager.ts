/**
 * Container Manager Service
 * Handles Docker Compose orchestration for different deployment modes
 * Manages container lifecycle based on selected deployment configuration
 */

import { exec } from 'child_process';
import { promisify } from 'util';
import * as path from 'path';
import * as fs from 'fs';
import { createLogger } from '../utils/logger.js';
import { RetryConfigs } from '../utils/retry.js';
import { EventEmitter } from 'events';

const execAsync = promisify(exec);

export type DeploymentMode = 'local-cli' | 'single-container' | 'full-stack';

export interface ContainerInfo {
  name: string;
  status: string;
  health?: string;
}

export interface DeploymentConfig {
  mode: DeploymentMode;
  services: string[];
  composeFile: string;
  description: string;
}

/**
 * Container Manager - Professional Docker orchestration service
 * Manages deployment modes and container lifecycle for Cyber-AutoAgent
 */
export class ContainerManager extends EventEmitter {
  private static instance: ContainerManager;
  private readonly logger = createLogger('ContainerManager');
  private currentMode: DeploymentMode = 'full-stack';
  private initialized = false;

  private readonly deploymentConfigs: Record<DeploymentMode, DeploymentConfig> = {
    'local-cli': {
      mode: 'local-cli',
      services: [],
      composeFile: '', // No containers for CLI mode
      description: 'Python CLI only - no containers'
    },
    'single-container': {
      mode: 'single-container',
      services: ['cyber-autoagent'],
      composeFile: 'docker-compose.yml', // Use same file, but only start cyber-autoagent service
      description: 'Core agent container only'
    },
    'full-stack': {
      mode: 'full-stack',
      services: [
        'cyber-autoagent',
        'langfuse-web',
        'postgres',
        'clickhouse', 
        'redis',
        'minio'
      ],
      composeFile: 'docker-compose.yml', // Use same file, start all services
      description: 'Full observability stack (6 services)'
    }
  };

  private constructor() {
    super();
    // Initialization happens lazily when first accessed
  }

  static getInstance(): ContainerManager {
    if (!ContainerManager.instance) {
      ContainerManager.instance = new ContainerManager();
    }
    return ContainerManager.instance;
  }

  /**
   * Ensure container manager is initialized with current mode detection
   */
  private async ensureInitialized(): Promise<void> {
    if (!this.initialized) {
      await this.detectCurrentMode();
      this.initialized = true;
    }
  }

  /**
   * Check current container status for intelligent setup
   */
  async checkContainerStatus(): Promise<{
    dockerAvailable: boolean;
    currentMode: DeploymentMode;
    runningContainers: ContainerInfo[];
    requiredContainers: {
      [mode: string]: {
        services: string[];
        running: string[];
        missing: string[];
        needsRestart: string[];
      };
    };
  }> {
    // Check Docker availability
    let dockerAvailable = false;
    try {
      await execAsync('docker info');
      dockerAvailable = true;
    } catch {
      dockerAvailable = false;
    }

    const runningContainers = dockerAvailable ? await this.getRunningContainers() : [];
    const runningNames = runningContainers.map(c => c.name);

    // Analyze container status for each deployment mode
    const requiredContainers: any = {};
    
    for (const [mode, config] of Object.entries(this.deploymentConfigs)) {
      const services = config.services;
      const running = services.filter(service =>
        runningNames.some(name => name.includes(service.replace('cyber-', '')))
      );
      const missing = services.filter(service =>
        !runningNames.some(name => name.includes(service.replace('cyber-', '')))
      );
      
      // Check if containers exist but are stopped
      const needsRestart: string[] = [];
      if (dockerAvailable) {
        try {
          const { stdout } = await execAsync('docker ps -a --format "{{.Names}}\t{{.Status}}"');
          const allContainers = stdout.split('\n').filter(line => line.trim());
          
          for (const service of missing) {
            const existsStopped = allContainers.some(line => 
              line.includes(service) && (line.includes('Exited') || line.includes('Created'))
            );
            if (existsStopped) {
              needsRestart.push(service);
            }
          }
        } catch {
          // Ignore errors getting stopped containers
        }
      }

      requiredContainers[mode] = {
        services,
        running,
        missing: missing.filter(s => !needsRestart.includes(s)),
        needsRestart
      };
    }

    return {
      dockerAvailable,
      currentMode: this.currentMode,
      runningContainers,
      requiredContainers
    };
  }

  /**
   * Switch to a different deployment mode with intelligent state detection
   */
  async switchToMode(targetMode: DeploymentMode): Promise<void> {
    await this.ensureInitialized();
    this.logger.info(`Switching deployment mode from ${this.currentMode} to ${targetMode}`);

    // Step 1: Analyze current container state
    this.emit('progress', 'Analyzing current container environment...');
    const status = await this.checkContainerStatus();
    
    if (!status.dockerAvailable && targetMode !== 'local-cli') {
      throw new Error('Docker is not running. Please start Docker Desktop and try again.');
    }

    const targetConfig = this.deploymentConfigs[targetMode];
    const targetStatus = status.requiredContainers[targetMode];

    if (this.currentMode === targetMode) {
      // Check if all required containers are already running
      if (targetStatus.missing.length === 0 && targetStatus.needsRestart.length === 0) {
        this.emit('progress', `✓ Already in ${targetMode} mode with all containers running`);
        return;
      } else {
        this.emit('progress', `◆ ${targetMode} mode selected, but ${targetStatus.missing.length + targetStatus.needsRestart.length} containers need attention`);
      }
    }

    try {
      // Step 2: Handle local CLI mode (no containers needed)
      if (targetMode === 'local-cli') {
        // Stop any running containers from other modes
        const allRunning = status.runningContainers;
        if (allRunning.length > 0) {
          this.emit('progress', `Stopping ${allRunning.length} containers for CLI-only mode...`);
          await this.stopAllContainers();
          this.emit('progress', `✓ Stopped all containers`);
        } else {
          this.emit('progress', `✓ CLI mode selected - no containers were running`);
        }
        
        this.currentMode = targetMode;
        this.emit('progress', `✓ Successfully switched to ${targetMode} mode`);
        return;
      }

      // Step 3: Handle container modes - stop containers not needed for target mode
      const containersToStop = status.runningContainers.filter(container =>
        !targetStatus.services.some(service => container.name.includes(service.replace('cyber-', '')))
      );

      if (containersToStop.length > 0) {
        this.emit('progress', `Stopping ${containersToStop.length} containers not needed for ${targetMode} mode...`);
        for (const container of containersToStop) {
          try {
            await execAsync(`docker stop ${container.name}`);
          } catch {
            // Ignore errors for containers that may have already stopped
          }
        }
        this.emit('progress', `✓ Stopped unnecessary containers`);
      } else {
        this.emit('progress', `✓ No unnecessary containers to stop`);
      }

      // Step 4: Start/restart containers needed for target mode
      if (targetStatus.needsRestart.length > 0) {
        this.emit('progress', `Restarting ${targetStatus.needsRestart.length} existing containers...`);
        for (const service of targetStatus.needsRestart) {
          try {
            await execAsync(`docker start ${service}`);
          } catch {
            // If restart fails, it will be handled in the start phase
          }
        }
        this.emit('progress', `✓ Restarted existing containers`);
      }

      if (targetStatus.missing.length > 0) {
        this.emit('progress', `Creating ${targetStatus.missing.length} new containers for ${targetMode} mode...`);
        await this.startContainers(targetConfig);
        this.emit('progress', `✓ Created and started new containers`);
      } else if (targetStatus.needsRestart.length === 0) {
        this.emit('progress', `✓ All required containers already running`);
      }

      this.currentMode = targetMode;
      this.logger.info(`Successfully switched to ${targetMode} mode`);
      this.emit('progress', `✓ Successfully switched to ${targetMode} mode`);

    } catch (error) {
      this.logger.error(`Failed to switch to ${targetMode} mode`, error as Error);
      throw error;
    }
  }

  /**
   * Get current deployment mode
   */
  async getCurrentMode(): Promise<DeploymentMode> {
    await this.ensureInitialized();
    return this.currentMode;
  }

  /**
   * Get deployment configuration for a mode
   */
  getDeploymentConfig(mode: DeploymentMode): DeploymentConfig {
    return this.deploymentConfigs[mode];
  }

  /**
   * Get all running containers
   */
  async getRunningContainers(): Promise<ContainerInfo[]> {
    try {
      // Use simpler format without Health field to avoid template errors on older Docker versions
      const { stdout } = await execAsync('docker ps --format "{{.Names}}\t{{.Status}}"');
      
      return stdout
        .split('\n')
        .filter(line => line.trim() && line.includes('cyber-'))
        .map(line => {
          const [name, status] = line.split('\t');
          return {
            name: name.trim(),
            status: status.trim(),
            health: undefined // Health field optional - not all containers have health checks
          };
        });
    } catch (error) {
      this.logger.error('Failed to get running containers', error as Error);
      return [];
    }
  }

  /**
   * Detect current deployment mode based on running containers
   */
  private async detectCurrentMode(): Promise<void> {
    try {
      const containers = await this.getRunningContainers();
      const containerNames = containers.map(c => c.name);

      // Count running services for each mode
      const fullStackServices = this.deploymentConfigs['full-stack'].services;
      const fullStackRunning = fullStackServices.filter(service => 
        containerNames.some(name => name.includes(service.replace('cyber-', '')))
      ).length;

      const singleContainerServices = this.deploymentConfigs['single-container'].services;
      const singleContainerRunning = singleContainerServices.filter(service =>
        containerNames.some(name => name.includes(service.replace('cyber-', '')))
      ).length;

      // Determine current mode based on running services
      if (fullStackRunning >= 4) {
        this.currentMode = 'full-stack';
      } else if (singleContainerRunning > 0) {
        this.currentMode = 'single-container';
      } else {
        this.currentMode = 'local-cli';
      }

      this.logger.info(`Detected current deployment mode: ${this.currentMode} (${containers.length} containers running)`);
    } catch (error) {
      this.logger.error('Failed to detect current deployment mode', error as Error);
      this.currentMode = 'local-cli'; // Default to CLI mode on error
    }
  }

  /**
   * Stop containers for a deployment configuration
   */
  private async stopContainers(config: DeploymentConfig): Promise<void> {
    if (config.services.length === 0) return;

    this.logger.info(`Stopping containers for ${config.mode} mode`);

    return await RetryConfigs.docker.execute(async () => {
      const composePath = this.getComposePath(config.composeFile);
      
      if (fs.existsSync(composePath)) {
        // Use docker-compose to stop specific services gracefully
        const serviceList = config.services.join(' ');
        const stopCommand = `docker-compose -f "${composePath}" stop ${serviceList}`;
        this.logger.info(`Stopping services: ${stopCommand}`);
        await execAsync(stopCommand);
      } else {
        // Fallback: stop containers individually
        for (const service of config.services) {
          try {
            await execAsync(`docker stop ${service} 2>/dev/null || true`);
          } catch {
            // Ignore errors for containers that don't exist
          }
        }
      }
    }, 'stopContainers');
  }

  /**
   * Stop all running cyber-autoagent containers
   */
  private async stopAllContainers(): Promise<void> {
    this.logger.info('Stopping all cyber-autoagent containers');

    return await RetryConfigs.docker.execute(async () => {
      const containers = await this.getRunningContainers();
      
      if (containers.length === 0) {
        return;
      }

      // Stop all containers individually
      for (const container of containers) {
        try {
          await execAsync(`docker stop ${container.name}`);
        } catch {
          // Ignore errors for containers that may have already stopped
        }
      }
    }, 'stopAllContainers');
  }

  /**
   * Start containers for a deployment configuration
   */
  private async startContainers(config: DeploymentConfig): Promise<void> {
    if (config.services.length === 0) return;

    this.logger.info(`Starting containers for ${config.mode} mode`);

    return await RetryConfigs.docker.execute(async () => {
      const composePath = this.getComposePath(config.composeFile);
      
      this.logger.debug(`Looking for docker-compose file at: ${composePath}`);
      
      if (!fs.existsSync(composePath)) {
        const error = new Error(`Docker compose file not found: ${composePath}`);
        this.logger.error(`Docker compose file missing - expectedPath: ${composePath}, configMode: ${config.mode}, composeFile: ${config.composeFile}`, error);
        throw error;
      }

      this.logger.info(`Starting containers using: ${composePath}`);
      this.emit('progress', `◆ Using docker-compose file: ${composePath}`);
      
      // Build the docker-compose command with specific services
      const serviceList = config.services.join(' ');
      
      // For single container mode, use --no-deps to skip dependencies and set environment variables
      let upCommand: string;
      let buildCommand: string;
      
      if (config.mode === 'single-container') {
        // Single container mode: disable observability and evaluation, skip dependencies
        const envVars = [
          'ENABLE_OBSERVABILITY=false',
          'ENABLE_AUTO_EVALUATION=false',
          'ENABLE_LANGFUSE_PROMPTS=false'
        ].join(' ');
        
        upCommand = `${envVars} docker-compose -f "${composePath}" up -d --no-deps ${serviceList}`;
        buildCommand = `docker-compose -f "${composePath}" build ${serviceList}`;
      } else {
        // Full stack mode: start all services with observability enabled
        upCommand = `docker-compose -f "${composePath}" up -d ${serviceList}`;
        buildCommand = `docker-compose -f "${composePath}" build ${serviceList}`;
      }
      
      try {
        // Start containers with docker-compose (only specified services)
        this.logger.info(`Running: ${upCommand}`);
        const { stdout, stderr } = await execAsync(upCommand);
        
        if (stderr && !stderr.includes('Creating') && !stderr.includes('Starting') && !stderr.includes('Building')) {
          this.logger.warn(`Docker compose stderr output: ${stderr}`);
        }
        
        this.logger.debug(`Docker compose output - stdout: ${stdout}, stderr: ${stderr}`);
      } catch (composeError: any) {
        // If docker-compose up fails, try building first
        if (composeError.message.includes('No such image') || composeError.message.includes('pull access denied')) {
          this.logger.info('Image not found, attempting to build...');
          
          try {
            this.logger.info(`Running build: ${buildCommand}`);
            await execAsync(buildCommand);
            const { stdout, stderr } = await execAsync(upCommand);
            this.logger.debug(`Docker compose output after build - stdout: ${stdout}, stderr: ${stderr}`);
          } catch (buildError) {
            this.logger.error('Failed to build and start containers', buildError as Error);
            throw buildError;
          }
        } else {
          throw composeError;
        }
      }
      
      // Wait for containers to be ready
      await this.waitForContainers(config.services, 30000); // 30 second timeout
      
    }, 'startContainers');
  }

  /**
   * Wait for containers to be in running state
   */
  private async waitForContainers(services: string[], timeoutMs: number): Promise<void> {
    const startTime = Date.now();
    
    while (Date.now() - startTime < timeoutMs) {
      const containers = await this.getRunningContainers();
      const runningServices = containers
        .filter(c => c.status.includes('Up'))
        .map(c => c.name);

      const expectedRunning = services.filter(service =>
        runningServices.some(name => name.includes(service.replace('cyber-', '')))
      );

      // For single container mode, just need 1 service running
      // For full stack, need at least 3 services running
      const requiredServices = services.length === 1 ? 1 : Math.min(services.length, 3);
      
      if (expectedRunning.length >= requiredServices) {
        this.logger.info(`Containers ready: ${expectedRunning.length}/${services.length} services running`);
        return;
      }

      // Wait 2 seconds before checking again
      await new Promise(resolve => setTimeout(resolve, 2000));
    }

    throw new Error(`Timeout waiting for containers to start (${timeoutMs}ms)`);
  }

  /**
   * Get full path to docker-compose file
   */
  private getComposePath(filename: string): string {
    // Look in docker directory relative to project root
    // Current working directory is: /Users/aaronbrown/Downloads/DEV/Cyber-AutoAgent/src/modules/interfaces/react
    // We need to go up to: /Users/aaronbrown/Downloads/DEV/Cyber-AutoAgent/docker/
    const currentDir = process.cwd();
    const projectRoot = path.join(currentDir, '..', '..', '..', '..');
    return path.join(projectRoot, 'docker', filename);
  }

  /**
   * Get container count for current mode
   */
  async getContainerCount(): Promise<{ running: number; total: number }> {
    await this.ensureInitialized();
    const config = this.deploymentConfigs[this.currentMode];
    const containers = await this.getRunningContainers();
    
    if (config.services.length === 0) {
      return { running: 0, total: 0 };
    }

    const expectedContainers = config.services;
    const runningCount = expectedContainers.filter(service =>
      containers.some(c => c.name.includes(service.replace('cyber-', '')) && c.status.includes('Up'))
    ).length;

    return {
      running: runningCount,
      total: expectedContainers.length
    };
  }
}