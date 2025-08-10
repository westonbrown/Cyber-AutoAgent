/**
 * Simplified Deployment Detector
 * 
 * Detects which deployment modes are currently active/healthy
 */

import { exec } from 'child_process';
import { promisify } from 'util';
import * as fs from 'fs/promises';
import * as path from 'path';
import { Config } from '../contexts/ConfigContext.js';

const execAsync = promisify(exec);

export type DeploymentMode = 'local-cli' | 'single-container' | 'full-stack';

export interface DeploymentStatus {
  mode: DeploymentMode;
  isHealthy: boolean;
  details: {
    pythonReady?: boolean;
    venvExists?: boolean;
    packageInstalled?: boolean;
    dockerRunning?: boolean;
    containersRunning?: string[];
  };
}

export interface DetectionResult {
  needsSetup: boolean;
  availableDeployments: DeploymentStatus[];
  message?: string;
}

export class DeploymentDetector {
  private static instance: DeploymentDetector;
  private lastDetection?: { result: DetectionResult; ts: number };
  private readonly defaultTtlMs = 3000;

  static getInstance(): DeploymentDetector {
    if (!this.instance) {
      this.instance = new DeploymentDetector();
    }
    return this.instance;
  }

  clearCache(): void {
    this.lastDetection = undefined;
  }

  /**
   * Detect available deployments
   */
  async detectDeployments(config: Config): Promise<DetectionResult> {
    // Serve from short-lived cache to prevent redundant docker/python calls on re-renders
    const now = Date.now();
    if (this.lastDetection && (now - this.lastDetection.ts) < this.defaultTtlMs) {
      return this.lastDetection.result;
    }

    const deployments = await this.scanDeployments();
    
    // Only need setup for truly first-time users who haven't configured anything
    // Don't trigger setup just because a configured deployment is temporarily offline
    const hasHealthyDeployment = deployments.some(d => d.isHealthy);
    const needsSetup = !config.isConfigured || !config.deploymentMode;
    
    const result: DetectionResult = {
      needsSetup,
      availableDeployments: deployments,
      message: needsSetup ? 'First-time setup required' : 
               hasHealthyDeployment ? 'Ready to use' : 'Configured but deployment offline'
    };

    // Cache result
    this.lastDetection = { result, ts: Date.now() };
    return result;
  }

  /**
   * Quick validation for startup
   */
  async quickValidate(config: Config): Promise<boolean> {
    if (!config.deploymentMode || !config.isConfigured) {
      return false;
    }
    
    // Trust config for quick validation
    return config.isConfigured && config.hasSeenWelcome;
  }

  /**
   * Scan for available deployments
   */
  private async scanDeployments(): Promise<DeploymentStatus[]> {
    const deployments: DeploymentStatus[] = [];
    
    // Check local-cli
    const localCli = await this.checkLocalCli();
    deployments.push(localCli);
    
    // Check Docker deployments
    const dockerRunning = await this.checkDocker();
    if (dockerRunning) {
      const containers = await this.getRunningContainers();
      
      // Single container
      if (containers.includes('cyber-autoagent')) {
        deployments.push({
          mode: 'single-container',
          isHealthy: true,
          details: { 
            dockerRunning: true,
            containersRunning: ['cyber-autoagent']
          }
        });
      } else {
        deployments.push({
          mode: 'single-container',
          isHealthy: false,
          details: { dockerRunning: true }
        });
      }
      
      // Full stack - requires at least langfuse to be considered full-stack
      // Use actual container names from docker-compose.yml
      const fullStackContainers = ['cyber-langfuse', 'cyber-langfuse-postgres', 'cyber-langfuse-redis'];
      const hasFullStack = fullStackContainers.some(c => containers.includes(c));
      
      deployments.push({
        mode: 'full-stack',
        isHealthy: hasFullStack,
        details: { 
          dockerRunning: true,
          containersRunning: containers.filter(c => [...fullStackContainers, 'cyber-autoagent'].includes(c))
        }
      });
    } else {
      // Docker not running
      deployments.push(
        { mode: 'single-container', isHealthy: false, details: {} },
        { mode: 'full-stack', isHealthy: false, details: {} }
      );
    }
    
    return deployments;
  }

