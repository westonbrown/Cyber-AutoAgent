/**
 * Health Monitor Service
 * 
 * Monitors the status of all Docker containers and system health.
 * Provides container status checking and recommendations.
 */

import { exec } from 'child_process';
import { promisify } from 'util';
import { getEnvironmentConfig } from '../config/environment.js';
import { createLogger } from '../utils/logger.js';
import { RetryConfigs, CircuitBreakers } from '../utils/retry.js';
import { ContainerManager } from './ContainerManager.js';

const execAsync = promisify(exec);

export interface ServiceStatus {
  name: string;
  displayName: string;
  status: 'running' | 'stopped' | 'error' | 'checking';
  health?: 'healthy' | 'unhealthy' | 'starting';
  uptime?: string;
  port?: number;
  url?: string;
  message?: string;
}

export interface HealthStatus {
  overall: 'healthy' | 'degraded' | 'unhealthy';
  services: ServiceStatus[];
  lastCheck: Date;
  dockerRunning: boolean;
}

export class HealthMonitor {
  private static instance: HealthMonitor;
  private checkInterval: NodeJS.Timeout | null = null;
  private lastStatus: HealthStatus | null = null;
  private listeners: ((status: HealthStatus) => void)[] = [];
  private readonly envConfig = getEnvironmentConfig();
  private readonly logger = createLogger('HealthMonitor');

  // Service definitions map for all possible services
  // Maps docker-compose service names to container names and display info
  private readonly serviceDefinitions = {
    // Direct container names
    'cyber-autoagent': {
      name: 'cyber-autoagent',
      displayName: 'Agent',
      critical: true
    },
    'cyber-langfuse': {
      name: 'cyber-langfuse',
      displayName: 'Langfuse',
      port: 3000,
      url: 'http://localhost:3000',
      critical: true
    },
    'cyber-langfuse-worker': {
      name: 'cyber-langfuse-worker',
      displayName: 'Langfuse Worker',
      critical: false
    },
    'cyber-langfuse-postgres': {
      name: 'cyber-langfuse-postgres',
      displayName: 'PostgreSQL',
      critical: false
    },
    'cyber-langfuse-clickhouse': {
      name: 'cyber-langfuse-clickhouse',
      displayName: 'ClickHouse',
      critical: false
    },
    'cyber-langfuse-redis': {
      name: 'cyber-langfuse-redis',
      displayName: 'Redis',
      critical: false
    },
    'cyber-langfuse-minio': {
      name: 'cyber-langfuse-minio',
      displayName: 'MinIO Storage',
      port: 9090,
      critical: false
    },
    // Docker-compose service names mapping to container names
    'langfuse-web': {
      name: 'cyber-langfuse',
      displayName: 'Langfuse',
      port: 3000,
      url: 'http://localhost:3000',
      critical: true
    },
    'postgres': {
      name: 'cyber-langfuse-postgres',
      displayName: 'PostgreSQL',
      critical: false
    },
    'clickhouse': {
      name: 'cyber-langfuse-clickhouse',
      displayName: 'ClickHouse',
      critical: false
    },
    'redis': {
      name: 'cyber-langfuse-redis',
      displayName: 'Redis',
      critical: false
    },
    'minio': {
      name: 'cyber-langfuse-minio',
      displayName: 'MinIO Storage',
      port: 9090,
      critical: false
    }
  };

  // Get current services based on deployment mode
  private async getCurrentServices() {
    const containerManager = ContainerManager.getInstance();
    const currentMode = await containerManager.getCurrentMode();
    const config = containerManager.getDeploymentConfig(currentMode);
    
    return config.services.map(serviceName => 
      this.serviceDefinitions[serviceName as keyof typeof this.serviceDefinitions]
    ).filter(Boolean);
  }

  private constructor() {}

  static getInstance(): HealthMonitor {
    if (!HealthMonitor.instance) {
      HealthMonitor.instance = new HealthMonitor();
    }
    return HealthMonitor.instance;
  }

  // Start monitoring with environment-aware interval
  startMonitoring(intervalMs?: number): void {
    if (this.checkInterval) {
      clearInterval(this.checkInterval);
    }

    const interval = intervalMs || this.envConfig.docker.healthCheckInterval;
    this.logger.info('Starting health monitoring', { intervalMs: interval });

    // Initial check
    this.checkHealth();

    // Set up periodic checks
    this.checkInterval = setInterval(() => {
      this.checkHealth();
    }, interval);
  }

  // Stop monitoring
  stopMonitoring(): void {
    if (this.checkInterval) {
      clearInterval(this.checkInterval);
      this.checkInterval = null;
    }
  }

  // Subscribe to health status updates
  subscribe(callback: (status: HealthStatus) => void): () => void {
    this.listeners.push(callback);
    
    // Send current status immediately if available
    if (this.lastStatus) {
      callback(this.lastStatus);
    }

    // Return unsubscribe function
    return () => {
      this.listeners = this.listeners.filter(l => l !== callback);
    };
  }

  // Get current status
  getCurrentStatus(): HealthStatus | null {
    return this.lastStatus;
  }

