/**
 * ProgressScreen Component
 * 
 * Shows setup progress with real-time updates, progress bar, and status messages.
 * Handles completion states, error handling, and retry functionality.
 */

import React, { useState, useEffect } from 'react';
import { Box, Text, useInput } from 'ink';
import Spinner from 'ink-spinner';
import { themeManager } from '../../themes/theme-manager.js';
import { DeploymentMode, SetupProgress, SetupService } from '../../services/SetupService.js';

interface ProgressScreenProps {
  deploymentMode: DeploymentMode;
  progress: SetupProgress | null;
  isComplete: boolean;
  isLoading: boolean;
  error: string | null;
  onComplete: () => void;
  onRetry: () => void;
  onBack: () => void;
}

export const ProgressScreen: React.FC<ProgressScreenProps> = React.memo(({
  deploymentMode,
  progress,
  isComplete,
  isLoading,
  error,
  onComplete,
  onRetry,
  onBack,
}) => {
  const theme = themeManager.getCurrentTheme();
  const [dots, setDots] = useState('');
  const [elapsedTime, setElapsedTime] = useState(0);
  const [startTime] = useState(Date.now());

  // Animate dots and track elapsed time
  useEffect(() => {
    if (!isLoading && !isComplete) return;

    const interval = setInterval(() => {
      setDots(prev => prev.length >= 3 ? '' : prev + '.');
      setElapsedTime(Math.floor((Date.now() - startTime) / 1000));
    }, 800);

    return () => clearInterval(interval);
  }, [isLoading, isComplete, startTime]);

  useInput((input, key) => {
    if (key.escape) {
      if (isComplete || error) {
        onBack();
      }
      return;
    }

    if (key.return && isComplete) {
      onComplete();
      return;
    }

    if (error) {
      if (input.toLowerCase() === 'r') {
        onRetry();
      } else if (input.toLowerCase() === 'b') {
        onBack();
      }
    }
  });

  const modeInfo = SetupService.getDeploymentModeInfo(deploymentMode);

  // Format elapsed time
  const formatTime = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  // Get deployment-specific estimates
  const getDeploymentEstimates = () => {
    switch (deploymentMode) {
      case 'local-cli':
        return { initial: '~1-2 minutes', duration: '1-2 min' };
      case 'single-container':
        return { initial: '~2-3 minutes', duration: '2-3 min' };
      case 'full-stack':
        return { initial: '~5-8 minutes', duration: '5-8 min' };
      default:
        return { initial: '~2-5 minutes', duration: '2-5 min' };
    }
  };

  // Estimate remaining time based on progress
  const getEstimatedTime = (): string => {
    const estimates = getDeploymentEstimates();
    if (!progress || progress.current === 0) return estimates.initial;
    const progressRatio = progress.current / progress.total;
    const remainingSeconds = Math.max(0, Math.round((elapsedTime / progressRatio) - elapsedTime));
    if (remainingSeconds > 60) {
      return `~${Math.ceil(remainingSeconds / 60)} minutes remaining`;
    }
    return remainingSeconds > 0 ? `~${remainingSeconds} seconds remaining` : 'Almost done';
  };

  // Get step-specific information
  const getStepInfo = (): { title: string; description: string; tips: string[] } => {
    if (!progress) return { title: 'Initializing', description: 'Preparing setup process', tips: [] };
    
    switch (progress.stepName) {
      case 'docker-check':
        return {
          title: 'Docker Verification',
          description: 'Ensuring Docker Desktop is running and accessible',
          tips: ['Make sure Docker Desktop is installed and running', 'Quick verification step (~10-30 seconds)']
        };
      case 'containers-start':
        const containerTips = deploymentMode === 'single-container' 
          ? ['Starting single container with core agent', 'Fastest container setup (~1-2 minutes)']
          : ['Downloading and starting multiple Docker containers', 'Longest step for full stack (~3-4 minutes)', 'First run may take longer due to image downloads'];
        return {
          title: deploymentMode === 'single-container' ? 'Container Deployment' : 'Service Stack Deployment',
          description: deploymentMode === 'single-container' 
            ? 'Starting containerized agent with core functionality'
            : 'Starting containerized services (Agent, Langfuse, PostgreSQL, Redis)',
          tips: containerTips
        };
      case 'network-setup':
        return {
          title: 'Network Configuration',  
          description: deploymentMode === 'single-container'
            ? 'Configuring container networking'
            : 'Configuring service networking and internal communication',
          tips: deploymentMode === 'single-container'
            ? ['Setting up container network access', 'Quick network setup (~15-30 seconds)']
            : ['Setting up container networking', 'Configuring service discovery', 'Usually completes in 30-60 seconds']
        };
      case 'database-setup':
        return {
          title: 'Database Initialization',
          description: 'Initializing PostgreSQL database and schema',
          tips: deploymentMode === 'full-stack'
            ? ['Creating database tables', 'Setting up initial configuration', 'Typically takes 30-90 seconds']
            : ['Setting up lightweight data storage', 'Quick initialization (~15-30 seconds)']
        };
      case 'validation':
        return {
          title: 'System Validation',
          description: deploymentMode === 'single-container' 
            ? 'Verifying container is healthy and responding'
            : 'Verifying all services are healthy and responding',
          tips: deploymentMode === 'single-container'
            ? ['Testing container connectivity', 'Quick validation (~10-20 seconds)']
            : ['Testing service connectivity', 'Validating configuration', 'Final health checks']
        };
      default:
        return {
          title: 'Processing',
          description: progress.message || 'Configuring environment',
          tips: []
        };
    }
  };

  const renderProgressBar = () => {
    if (!progress) return null;

    const percentage = Math.round((progress.current / progress.total) * 100);
    const barWidth = 50;
    const filledWidth = Math.round((progress.current / progress.total) * barWidth);
    const emptyWidth = barWidth - filledWidth;

    return (
      <Box flexDirection="column" alignItems="center" marginY={1}>
        {/* Progress bar - compact */}
        <Box>
          <Text color={theme.primary}>
            {'█'.repeat(filledWidth)}
          </Text>
          <Text color={theme.muted}>
            {'░'.repeat(emptyWidth)}
          </Text>
        </Box>
        
        {/* Progress stats - inline */}
        <Box marginTop={0.5} flexDirection="row">
          <Text color={theme.info}>
            {percentage}% ({progress.current}/{progress.total}) • 
          </Text>
          <Text color={theme.muted}>
            {formatTime(elapsedTime)} elapsed • {getEstimatedTime()}
          </Text>
        </Box>
      </Box>
    );
  };

  const renderStatusSection = () => {
    if (error) {
      return (
        <Box flexDirection="column" alignItems="center" marginY={2}>
          <Text color={theme.danger} bold>✗ Setup Failed</Text>
          <Box marginTop={1} borderStyle="single" borderColor={theme.danger} paddingX={2} paddingY={1}>
            <Text color={theme.danger}>{error}</Text>
          </Box>
        </Box>
      );
    }

    if (isComplete) {
      return (
        <Box flexDirection="column" alignItems="center" marginY={2}>
          <Text color={theme.success} bold>✓ Setup Complete!</Text>
          <Text color={theme.muted}>Your environment is ready for security assessments</Text>
        </Box>
      );
    }

    if (isLoading && progress) {
      const stepInfo = getStepInfo();
      
      return (
        <Box flexDirection="column" alignItems="center" marginY={1}>
          {/* Current step title - compact */}
          <Box>
            <Spinner type="dots" />
            <Text color={theme.info} bold> {stepInfo.title}{dots}</Text>
          </Box>
          
          {/* Step description - compact */}
          <Box marginTop={0.5} marginBottom={1}>
            <Text color={theme.muted} italic>
              {stepInfo.description}
            </Text>
          </Box>
          
          {/* Step tips - more compact */}
          {stepInfo.tips.length > 0 && stepInfo.tips.length <= 2 && (
            <Box flexDirection="column" alignItems="center" marginTop={0.5}>
              {stepInfo.tips.slice(0, 2).map((tip, index) => (
                <Text key={index} color={theme.muted}>• {tip}</Text>
              ))}
            </Box>
          )}
        </Box>
      );
    }

    return (
      <Box flexDirection="column" alignItems="center" marginY={2}>
        <Text color={theme.muted}>Preparing to start setup...</Text>
      </Box>
    );
  };

  const renderActionSection = () => {
    if (error) {
      return (
        <Box justifyContent="center" marginTop={2}>
          <Text color={theme.info}>
            Press <Text bold color={theme.primary}>R</Text> to retry, {' '}
            <Text bold color={theme.muted}>B</Text> to go back, or {' '}
            <Text bold color={theme.muted}>Esc</Text> to cancel
          </Text>
        </Box>
      );
    }

    if (isComplete) {
      return (
        <Box justifyContent="center" marginTop={2}>
          <Text color={theme.info}>
            Press <Text bold color={theme.primary}>Enter</Text> to continue to main application
          </Text>
        </Box>
      );
    }

    if (isLoading) {
      const estimates = getDeploymentEstimates();
      return (
        <Box flexDirection="column" alignItems="center" marginTop={1}>
          <Text color={theme.muted} italic>
            💻 Setup takes {estimates.duration} - you can minimize this window
          </Text>
        </Box>
      );
    }

    return null;
  };

  return (
    <Box flexDirection="column" paddingX={2} paddingY={0}>
      {/* Compact header */}
      <Box justifyContent="center" marginBottom={1}>
        <Text bold color={theme.primary}>🚀 {modeInfo.name} Setup</Text>
        {isLoading && (
          <Text color={theme.warning}> • {getDeploymentEstimates().duration}</Text>
        )}
      </Box>

      {/* Mode info - compact */}
      <Box justifyContent="center" marginBottom={2}>
        <Text color={theme.muted} italic>
          {modeInfo.description}
        </Text>
      </Box>

      {/* Progress section */}
      {renderProgressBar()}
      {renderStatusSection()}
      {renderActionSection()}
    </Box>
  );
}, (prevProps, nextProps) => {
  // Custom comparison to prevent re-renders when only progress message changes frequently
  return (
    prevProps.deploymentMode === nextProps.deploymentMode &&
    prevProps.isComplete === nextProps.isComplete &&
    prevProps.isLoading === nextProps.isLoading &&
    prevProps.error === nextProps.error &&
    prevProps.progress?.current === nextProps.progress?.current &&
    prevProps.progress?.total === nextProps.progress?.total &&
    prevProps.progress?.stepName === nextProps.progress?.stepName
    // Don't compare progress.message to reduce flickering
  );
});