  /**
   * Check local CLI deployment
   */
  private async checkLocalCli(): Promise<DeploymentStatus> {
    const status: DeploymentStatus = {
      mode: 'local-cli',
      isHealthy: false,
      details: {}
    };
    
    // Check Python - try both python3 and python
    try {
      const { stdout } = await execAsync('python3 --version').catch(() => 
        execAsync('python --version')
      );
      const match = stdout.match(/Python (\d+)\.(\d+)/);
      if (match) {
        const major = parseInt(match[1]);
        const minor = parseInt(match[2]);
        status.details.pythonReady = major >= 3 && minor >= 9; // Reasonable minimum (Python 3.9+)
      }
    } catch {
      status.details.pythonReady = false;
    }
    
    // Check for .venv using robust project root detection
    const venvPath = await this.findProjectVenv();
    if (venvPath) {
      status.details.venvExists = true;
    }
    
    // Local CLI is healthy ONLY if:
    // 1. .venv exists (preferred setup), OR
    // 2. cyberautoagent is properly importable with all dependencies from project directory
    if (status.details.venvExists) {
      // If .venv exists, assume it's properly set up (most reliable)
      status.isHealthy = true;
    } else if (status.details.pythonReady) {
      // Test if cyberautoagent can be imported with dependencies from project context
      try {
        // Test from project directory with PYTHONPATH to simulate real usage
        const projectRoot = process.cwd();
        const testCommand = `cd "${projectRoot}" && PYTHONPATH="${projectRoot}/src" python3 -c "import cyberautoagent; print('CLI Ready')"`;
        await execAsync(testCommand, { timeout: 5000 });
        status.isHealthy = true;
        status.details.packageInstalled = true;
      } catch {
        // Package not installed or dependencies missing - local-cli not ready
        status.isHealthy = false;
        status.details.packageInstalled = false;
      }
    } else {
      status.isHealthy = false;
    }
    
    return status;
  }

  /**
   * Check if Docker is running
   */
  private async checkDocker(): Promise<boolean> {
    try {
      await execAsync('docker info', { timeout: 3000 });
      return true;
    } catch {
      return false;
    }
  }

  /**
   * Get list of running containers
   */
  private async getRunningContainers(): Promise<string[]> {
    try {
      const { stdout } = await execAsync('docker ps --format "{{.Names}}"', { timeout: 3000 });
      return stdout.trim().split('\n').filter(Boolean);
    } catch {
      return [];
    }
  }

  /**
   * Find project .venv directory using robust path resolution
   * Priority: 1) CYBER_PROJECT_ROOT env var, 2) Search upward for project markers, 3) Fallback to relative paths
   */
  private async findProjectVenv(): Promise<string | null> {
    // Priority 1: Check environment variable (for advanced users)
    if (process.env.CYBER_PROJECT_ROOT) {
      const envVenvPath = path.join(process.env.CYBER_PROJECT_ROOT, '.venv');
      try {
        const stats = await fs.stat(envVenvPath);
        if (stats.isDirectory()) {
          return envVenvPath;
        }
      } catch {
        // Environment variable set but path doesn't exist - continue searching
      }
    }

    // Priority 2: Search upward for project root markers (first-time user experience)
    let currentDir = process.cwd();
    const maxLevels = 10; // Reasonable limit to prevent infinite loops
    
    for (let i = 0; i < maxLevels; i++) {
      // Check for project markers that indicate we found the project root
      const projectMarkers = ['pyproject.toml', 'docker/docker-compose.yml', '.git'];
      const hasProjectMarker = await Promise.all(
        projectMarkers.map(async (marker) => {
          try {
            await fs.stat(path.join(currentDir, marker));
            return true;
          } catch {
            return false;
          }
        })
      ).then(results => results.some(Boolean));

      if (hasProjectMarker) {
        // Found project root, check for .venv here
        const venvPath = path.join(currentDir, '.venv');
        try {
          const stats = await fs.stat(venvPath);
          if (stats.isDirectory()) {
            return venvPath;
          }
        } catch {
          // Project root found but no .venv - continue searching
        }
      }

      // Move up one directory
      const parentDir = path.dirname(currentDir);
      if (parentDir === currentDir) {
        // Reached filesystem root
        break;
      }
      currentDir = parentDir;
    }

    // Priority 3: Fallback to relative paths (existing user compatibility)
    const fallbackPaths = [
      path.join(process.cwd(), '..', '..', '..', '..', '.venv'), // 4 levels up
      path.join(process.cwd(), '..', '..', '..', '.venv'), // 3 levels up
      path.join(process.cwd(), '.venv'), // Current dir
    ];
    
    for (const venvPath of fallbackPaths) {
      try {
        const stats = await fs.stat(venvPath);
        if (stats.isDirectory()) {
          return venvPath;
        }
      } catch {
        // Try next path
      }
    }

    return null;
  }
}