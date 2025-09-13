/**
 * First-Time Initialization Flow
 * 
 * Guides users through setup: Docker containers, configuration, and first scan.
 * Provides step-by-step onboarding for new users.
 */

import React, { useState, useEffect } from 'react';
import { Box, Text, useInput } from 'ink';
import Spinner from 'ink-spinner';
import Divider from 'ink-divider';
import { HealthMonitor, HealthStatus } from '../services/HealthMonitor.js';
import { useConfig } from '../contexts/ConfigContext.js';
import { themeManager } from '../themes/theme-manager.js';
import { Header } from './Header.js';
import { ContainerManager } from '../services/ContainerManager.js';
import { exec } from 'child_process';
import { promisify } from 'util';
import * as path from 'path';
import * as fs from 'fs';
import { getEnvironmentConfig, getDockerComposePaths } from '../config/environment.js';
import { createLogger } from '../utils/logger.js';
import { RetryConfigs } from '../utils/retry.js';
import SetupProgressScreen from './SetupProgressScreen.js';
import { LogEntry } from './LogContainer.js';

const execAsync = promisify(exec);

interface InitializationFlowProps {
  onComplete: (completionMessage?: string) => void;
  terminalWidth?: number;
}

type InitStep = 
  | 'welcome'
  | 'deployment-selection'
  | 'switching-containers'
  | 'container-setup-progress'
  | 'setup-progress-screen'
  | 'checking-docker'
  | 'docker-not-running'
  | 'checking-containers'
  | 'starting-containers'
  | 'containers-ready'
  | 'checking-config'
  | 'setup-complete'
  | 'error';

type DeploymentMode = 'local-cli' | 'single-container' | 'full-stack';

interface StepStatus {
  docker: 'pending' | 'checking' | 'success' | 'error';
  containers: 'pending' | 'checking' | 'starting' | 'success' | 'error';
  config: 'pending' | 'checking' | 'needed' | 'success';
}

