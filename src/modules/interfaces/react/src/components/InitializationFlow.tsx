/**
 * First-Time Initialization Flow
 * Guides users through setup: Docker containers, configuration, and first scan
 * Professional onboarding experience inspired by Gemini CLI
 */

import React, { useState, useEffect } from 'react';
import { Box, Text, useInput } from 'ink';
import Spinner from 'ink-spinner';
import { HealthMonitor, HealthStatus } from '../services/HealthMonitor.js';
import { useConfig } from '../contexts/ConfigContext.js';
import { themeManager } from '../themes/theme-manager.js';
import { exec } from 'child_process';
import { promisify } from 'util';
import * as path from 'path';
import * as fs from 'fs';
import { getEnvironmentConfig, getDockerComposePaths } from '../config/environment.js';
import { createLogger } from '../utils/logger.js';
import { RetryConfigs } from '../utils/retry.js';

const execAsync = promisify(exec);

interface InitializationFlowProps {
  onComplete: () => void;
}

type InitStep = 
  | 'checking-docker'
  | 'docker-not-running'
  | 'checking-containers'
  | 'starting-containers'
  | 'containers-ready'
  | 'checking-config'
  | 'setup-complete'
  | 'error';

interface StepStatus {
  docker: 'pending' | 'checking' | 'success' | 'error';
  containers: 'pending' | 'checking' | 'starting' | 'success' | 'error';
  config: 'pending' | 'checking' | 'needed' | 'success';
}

