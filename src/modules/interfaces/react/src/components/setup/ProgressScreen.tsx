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

export const ProgressScreen: React.FC<ProgressScreenProps> = ({
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

  // Animate dots for loading state
  useEffect(() => {
    if (!isLoading && !isComplete) return;

    const interval = setInterval(() => {
      setDots(prev => prev.length >= 3 ? '' : prev + '.');
    }, 500);

    return () => clearInterval(interval);
  }, [isLoading, isComplete]);

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

  const renderProgressBar = () => {
    if (!progress) return null;

    const percentage = Math.round((progress.current / progress.total) * 100);
    const barWidth = 40;
    const filledWidth = Math.round((progress.current / progress.total) * barWidth);
    const emptyWidth = barWidth - filledWidth;

    return (
      <Box flexDirection="column" alignItems="center" marginY={1}>
        {/* Progress bar */}
        <Box>
          <Text color={theme.primary}>
            {'█'.repeat(filledWidth)}
          </Text>
          <Text color={theme.muted}>
            {'░'.repeat(emptyWidth)}
          </Text>
        </Box>
        
        {/* Percentage */}
        <Box marginTop={0.5}>
          <Text color={theme.info}>
            {percentage}% ({progress.current}/{progress.total})
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
      return (
        <Box flexDirection="column" alignItems="center" marginY={2}>
          <Box>
            <Spinner type="dots" />
            <Text color={theme.info}> Configuring environment{dots}</Text>
          </Box>
          <Box marginTop={1}>
            <Text color={theme.muted}>{progress.message}</Text>
          </Box>
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
      return (
        <Box justifyContent="center" marginTop={2}>
          <Text color={theme.muted}>
            Please wait while we configure your deployment...
          </Text>
        </Box>
      );
    }

    return null;
  };

  return (
    <Box flexDirection="column" paddingX={2} paddingY={1}>
      {/* Title */}
      <Box justifyContent="center" marginBottom={2}>
        <Text bold color={theme.primary}>
          Environment Setup
        </Text>
      </Box>

      {/* Mode info */}
      <Box justifyContent="center" marginBottom={1}>
        <Text color={theme.muted}>
          Configuring: <Text color={theme.primary} bold>{modeInfo.name}</Text>
        </Text>
      </Box>
      
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
};