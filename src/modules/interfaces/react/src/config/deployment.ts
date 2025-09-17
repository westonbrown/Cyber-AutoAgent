/**
 * Deployment Mode Detection for React UI
 * 
 * Detects the deployment environment and provides smart defaults
 * for observability and evaluation settings based on available infrastructure.
 */

import * as net from 'node:net';

export type DeploymentMode = 'cli' | 'container' | 'compose';

export interface DeploymentInfo {
  mode: DeploymentMode;
  observabilityDefault: boolean;
  evaluationDefault: boolean;
  langfuseHost: string;
  description: string;
}

/**
 * Detect if running inside Docker container
 */
function isDocker(): boolean {
  // Check for Docker environment markers
  return !!(
    process.env.CONTAINER === 'docker' ||
    process.env.IS_DOCKER ||
    process.platform === 'linux' // React runs in Node, this is a heuristic for containers
  );
}

/**
 * Check if Langfuse service is available
 */
async function isLangfuseAvailable(): Promise<boolean> {
  try {
    const isInDocker = isDocker();
    
    if (isInDocker) {
      // In Docker, try to connect to langfuse-web service
      // Use a simple socket check since fetch might not be available
      const host = 'langfuse-web';
      const port = 3000;
      
      return new Promise((resolve) => {
        const socket = new net.Socket();
        
        socket.setTimeout(2000);
        
        socket.on('connect', () => {
          socket.destroy();
          resolve(true);
        });
        
        socket.on('error', () => {
          resolve(false);
        });
        
        socket.on('timeout', () => {
          socket.destroy();
          resolve(false);
        });
        
        socket.connect(port, host);
      });
    } else {
      // Outside Docker, check localhost
      try {
        const response = await fetch('http://localhost:3000/api/public/health', { 
          method: 'GET',
          signal: AbortSignal.timeout(2000)
        });
        return response.ok;
      } catch {
        return false;
      }
    }
  } catch {
    return false;
  }
}

/**
 * Detect deployment mode and return appropriate configuration defaults
 */
export async function detectDeploymentMode(): Promise<DeploymentInfo> {
  const isInDocker = isDocker();
  const langfuseAvailable = await isLangfuseAvailable();
  
  if (isInDocker) {
    if (langfuseAvailable) {
      // Full Docker Compose stack
      return {
        mode: 'compose',
        observabilityDefault: true,
        evaluationDefault: true,
        langfuseHost: 'http://langfuse-web:3000',
        description: 'Full-stack deployment with observability infrastructure'
      };
    } else {
      // Single container mode
      return {
        mode: 'container',
        observabilityDefault: false,
        evaluationDefault: false,
        langfuseHost: 'http://localhost:3000',
        description: 'Single container deployment (no observability infrastructure)'
      };
    }
  } else {
    if (langfuseAvailable) {
      // Local development with Langfuse running
      return {
        mode: 'compose',
        observabilityDefault: true,
        evaluationDefault: true,
        langfuseHost: 'http://localhost:3000',
        description: 'Local development with observability services running'
      };
    } else {
      // Pure CLI mode
      return {
        mode: 'cli',
        observabilityDefault: false,
        evaluationDefault: false,
        langfuseHost: 'http://localhost:3000',
        description: 'CLI mode (no observability infrastructure)'
      };
    }
  }
}

/**
 * Get deployment-aware defaults synchronously (for initial config)
 * This provides conservative defaults that can be updated asynchronously
 */
export function getDeploymentDefaults(): Partial<DeploymentInfo> {
  const isInDocker = isDocker();
  
  // Conservative defaults - assume no observability unless proven otherwise
  return {
    observabilityDefault: false,
    evaluationDefault: false,
    langfuseHost: isInDocker ? 'http://langfuse-web:3000' : 'http://localhost:3000',
    description: isInDocker ? 'Container deployment' : 'CLI deployment'
  };
}