  // Perform health check with circuit breaker protection
  async checkHealth(): Promise<HealthStatus> {
    return await CircuitBreakers.healthMonitor.execute(async () => {
      const status: HealthStatus = {
        overall: 'healthy',
        services: [],
        lastCheck: new Date(),
        dockerRunning: false
      };

      try {
        // First check if Docker is running with retry
        const dockerRunning = await RetryConfigs.healthCheck.execute(
          () => this.checkDockerDaemon(),
          'checkDockerDaemon'
        );
      status.dockerRunning = dockerRunning;

      if (!dockerRunning) {
        status.overall = 'unhealthy';
        const currentServices = await this.getCurrentServices();
        status.services = currentServices.map(svc => ({
          name: svc.name,
          displayName: svc.displayName,
          status: 'error',
          message: 'Docker not running'
        }));
      } else {
        // Check each service based on current deployment mode
        const currentServices = await this.getCurrentServices();
        const serviceStatuses = await Promise.all(
          currentServices.map(svc => this.checkService(svc))
        );
        
        status.services = serviceStatuses;

        // Determine overall health
        const criticalServices = serviceStatuses.filter((svc, idx) => 
          currentServices[idx].critical
        );
        const hasUnhealthyCritical = criticalServices.some(
          svc => svc.status !== 'running' || svc.health === 'unhealthy'
        );
        const hasUnhealthyNonCritical = serviceStatuses.some(
          svc => svc.status !== 'running' || svc.health === 'unhealthy'
        );

        if (hasUnhealthyCritical) {
          status.overall = 'unhealthy';
        } else if (hasUnhealthyNonCritical) {
          status.overall = 'degraded';
        }
      }
      } catch (error) {
        this.logger.error('Health check failed', error as Error);
        status.overall = 'unhealthy';
        const currentServices = await this.getCurrentServices();
        status.services = currentServices.map(svc => ({
          name: svc.name,
          displayName: svc.displayName,
          status: 'error',
          message: error instanceof Error ? error.message : 'Unknown error'
        }));
      }

      this.lastStatus = status;
      this.notifyListeners(status);
      return status;
    }, 'healthCheck');
  }

  // Check if Docker daemon is running
  private async checkDockerDaemon(): Promise<boolean> {
    try {
      await execAsync('docker info');
      return true;
    } catch {
      return false;
    }
  }

  // Check individual service
  private async checkService(service: {
    name: string;
    displayName: string;
    port?: number;
    url?: string;
  }): Promise<ServiceStatus> {
    const status: ServiceStatus = {
      name: service.name,
      displayName: service.displayName,
      status: 'checking',
      port: service.port,
      url: service.url
    };

    try {
      // First try to find container by exact name
      let containerInfo: string | null = null;
      
      try {
        // First check if container with exact name is running
        const { stdout: checkRunning } = await execAsync(
          `docker ps --filter "name=^${service.name}$" --format "{{.Names}}" | head -1`
        );
        
        if (checkRunning.trim() === service.name) {
          // Container with exact name is running, inspect it
          const { stdout } = await execAsync(
            `docker inspect ${service.name} --format='{{.State.Status}}|{{if .State.Health}}{{.State.Health.Status}}{{else}}no-health{{end}}|{{.State.StartedAt}}'`
          );
          containerInfo = stdout.trim();
        } else {
          throw new Error('Container not running with exact name');
        }
      } catch {
        // If exact name fails, try to find by image name
        if (service.name === 'cyber-autoagent') {
          try {
            const { stdout: containerId } = await execAsync(
              `docker ps --filter "ancestor=cyber-autoagent:sudo" --format "{{.ID}}" | head -1`
            );
            if (containerId.trim()) {
              const { stdout } = await execAsync(
                `docker inspect ${containerId.trim()} --format='{{.State.Status}}|{{if .State.Health}}{{.State.Health.Status}}{{else}}no-health{{end}}|{{.State.StartedAt}}'`
              );
              containerInfo = stdout.trim();
            }
          } catch {
            // Ignore error, will be handled below
          }
        }
      }
      
      if (containerInfo) {
        const [containerStatus, healthStatus, startedAt] = containerInfo.split('|');

        // Set status
        if (containerStatus === 'running') {
          status.status = 'running';
          // Handle containers without health checks
          if (healthStatus === 'no-health') {
            status.health = undefined;
          } else {
            status.health = healthStatus as any || 'healthy';
          }
          
          // Calculate uptime
          if (startedAt && startedAt !== '<no value>') {
            const started = new Date(startedAt);
            const uptime = Date.now() - started.getTime();
            status.uptime = this.formatUptime(uptime);
          }
        } else {
          status.status = 'stopped';
        }
      } else {
        status.status = 'stopped';
        status.message = 'Container not found';
      }
    } catch (error) {
      // Container doesn't exist or other error
      status.status = 'stopped';
      status.message = 'Container not found';
    }

    return status;
  }

  // Format uptime duration
  private formatUptime(ms: number): string {
    const seconds = Math.floor(ms / 1000);
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);
    const days = Math.floor(hours / 24);

    if (days > 0) {
      return `${days}d ${hours % 24}h`;
    } else if (hours > 0) {
      return `${hours}h ${minutes % 60}m`;
    } else if (minutes > 0) {
      return `${minutes}m ${seconds % 60}s`;
    } else {
      return `${seconds}s`;
    }
  }

  // Notify all listeners
  private notifyListeners(status: HealthStatus): void {
    this.listeners.forEach(listener => listener(status));
  }

  // Manual health check (for /health command)
  async getDetailedHealth(): Promise<{
    status: HealthStatus;
    recommendations: string[];
  }> {
    const status = await this.checkHealth();
    const recommendations: string[] = [];

    // Generate recommendations based on status
    if (!status.dockerRunning) {
      recommendations.push('Start Docker Desktop to enable Cyber-AutoAgent');
    }

    status.services.forEach(svc => {
      if (svc.status === 'stopped' && svc.name === 'cyber-autoagent') {
        recommendations.push('Run "docker-compose up -d" to start the agent');
      } else if (svc.status === 'stopped' && svc.displayName === 'Langfuse') {
        recommendations.push('Langfuse is stopped. Observability features will be unavailable');
      } else if (svc.health === 'unhealthy') {
        recommendations.push(`${svc.displayName} is unhealthy. Check logs with: docker logs ${svc.name}`);
      }
    });

    return { status, recommendations };
  }
}