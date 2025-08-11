/**
 * Setup Progress Screen
 * 
 * Dedicated screen for showing environment setup progress with logs,
 * status updates, and clear feedback. Shows between setup wizard
 * completion and main application screen.
 */

import React, { useState, useEffect, useCallback } from 'react';
import { Box, Text, Static, useInput, useApp } from 'ink';
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
  const { exit } = useApp();
  const [currentStep, setCurrentStep] = useState(1);
  const [totalSteps, setTotalSteps] = useState(5);
  const [startTime] = useState<Date>(new Date());
  const [elapsed, setElapsed] = useState<string>('0:00');
  const [showCursor, setShowCursor] = useState(true);
  const autoContinuedRef = React.useRef(false);

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

  // Elapsed timer (mm:ss)
  useEffect(() => {
    if (isComplete || hasFailed) return;
    const interval = setInterval(() => {
      const seconds = Math.max(0, Math.floor((Date.now() - startTime.getTime()) / 1000));
      const mm = Math.floor(seconds / 60).toString();
      const ss = (seconds % 60).toString().padStart(2, '0');
      setElapsed(`${mm}:${ss}`);
    }, 1000);
    return () => clearInterval(interval);
  }, [startTime, isComplete, hasFailed]);

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

  // Auto-continue to configuration after successful setup
  useEffect(() => {
    if (isComplete && !hasFailed && !autoContinuedRef.current) {
      autoContinuedRef.current = true;
      // Slight delay to let UI render the "Setup Complete" state before transitioning
      const t = setTimeout(() => {
        try { onContinue(); } catch {}
      }, 300);
      return () => clearTimeout(t);
    }
  }, [isComplete, hasFailed, onContinue]);

  const getModeDisplayName = () => {
    switch (deploymentMode) {
      case 'local-cli': return 'Local CLI';
      case 'single-container': return 'Single Container';
      case 'full-stack': return 'Enterprise Stack';
      default: return deploymentMode;
    }
  };

  // Header is rendered by main App.tsx - no duplicate needed

  const renderProgressSection = () => (
    <Box flexDirection="column" marginBottom={1}>
      {/* Compact header line */}
      <Box justifyContent="center" marginBottom={1}>
        {/* Loading animation belongs with the headline when in progress */}
        {!isComplete && !hasFailed && (
          <>
            <StatusIcons.Loading />
            <Text> </Text>
          </>
        )}
        <Text color={theme.muted}>
          Setting up <Text color={theme.primary} bold>{getModeDisplayName()}</Text>
          {'  '}•{'  '}Elapsed <Text color={theme.accent}>{elapsed}</Text>
          {'  '}•{'  '}Step {currentStep}/{totalSteps}
        </Text>
      </Box>

      {/* Progress Bar */}
      <Box justifyContent="center" marginBottom={1}>
        <ProgressIndicator 
          current={currentStep} 
          total={totalSteps} 
          width={50}
          showPercentage={true}
        />
      </Box>

      {/* Status */}
      <Box justifyContent="center" marginBottom={1}>
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
            <Text color="cyan">Configuring environment{showCursor ? '...' : '   '}</Text>
          </Box>
        )}
      </Box>

      {/* Step checklist */}
      <Box flexDirection="column" alignItems="center">
        {(() => {
          const steps: string[] = (() => {
            if (deploymentMode === 'local-cli') return ['Checking Python', 'Create virtual environment', 'Install dependencies', 'Verify environment'];
            if (deploymentMode === 'single-container') return ['Checking Docker', 'Starting agent container', 'Health check'];
            return ['Checking Docker', 'Starting containers', 'Network connectivity', 'Health checks', 'Enable observability'];
          })();
          return (
            <Box flexDirection="column">
              {steps.map((label, idx) => {
                const index = idx + 1;
                const isDone = index < currentStep || (isComplete && index <= totalSteps);
                const isActive = index === currentStep && !isComplete && !hasFailed;
                const color = isDone ? theme.success : isActive ? theme.accent : theme.muted;
                const icon = isDone ? <StatusIcons.Success /> : isActive ? <StatusIcons.Loading /> : <Text color={theme.muted}>○</Text>;
                return (
                  <Box key={label} flexDirection="row" alignItems="center">
                    <Box width={3} justifyContent="flex-end">{icon}</Box>
                    <Text> </Text>
                    <Text color={color}>{label}</Text>
                  </Box>
                );
              })}
            </Box>
          );
        })()}
      </Box>
    </Box>
  );

  const renderLogSection = () => (
    <Box marginY={1}>
      <LogContainer
        logs={setupLogs}
        maxHeight={10}
        title="Setup Progress"
        showTimestamps={true}
        autoScroll={true}
        bordered={true}
      />
    </Box>
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
    <Box flexDirection="column" marginTop={1}>
      <Box justifyContent="center">
        {hasFailed ? (
          <Text color={theme.muted}>
            Press <Text color={theme.accent} bold>R</Text> to retry, <Text color={theme.accent} bold>B</Text> to go back, or <Text color={theme.accent} bold>Esc</Text> to exit
          </Text>
        ) : isComplete ? (
          <Text color={theme.muted}>
            Press <Text color={theme.accent} bold>Enter</Text> to continue to configuration
          </Text>
        ) : (
          <Text color={theme.muted}>Press <Text color={theme.accent} bold>Esc</Text> to cancel</Text>
        )}
      </Box>
    </Box>
  );

  // Handle keyboard input
  const handleInput = useCallback((input: string, key: any) => {
    if (key.escape) {
      // Use Ink's exit to allow proper cleanup
      exit();
      return;
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
  }, [hasFailed, isComplete, onRetry, onBackToSetup, onContinue, exit]);

  // Use React Ink's useInput hook instead of manually handling stdin
  // This prevents conflicts and memory leaks
  useInput((input, key) => {
    handleInput(input, key);
  });

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