export const InitializationFlow: React.FC<InitializationFlowProps> = ({ onComplete }) => {
  const { config } = useConfig();
  const theme = themeManager.getCurrentTheme();
  const envConfig = getEnvironmentConfig();
  const logger = createLogger('InitializationFlow');
  const [currentStep, setCurrentStep] = useState<InitStep>('checking-docker');
  const [stepStatus, setStepStatus] = useState<StepStatus>({
    docker: 'checking',
    containers: 'pending',
    config: 'pending'
  });
  const [healthStatus, setHealthStatus] = useState<HealthStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showContinue, setShowContinue] = useState(false);

  useEffect(() => {
    checkInitialization();
  }, []);

  // Handle keyboard input
  useInput((input, key) => {
    if (showContinue && (key.return || input === ' ')) {
      onComplete();
    }
  });

  const checkInitialization = async () => {
    const monitor = HealthMonitor.getInstance();
    
    // Step 1: Check Docker
    setStepStatus(prev => ({ ...prev, docker: 'checking' }));
    const dockerStatus = await checkDockerStatus();
    
    if (!dockerStatus) {
      setStepStatus(prev => ({ ...prev, docker: 'error' }));
      setCurrentStep('docker-not-running');
      return;
    }
    
    setStepStatus(prev => ({ ...prev, docker: 'success' }));
    
    // Step 2: Check containers
    setCurrentStep('checking-containers');
    setStepStatus(prev => ({ ...prev, containers: 'checking' }));
    
    const health = await monitor.checkHealth();
    setHealthStatus(health);
    
    const criticalServices = ['cyber-langfuse'];
    const criticalRunning = health.services
      .filter(s => criticalServices.includes(s.name))
      .every(s => s.status === 'running');
    
    if (!criticalRunning) {
      // Check if containers are actually running but with different names
      const runningContainers = health.services.filter(s => s.status === 'running').length;
      
      // If we have at least some containers running, don't try to start them
      if (runningContainers >= 3) {
        // Most containers are running, just proceed
        console.log('Containers detected with different names, proceeding...');
      } else {
        // Try to start containers
        setCurrentStep('starting-containers');
        setStepStatus(prev => ({ ...prev, containers: 'starting' }));
        
        const started = await startContainers();
        if (!started) {
          // Check again if they're actually running
          const recheckHealth = await monitor.checkHealth();
          const runningAfterError = recheckHealth.services.filter(s => s.status === 'running').length;
          
          if (runningAfterError >= 4) {
            // They're actually running, just with different names
            console.log('Containers are already running');
            setHealthStatus(recheckHealth);
          } else {
            setStepStatus(prev => ({ ...prev, containers: 'error' }));
            setCurrentStep('error');
            setError('Failed to start containers. Please run: docker-compose up -d');
            return;
          }
        } else {
          // Re-check health after starting
          await new Promise(resolve => setTimeout(resolve, 5000)); // Wait for containers to start
          const newHealth = await monitor.checkHealth();
          setHealthStatus(newHealth);
        }
      }
    }
    
    setStepStatus(prev => ({ ...prev, containers: 'success' }));
    setCurrentStep('containers-ready');
    
    // Step 3: Check configuration
    setCurrentStep('checking-config');
    setStepStatus(prev => ({ ...prev, config: 'checking' }));
    
    if (!config.isConfigured) {
      setStepStatus(prev => ({ ...prev, config: 'needed' }));
      setShowContinue(true);
    } else {
      setStepStatus(prev => ({ ...prev, config: 'success' }));
      setCurrentStep('setup-complete');
      
      // Auto-complete after a short delay
      setTimeout(() => {
        onComplete();
      }, 2000);
    }
  };

  const checkDockerStatus = async (): Promise<boolean> => {
    try {
      await execAsync('docker info');
      return true;
    } catch {
      return false;
    }
  };

  const startContainers = async (): Promise<boolean> => {
    return await RetryConfigs.docker.execute(async () => {
      // Find docker-compose.yml using environment-aware path detection
      const possiblePaths = getDockerComposePaths();
      
      let composePath = '';
      for (const possiblePath of possiblePaths) {
        if (fs.existsSync(possiblePath)) {
          composePath = possiblePath;
          logger.debug('Found docker-compose file', { path: composePath });
          break;
        }
      }
      
      if (!composePath) {
        const error = new Error('Could not find docker-compose.yml in any expected location');
        logger.error('Docker compose file not found', undefined, { 
          searchedPaths: possiblePaths 
        });
        throw error;
      }
      
      // First check if containers exist but are stopped
      const { stdout: psOutput } = await execAsync('docker ps -a --format "{{.Names}}"');
      const existingContainers = psOutput.split('\n').filter(name => name.includes('cyber-'));
      
      if (existingContainers.length > 0) {
        // Try to start existing containers
        try {
          await execAsync(`docker-compose -f ${composePath} start`);
          return true;
        } catch {
          // If start fails, try up without -d to avoid conflicts
          try {
            await execAsync(`docker-compose -f ${composePath} up --no-recreate -d`);
            return true;
          } catch (upError) {
            logger.error('Failed to start existing containers', upError as Error);
            throw upError;
          }
        }
      } else {
        // No existing containers, create new ones
        logger.info('Creating new containers', { composePath });
        await execAsync(`docker-compose -f ${composePath} up -d`);
        return true;
      }
    }, 'startContainers').catch((error) => {
      logger.error('Failed to start containers after retries', error);
      return false;
    });
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'checking':
      case 'starting':
        return <Spinner type="dots" />;
      case 'success':
        return <Text color={theme.success}>✓</Text>;
      case 'error':
        return <Text color={theme.danger}>✗</Text>;
      case 'pending':
        return <Text color={theme.muted}>○</Text>;
      default:
        return <Text color={theme.muted}>-</Text>;
    }
  };

  return (
    <Box flexDirection="column" paddingX={2} paddingY={1}>
      <Box marginBottom={2}>
        <Text bold color={theme.primary}>
          Cyber-AutoAgent Initialization
        </Text>
      </Box>

      {/* Docker Status */}
      <Box marginBottom={1}>
        {getStatusIcon(stepStatus.docker)}
        <Text color={stepStatus.docker === 'error' ? theme.danger : theme.foreground}>
          {' '}Docker Desktop
        </Text>
      </Box>

      {/* Container Status */}
      {stepStatus.docker === 'success' && (
        <Box marginBottom={1}>
          {getStatusIcon(stepStatus.containers)}
          <Text color={stepStatus.containers === 'error' ? theme.danger : theme.foreground}>
            {' '}Services: 
          </Text>
          {healthStatus && (
            <Text color={theme.muted}>
              {' '}({healthStatus.services.filter(s => s.status === 'running').length}/{healthStatus.services.length} running)
            </Text>
          )}
        </Box>
      )}

      {/* Configuration Status */}
      {stepStatus.containers === 'success' && (
        <Box marginBottom={1}>
          {getStatusIcon(stepStatus.config)}
          <Text color={theme.foreground}>
            {' '}Configuration
          </Text>
          {stepStatus.config === 'needed' && (
            <Text color={theme.warning}> (Setup required)</Text>
          )}
        </Box>
      )}

      {/* Messages based on current step */}
      <Box marginTop={2}>
        {currentStep === 'docker-not-running' && (
          <Box flexDirection="column">
            <Text color={theme.danger}>Docker Desktop is not running.</Text>
            <Text color={theme.muted}>Please start Docker Desktop and restart the application.</Text>
          </Box>
        )}

        {currentStep === 'starting-containers' && (
          <Box>
            <Spinner type="dots" />
            <Text color={theme.info}> Starting containers...</Text>
          </Box>
        )}

        {currentStep === 'containers-ready' && stepStatus.config === 'needed' && (
          <Box flexDirection="column">
            <Text color={theme.success}>✓ All services are running!</Text>
            <Box marginTop={1}>
              <Text color={theme.info}>First-time setup detected. Press </Text>
              <Text color={theme.primary} bold>Enter</Text>
              <Text color={theme.info}> to configure your AI provider.</Text>
            </Box>
          </Box>
        )}

        {currentStep === 'setup-complete' && (
          <Box flexDirection="column">
            <Text color={theme.success}>✓ Environment ready!</Text>
            <Text color={theme.muted}>Loading application...</Text>
          </Box>
        )}

        {error && (
          <Box flexDirection="column">
            <Text color={theme.danger}>Error: {error}</Text>
          </Box>
        )}
      </Box>

      {/* Service Details (if containers are being checked/started) */}
      {healthStatus && (currentStep === 'checking-containers' || currentStep === 'starting-containers') && (
        <Box flexDirection="column" marginTop={2}>
          <Text color={theme.muted}>Service Status:</Text>
          {healthStatus.services.slice(0, 4).map(service => (
            <Box key={service.name} paddingLeft={1}>
              <Text color={service.status === 'running' ? theme.success : theme.muted}>
                {service.status === 'running' ? '✓' : '○'} {service.displayName}
              </Text>
            </Box>
          ))}
        </Box>
      )}
    </Box>
  );
};