/**
 * Setup Progress Screen
 * 
 * Dedicated screen for showing environment setup progress with logs,
 * status updates, and clear feedback. Shows between setup wizard
 * completion and main application screen.
 */

import React, { useState, useEffect, useCallback } from 'react';
import { Box, Text, Static } from 'ink';
import { createLogger } from '../utils/logger.js';
import { themeManager } from '../themes/theme-manager.js';
import { LogContainer, LogEntry } from './LogContainer.js';
import { ProgressIndicator, StatusIcons, Divider } from './icons.js';

interface SetupProgressScreenProps {
  /** Current deployment mode being set up */
  deploymentMode: 'local-cli' | 'single-container' | 'full-stack';
  /** Setup logs to display */
  setupLogs: LogEntry[];
  /** Whether setup is complete */
  isComplete: boolean;
  /** Whether setup failed */
  hasFailed: boolean;
  /** Error message if setup failed */
  errorMessage?: string;
  /** Callback when user wants to continue */
  onContinue: () => void;
  /** Callback when user wants to retry setup */
  onRetry: () => void;
  /** Callback when user wants to go back to setup wizard */
  onBackToSetup: () => void;
}

const logger = createLogger('SetupProgressScreen');

export const SetupProgressScreen: React.FC<SetupProgressScreenProps> = ({
  deploymentMode,
  setupLogs,
  isComplete,
  hasFailed,
  errorMessage,
  onContinue,
  onRetry,
  onBackToSetup
}) => {
  const theme = themeManager.getCurrentTheme();
  const [currentStep, setCurrentStep] = useState(1);
  const [totalSteps, setTotalSteps] = useState(5);
  const [showCursor, setShowCursor] = useState(true);

  // Determine steps based on deployment mode
  useEffect(() => {
    switch (deploymentMode) {
      case 'local-cli':
        setTotalSteps(4); // Python check, venv, deps, verify
        break;
      case 'single-container':
        setTotalSteps(3); // Docker check, container start, health check
        break;
      case 'full-stack':
        setTotalSteps(5); // Docker check, containers start, network, health check, observability
        break;
    }
  }, [deploymentMode]);

  // Update current step based on log content
  useEffect(() => {
    const latestLog = setupLogs[setupLogs.length - 1];
    if (!latestLog) return;

    const message = latestLog.message.toLowerCase();
    
    if (deploymentMode === 'local-cli') {
      if (message.includes('checking python')) setCurrentStep(1);
      else if (message.includes('virtual environment')) setCurrentStep(2);
      else if (message.includes('installing') || message.includes('dependencies')) setCurrentStep(3);
      else if (message.includes('verifying') || message.includes('complete')) setCurrentStep(4);
    } else if (deploymentMode === 'single-container') {
      if (message.includes('checking docker')) setCurrentStep(1);
      else if (message.includes('starting container')) setCurrentStep(2);
      else if (message.includes('health check') || message.includes('ready')) setCurrentStep(3);
    } else if (deploymentMode === 'full-stack') {
      if (message.includes('checking docker')) setCurrentStep(1);
      else if (message.includes('starting containers')) setCurrentStep(2);
      else if (message.includes('network') || message.includes('connectivity')) setCurrentStep(3);
      else if (message.includes('health check')) setCurrentStep(4);
      else if (message.includes('observability') || message.includes('complete')) setCurrentStep(5);
    }
  }, [setupLogs, deploymentMode]);

  // Animate cursor for active setup
  useEffect(() => {
    if (isComplete || hasFailed) return;

    const interval = setInterval(() => {
      setShowCursor(prev => !prev);
    }, 500);

    return () => clearInterval(interval);
  }, [isComplete, hasFailed]);

  const getModeDisplayName = () => {
    switch (deploymentMode) {
      case 'local-cli': return 'Local CLI Only';
      case 'single-container': return 'Single Container';
      case 'full-stack': return 'Enterprise (Full Stack)';
      default: return deploymentMode;
    }
  };

  // Header is rendered by main App.tsx - no duplicate needed

  const renderProgressSection = () => (
    <Box flexDirection="column" marginBottom={2}>
      {/* Environment Setup Header */}
      <Box justifyContent="center" marginBottom={1}>
        <Text color={theme.accent} bold>Environment Configuration</Text>
      </Box>

      {/* Mode and Progress */}
      <Box justifyContent="center" marginBottom={1}>
        <Text color={theme.muted}>
          Setting up: <Text color={theme.primary} bold>{getModeDisplayName()}</Text>
        </Text>
      </Box>

      {/* Progress Bar */}
      <Box justifyContent="center" marginBottom={1}>
        <ProgressIndicator 
          current={currentStep} 
          total={totalSteps} 
          width={30}
          showPercentage={true}
        />
      </Box>

      {/* Status */}
      <Box justifyContent="center">
        {hasFailed ? (
          <Box>
            <StatusIcons.Error />
            <Text color="red" bold> Setup Failed</Text>
          </Box>
        ) : isComplete ? (
          <Box>
            <StatusIcons.Success />
            <Text color="green" bold> Setup Complete</Text>
          </Box>
        ) : (
          <Box>
            <StatusIcons.Loading />
            <Text color="cyan"> Configuring environment{showCursor ? '...' : '   '}</Text>
          </Box>
        )}
      </Box>
    </Box>
  );

  const renderLogSection = () => (
    <LogContainer
      logs={setupLogs}
      maxHeight={10}
      title="Setup Progress"
      showTimestamps={true}
      autoScroll={true}
      bordered={true}
    />
  );

  const renderErrorSection = () => {
    if (!hasFailed || !errorMessage) return null;

    return (
      <Box flexDirection="column" marginBottom={2}>
        <Box 
          borderStyle="single" 
          borderColor="red" 
          paddingX={1} 
          paddingY={1}
        >
          <Box flexDirection="column">
            <Text color="red" bold>Setup Error:</Text>
            <Text color="red">{errorMessage}</Text>
          </Box>
        </Box>
      </Box>
    );
  };

  const renderActionSection = () => (
    <Box flexDirection="column">
      {/* Instructions */}
      <Box justifyContent="center" marginBottom={1}>
        {hasFailed ? (
          <Text color={theme.muted}>
            Press <Text color={theme.accent} bold>R</Text> to retry, {' '}
            <Text color={theme.accent} bold>B</Text> to go back, or {' '}
            <Text color={theme.accent} bold>Esc</Text> to exit
          </Text>
        ) : isComplete ? (
          <Text color={theme.muted}>
            Press <Text color={theme.accent} bold>Enter</Text> to continue to main application
          </Text>
        ) : (
          <Text color={theme.muted}>
            Please wait while environment is being configured...
          </Text>
        )}
      </Box>
    </Box>
  );

  // Handle keyboard input
  const handleInput = useCallback((input: string, key: any) => {
    if (key.escape) {
      process.exit(0);
    }

    if (hasFailed) {
      if (input.toLowerCase() === 'r') {
        onRetry();
      } else if (input.toLowerCase() === 'b') {
        onBackToSetup();
      }
    } else if (isComplete && key.return) {
      onContinue();
    }
  }, [hasFailed, isComplete, onRetry, onBackToSetup, onContinue]);

  // Register input handler
  useEffect(() => {
    process.stdin.setRawMode?.(true);
    process.stdin.resume();
    process.stdin.on('data', (data) => {
      const input = data.toString();
      const key = {
        return: input === '\r' || input === '\n',
        escape: input === '\u001b'
      };
      handleInput(input, key);
    });

    return () => {
      process.stdin.setRawMode?.(false);
      process.stdin.removeAllListeners('data');
    };
  }, [handleInput]);

  return (
    <Box flexDirection="column" minHeight={process.stdout.rows || 24}>
      {renderProgressSection()}
      {renderLogSection()}
      {renderErrorSection()}
      {renderActionSection()}
    </Box>
  );
};

export default SetupProgressScreen;