export const InitializationFlow: React.FC<InitializationFlowProps> = ({ onComplete, terminalWidth = 80 }) => {
  const { config, updateConfig, saveConfig } = useConfig();
  const theme = themeManager.getCurrentTheme();
  const envConfig = getEnvironmentConfig();
  const logger = createLogger('InitializationFlow');
  const [currentStep, setCurrentStep] = useState<InitStep>('welcome');

  // Screen clearing is handled by App.tsx refreshStatic() when /setup is triggered
  const [deploymentMode, setDeploymentMode] = useState<DeploymentMode>('full-stack');
  const [selectedModeIndex, setSelectedModeIndex] = useState(0);
  const [stepStatus, setStepStatus] = useState<StepStatus>({
    docker: 'pending',
    containers: 'pending',
    config: 'pending'
  });
  const [healthStatus, setHealthStatus] = useState<HealthStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showContinue, setShowContinue] = useState(false);
  const [setupLogs, setSetupLogs] = useState<LogEntry[]>([]);
  const [isSetupComplete, setIsSetupComplete] = useState(false);
  const [setupHasFailed, setSetupHasFailed] = useState(false);
  const [setupErrorMessage, setSetupErrorMessage] = useState<string>('');
  const [isSwitchingMode, setIsSwitchingMode] = useState(false);

  const addSetupLog = (message: string, level: 'info' | 'success' | 'warning' | 'error' = 'info') => {
    // Prevent duplicate consecutive messages
    setSetupLogs(prev => {
      const lastLog = prev[prev.length - 1];
      if (lastLog && lastLog.message === message) {
        // Skip duplicate message
        return prev;
      }
      
      const logEntry: LogEntry = {
        id: `log-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
        timestamp: new Date().toLocaleTimeString(),
        level,
        message
      };
      return [...prev, logEntry];
    });
  };

  const deploymentModes = [
    {
      id: 'local-cli' as DeploymentMode,
      name: 'Local CLI',
      description: 'Minimal footprint - Python environment with direct API calls',
      icon: `
  ┌─────────┐
  │ >_ CLI  │
  │  Python │
  └─────────┘`,
      requirements: ['~100MB disk', '1GB RAM', 'Python 3.11+', 'Direct LLM API access']
    },
    {
      id: 'single-container' as DeploymentMode,
      name: 'Single Container',
      description: 'Isolated execution - Docker container with core agent only',
      icon: `
  ┌───────────┐
  │ ┌───────┐ │
  │ │ AGENT │ │
  │ └───────┘ │
  └───────────┘`,
      requirements: ['Disk: ~2GB', 'Memory: 4GB', 'CPU: 2 vCPU', 'Containers: 1', 'Dependencies: Docker Desktop']
    },
    {
      id: 'full-stack' as DeploymentMode,
      name: 'Full Stack',
      description: 'Complete platform - All services with observability and evaluation',
      icon: `
  ┌─────────────┐
  │ ┌─┐ ┌─┐ ┌─┐ │
  │ │ │ │ │ │ │ │
  │ └─┘ └─┘ └─┘ │
  │ ┌─┐ ┌─┐ ┌─┐ │
  │ │ │ │ │ │ │ │
  │ └─┘ └─┘ └─┘ │
  └─────────────┘`,
      requirements: ['Disk: ~5GB', 'Memory: 8GB', 'CPU: 4 vCPU', 'Containers: 7', 'Dependencies: Docker Compose']
    }
  ];

  useEffect(() => {
    // Only auto-proceed if we're past the selection screens and not in setup progress
    // Add more guards to prevent infinite loops
    if (currentStep !== 'welcome' && 
        currentStep !== 'deployment-selection' && 
        currentStep !== 'setup-progress-screen' &&
        currentStep !== 'switching-containers' &&
        currentStep !== 'starting-containers' &&
        currentStep !== 'checking-containers' &&
        currentStep !== 'checking-config') {
      checkInitialization();
    }
  }, [currentStep]); // checkInitialization is a stable function

  // Handle keyboard input
  useInput((input, key) => {
    if (currentStep === 'welcome') {
      if (key.return || input === ' ') {
        setCurrentStep('deployment-selection');
      } else if (key.escape) {
        // Screen clearing handled by app component
        onComplete();
      }
    } else if (currentStep === 'deployment-selection') {
      if (key.upArrow) {
        setSelectedModeIndex(prev => prev > 0 ? prev - 1 : deploymentModes.length - 1);
      } else if (key.downArrow) {
        setSelectedModeIndex(prev => prev < deploymentModes.length - 1 ? prev + 1 : 0);
      } else if (key.return) {
        // Prevent multiple invocations
        if (isSwitchingMode) return;
        
        const selected = deploymentModes[selectedModeIndex];
        setDeploymentMode(selected.id);
        
        // Save deployment mode to config
        updateConfig({ deploymentMode: selected.id });
        
        // Save config immediately to persist the deployment mode
        saveConfig().catch(err => {
          logger.error('Failed to save deployment mode', err);
        });
        
        // Clear logs and set initial state
        setSetupLogs([]);
        setSetupHasFailed(false);
        setSetupErrorMessage('');
        setIsSetupComplete(false);
        
        // Add initial log
        addSetupLog(`▶ Initializing ${selected.name} mode...`);
        
        // Transition directly to setup progress screen
        setCurrentStep('setup-progress-screen');
        
        // Mark that we're switching mode to prevent duplicates
        setIsSwitchingMode(true);
        
        // Switch containers based on selected mode
        setTimeout(() => {
          switchDeploymentMode(selected.id);
        }, 100);
      } else if (key.escape) {
        // Screen clearing handled by app component
        onComplete();
      }
    } else if (showContinue && (key.return || input === ' ')) {
      // Add a notification to operation history before completing
      if (currentStep === 'setup-complete') {
        const modeDisplay = deploymentMode === 'local-cli' ? 'CLI' : 
                           deploymentMode === 'single-container' ? 'Agent Container' : 
                           'Enterprise Stack';
        
        // This will be handled by the parent component (App.tsx) to add to operation history
        // We'll pass this info through onComplete
        onComplete(`Deployment mode set to ${modeDisplay}. Environment ready.`);
      } else {
        onComplete();
      }
    }
  });

  const checkInitialization = async () => {
    const monitor = HealthMonitor.getInstance();
    
    // Skip Docker checks for local CLI mode
    if (deploymentMode === 'local-cli') {
      setStepStatus(prev => ({ ...prev, docker: 'success', containers: 'success' }));
      setCurrentStep('checking-config');
      
      // Check configuration
      setStepStatus(prev => ({ ...prev, config: 'checking' }));
      
      if (!config.isConfigured) {
        setStepStatus(prev => ({ ...prev, config: 'needed' }));
        setShowContinue(true);
      } else {
        setStepStatus(prev => ({ ...prev, config: 'success' }));
        setCurrentStep('setup-complete');
        
        // Complete immediately to avoid screen flicker
        onComplete();
      }
      return;
    }
    
    // Step 1: Check Docker (for container modes)
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
        // console.log('Containers detected with different names, proceeding...');
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
            // console.log('Containers are already running');
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
      
      // If user explicitly ran /setup, show them the continue option instead of auto-completing
      // This allows them to reconfigure deployment mode even if already configured
      if (process.env.CYBER_SHOW_SETUP === 'true') {
        setShowContinue(true);
      } else {
        setCurrentStep('setup-complete');
        
        // Complete immediately to avoid screen flicker
        onComplete();
      }
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

  const switchDeploymentMode = async (targetMode: DeploymentMode) => {
    // Prevent multiple simultaneous invocations
    if (!isSwitchingMode && currentStep !== 'setup-progress-screen') {
      setCurrentStep('setup-progress-screen');
      setIsSwitchingMode(true);
    }
    
    try {
      setDeploymentMode(targetMode);
      setSetupHasFailed(false);
      setSetupErrorMessage('');
      setIsSetupComplete(false);

      // Handle Python setup for CLI mode
      if (targetMode === 'local-cli') {
        const { PythonExecutionService } = await import('../services/PythonExecutionService.js');
        const pythonService = new PythonExecutionService();
        
        // Check Python version first
        addSetupLog('Checking Python installation...', 'info');
        const pythonCheck = await pythonService.checkPythonVersion();
        
        if (!pythonCheck.installed) {
          throw new Error(pythonCheck.error || 'Python 3.10+ is required');
        }
        
        addSetupLog(`Python ${pythonCheck.version} detected`, 'success');
        
        // Setup Python environment
        await pythonService.setupPythonEnvironment((message) => {
          addSetupLog(message, 'info');
        });
        
        // Add final completion log
        addSetupLog('Python environment setup complete!', 'success');
        
      } else {
        // Handle container modes
        const containerManager = ContainerManager.getInstance();
        const monitor = HealthMonitor.getInstance();
        
        // Listen for progress events
        const progressHandler = (message: string) => {
          addSetupLog(message, 'info');
        };
        
        containerManager.on('progress', progressHandler);
        
        // Switch to the target deployment mode
        await containerManager.switchToMode(targetMode);
        
        // Remove listener after completion
        containerManager.off('progress', progressHandler);
        
        // Force immediate health check to get updated container status
        const updatedHealth = await monitor.checkHealth();
        setHealthStatus(updatedHealth);
        
        // Add final completion log
        addSetupLog('Container setup complete!', 'success');
      }
      
      // Mark setup as complete
      setIsSetupComplete(true);
      setIsSwitchingMode(false);
      
      // Auto-continue after a short delay to show success
      setTimeout(() => {
        handleSetupContinue();
      }, 1500);
      
    } catch (error) {
      logger.error('Failed to switch deployment mode', error as Error);
      let errorMessage = (error as Error).message;
      
      // Provide more user-friendly error messages
      if (errorMessage.includes('Python not found')) {
        errorMessage = 'Python 3.10+ is not installed. Please install Python from https://python.org';
      } else if (errorMessage.includes('Python 3.10+ is required')) {
        errorMessage = 'Python 3.10 or higher is required. Please upgrade your Python installation.';
      } else if (errorMessage.includes('No requirements.txt')) {
        errorMessage = 'Missing requirements.txt or pyproject.toml in project root.';
      } else if (errorMessage.includes('Docker compose file not found')) {
        errorMessage = `Missing Docker configuration file. Please ensure docker/docker-compose.yml exists in the project root.`;
      } else if (errorMessage.includes('No such image')) {
        errorMessage = 'Docker image not found. The application will attempt to build it automatically.';
      } else if (errorMessage.includes('Docker is not running')) {
        errorMessage = 'Docker Desktop is not running. Please start Docker Desktop and try again.';
      } else if (errorMessage.includes('Cannot connect to the Docker daemon')) {
        errorMessage = 'Cannot connect to Docker. Please ensure Docker Desktop is running and try again.';
      } else if (errorMessage.includes('Timeout waiting for containers')) {
        errorMessage = 'Container startup timeout. This may be due to resource constraints or network issues. Try again or check Docker Desktop resources.';
      } else if (errorMessage.includes('failed to execute template')) {
        errorMessage = 'Docker version compatibility issue. Please update Docker Desktop to the latest version.';
      }
      
      // Mark setup as failed and set error details
      setSetupHasFailed(true);
      setSetupErrorMessage(errorMessage);
      setIsSwitchingMode(false);
      addSetupLog(`Setup failed: ${errorMessage}`, 'error');
    }
  };

  // Setup Progress Screen Callbacks
  const handleSetupContinue = () => {
    // Transition directly to completion
    onComplete(`✓ ${deploymentMode === 'local-cli' ? 'Local CLI' : deploymentMode === 'single-container' ? 'Agent Container' : 'Enterprise Stack'} setup completed successfully!`);
  };

  const handleSetupRetry = () => {
    // Reset setup state and retry
    setSetupLogs([]);
    setSetupHasFailed(false);
    setSetupErrorMessage('');
    setIsSetupComplete(false);
    setIsSwitchingMode(true);
    
    // Retry after a small delay to ensure state is clean
    setTimeout(() => {
      switchDeploymentMode(deploymentMode);
    }, 100);
  };

  const handleBackToSetup = () => {
    // Reset and go back to deployment selection
    setSetupLogs([]);
    setSetupHasFailed(false);
    setSetupErrorMessage('');
    setIsSetupComplete(false);
    setCurrentStep('deployment-selection');
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

  // Render different content based on current step
  if (currentStep === 'welcome') {
    return (
      <Box flexDirection="column" paddingX={4} paddingY={3}>
        {/* Header rendered by main App.tsx - no duplicate needed */}
        
        <Box marginTop={2} marginBottom={2}>
          <Text bold color={theme.primary}>
            Setup Wizard
          </Text>
        </Box>
        
        <Divider title="Configuration" titleColor={theme.primary} dividerColor={theme.muted} />
        
        <Box borderStyle="round" borderColor={theme.primary} padding={2} marginY={2}>
          <Box flexDirection="column">
            <Text bold color={theme.foreground}>
              Welcome to Cyber-AutoAgent Setup
            </Text>
            <Box marginTop={1}>
              <Text color={theme.muted}>
                Configure your deployment environment and AI providers
              </Text>
            </Box>
            <Box flexDirection="column" marginTop={2} marginLeft={1}>
              <Text color={theme.success}>→ Select deployment mode</Text>
              <Text color={theme.success}>→ Validate system requirements</Text>
              <Text color={theme.success}>→ Configure AI providers</Text>
              <Text color={theme.success}>→ Initialize services</Text>
            </Box>
          </Box>
        </Box>
        
        <Box marginTop={1}>
          <Text color={theme.info}>
            Press <Text bold color={theme.primary}>Enter</Text> to begin or <Text bold color={theme.muted}>Esc</Text> to exit
          </Text>
        </Box>
      </Box>
    );
  }

  if (currentStep === 'deployment-selection') {
    return (
      <Box flexDirection="column" paddingX={2} paddingY={1}>
        {/* Header rendered by main App.tsx - no duplicate needed */}
        
        <Box marginTop={2} marginBottom={2}>
          <Text bold color={theme.primary}>
            Choose Your Deployment Mode
          </Text>
        </Box>
        
        <Divider dividerColor={theme.muted} />
        
        <Box flexDirection="column" marginY={1}>
          {deploymentModes.map((mode, index) => {
            const isSelected = index === selectedModeIndex;
            return (
              <Box
                key={mode.id}
                borderStyle={isSelected ? 'double' : 'single'}
                borderColor={isSelected ? theme.primary : theme.muted}
                padding={1}
                marginY={0.5}
              >
                <Box flexDirection="column">
                  <Box flexDirection="row">
                    <Box marginRight={3} alignSelf="flex-start">
                      <Text color={isSelected ? theme.primary : theme.muted}>
                        {mode.icon}
                      </Text>
                    </Box>
                    <Box flexDirection="column" marginTop={2}>
                      <Box>
                        <Text bold color={isSelected ? theme.primary : theme.foreground}>
                          {mode.name}
                        </Text>
                        {mode.id === 'full-stack' && (
                          <Text color={theme.success}> (Recommended)</Text>
                        )}
                      </Box>
                      <Box marginTop={0.5}>
                        <Text color={theme.muted}>
                          {mode.description}
                        </Text>
                      </Box>
                      <Box marginTop={0.5}>
                        <Text color={theme.info}>Requirements: </Text>
                        <Text color={theme.muted}>{mode.requirements.join(', ')}</Text>
                      </Box>
                    </Box>
                  </Box>
                </Box>
              </Box>
            );
          })}
        </Box>
        
        <Divider dividerColor={theme.muted} />
        
        <Box marginTop={1}>
          <Text color={theme.info}>
            Use <Text bold>↑↓</Text> to select, <Text bold color={theme.primary}>Enter</Text> to confirm
          </Text>
        </Box>
      </Box>
    );
  }


  // Setup Progress Screen - Dedicated screen for environment setup
  if (currentStep === 'setup-progress-screen') {
    return (
      <SetupProgressScreen
        deploymentMode={deploymentMode}
        setupLogs={setupLogs}
        isComplete={isSetupComplete}
        hasFailed={setupHasFailed}
        errorMessage={setupErrorMessage}
        onContinue={handleSetupContinue}
        onRetry={handleSetupRetry}
        onBackToSetup={handleBackToSetup}
      />
    );
  }

  // Original initialization flow UI
  return (
    <Box flexDirection="column" paddingX={2} paddingY={1}>
      {/* Header rendered by main App.tsx - no duplicate needed */}
      
      <Box marginTop={2} marginBottom={2}>
        <Text bold color={theme.primary}>
          Cyber-AutoAgent Initialization
        </Text>
        <Text color={theme.muted}> ({deploymentMode})</Text>
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

        {currentStep === 'switching-containers' && (
          <Box>
            <Spinner type="dots" />
            <Text color={theme.info}> Switching deployment mode...</Text>
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
            <Text color={theme.success}>✓ Deployment mode switched to {deploymentMode}!</Text>
            <Box marginTop={1}>
              <Text color={theme.info}>Environment Status:</Text>
            </Box>
            {healthStatus && healthStatus.services.length > 0 && (
              <Box flexDirection="column" marginTop={1} marginLeft={2}>
                {healthStatus.services.slice(0, 6).map(service => (
                  <Box key={service.name}>
                    <Text color={service.status === 'running' ? theme.success : theme.muted}>
                      {service.status === 'running' ? '✓' : '○'} {service.displayName}
                    </Text>
                    {service.status === 'running' && (
                      <Text color={theme.success}> (Ready)</Text>
                    )}
                  </Box>
                ))}
              </Box>
            )}
            {deploymentMode === 'local-cli' && (
              <Box marginTop={1} marginLeft={2}>
                <Text color={theme.success}>✓ CLI mode - No containers required</Text>
              </Box>
            )}
            <Box marginTop={2}>
              <Text color={theme.info}>Press </Text>
              <Text color={theme.primary} bold>Enter</Text>
              <Text color={theme.info}> to continue to the main interface</Text>
            </Box>
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