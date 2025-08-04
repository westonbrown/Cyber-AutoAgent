/**
 * Environment Configuration Management
 * Handles different deployment environments (development, staging, production)
 * with appropriate fallbacks and validation
 */

export type Environment = 'development' | 'staging' | 'production';

export interface EnvironmentConfig {
  env: Environment;
  isDevelopment: boolean;
  isProduction: boolean;
  isStaging: boolean;
  dockerCompose: {
    file: string;
    profile?: string;
  };
  logging: {
    level: 'debug' | 'info' | 'warn' | 'error';
    structured: boolean;
  };
  docker: {
    networkName: string;
    autoCleanup: boolean;
    healthCheckInterval: number;
  };
  api: {
    timeout: number;
    retries: number;
  };
}

/**
 * Detect current environment from NODE_ENV or default to development
 */
export function getEnvironment(): Environment {
  const nodeEnv = process.env.NODE_ENV?.toLowerCase();
  
  switch (nodeEnv) {
    case 'production':
    case 'prod':
      return 'production';
    case 'staging':
    case 'stage':
      return 'staging';
    case 'development':
    case 'dev':
    default:
      return 'development';
  }
}

/**
 * Get environment-specific configuration
 */
export function getEnvironmentConfig(): EnvironmentConfig {
  const env = getEnvironment();
  
  const baseConfig: EnvironmentConfig = {
    env,
    isDevelopment: env === 'development',
    isProduction: env === 'production',
    isStaging: env === 'staging',
    dockerCompose: {
      file: env === 'production' ? 'docker-compose.prod.yml' : 'docker-compose.yml',
      profile: env === 'development' ? 'dev' : undefined
    },
    logging: {
      level: env === 'production' ? 'info' : 'debug',
      structured: env === 'production'
    },
    docker: {
      networkName: env === 'production' ? 'cyber-autoagent-prod' : 'cyber-autoagent_default',
      autoCleanup: env !== 'development',
      healthCheckInterval: env === 'production' ? 30000 : 10000
    },
    api: {
      timeout: env === 'production' ? 60000 : 30000,
      retries: env === 'production' ? 3 : 1
    }
  };

  return baseConfig;
}

/**
 * Validate environment configuration
 */
export function validateEnvironment(): { valid: boolean; errors: string[] } {
  const errors: string[] = [];
  const env = getEnvironment();
  
  // Check for required environment variables in production
  if (env === 'production') {
    const required = ['NODE_ENV'];
    for (const envVar of required) {
      if (!process.env[envVar]) {
        errors.push(`Missing required environment variable: ${envVar}`);
      }
    }
  }
  
  // Validate Docker availability
  if (typeof process !== 'undefined' && process.platform === 'win32') {
    // Additional Windows-specific validation could go here
  }
  
  return {
    valid: errors.length === 0,
    errors
  };
}

/**
 * Get environment-specific paths for Docker Compose files
 */
export function getDockerComposePaths(): string[] {
  const config = getEnvironmentConfig();
  const projectRoot = process.cwd();
  
  return [
    require('path').join(projectRoot, 'docker', config.dockerCompose.file),
    require('path').join(projectRoot, config.dockerCompose.file),
    require('path').join(projectRoot, '..', 'docker', config.dockerCompose.file),
    // Fallback to default
    require('path').join(projectRoot, 'docker', 'docker-compose.yml'),
    require('path').join(projectRoot, 'docker-compose.yml')
  ];
}