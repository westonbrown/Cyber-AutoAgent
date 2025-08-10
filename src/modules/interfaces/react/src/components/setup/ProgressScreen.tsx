/**
 * ProgressScreen Component
 * 
 * Clean, informative setup progress display inspired by ink examples
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

// Step details for each deployment mode
const SETUP_STEPS = {
  'local-cli': [
    { name: 'environment', label: 'Setting up Python environment', detail: 'Creating virtual environment and installing packages' },
    { name: 'dependencies', label: 'Installing dependencies', detail: 'pip install -e . (cyberautoagent, strands-sdk)' },
    { name: 'config', label: 'Configuring CLI', detail: 'Setting up configuration files' },
    { name: 'validation', label: 'Validating setup', detail: 'Testing Python module import' }
  ],
  'single-container': [
    { name: 'docker-check', label: 'Checking Docker', detail: 'Verifying Docker Desktop is running' },
    { name: 'pull', label: 'Pulling image', detail: 'docker pull cyberautoagent:latest' },
    { name: 'containers-start', label: 'Starting container', detail: 'docker run cyber-autoagent' },
    { name: 'network-setup', label: 'Setting up network', detail: 'Configuring port mappings' },
    { name: 'validation', label: 'Health check', detail: 'Verifying container is responsive' }
  ],
  'full-stack': [
    { name: 'docker-check', label: 'Checking Docker', detail: 'Verifying Docker Desktop is running' },
    { name: 'pull', label: 'Pulling images', detail: 'Downloading Langfuse, PostgreSQL, Redis images' },
    { name: 'containers-start', label: 'Starting services', detail: 'docker-compose up -d (4 containers)' },
    { name: 'network-setup', label: 'Configuring network', detail: 'Setting up inter-container communication' },
    { name: 'database-setup', label: 'Initializing database', detail: 'Creating tables and initial configuration' },
    { name: 'validation', label: 'Health checks', detail: 'Testing all services are connected' }
  ]
};

// What gets installed for each mode
const INSTALLATION_INFO = {
  'local-cli': {
    title: 'Python Environment',
    items: [
      '📦 cyberautoagent package',
      '📦 strands-sdk (agent framework)',
      '📦 Python dependencies (30+ packages)',
      '⚙️ Configuration files'
    ]
  },
  'single-container': {
    title: 'Docker Container',
    items: [
      '🐳 cyber-autoagent container',
      '📦 Pre-configured Python environment',
      '🔧 Basic security tools',
      '⚙️ Container networking'
    ]
  },
  'full-stack': {
    title: 'Enterprise Stack',
    items: [
      '🐳 cyber-autoagent (main agent)',
      '📊 Langfuse (observability)',
      '🗄️ PostgreSQL (database)',
      '⚡ Redis (caching)',
      '🔗 Docker network bridge'
    ]
  }
};

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
  const [elapsedTime, setElapsedTime] = useState(0);
  const startTime = React.useRef(Date.now());

  useEffect(() => {
    // Update timer less frequently to reduce re-renders during setup
    const interval = setInterval(() => {
      setElapsedTime(Math.floor((Date.now() - startTime.current) / 1000));
    }, 5000); // Update every 5 seconds instead of every second
    return () => clearInterval(interval);
  }, []);

  useInput((input, key) => {
    if (key.escape) {
      onBack();
    } else if (key.return && isComplete) {
      onComplete();
    } else if (error && input.toLowerCase() === 'r') {
      onRetry();
    }
  });

  const formatTime = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const steps = SETUP_STEPS[deploymentMode];
  const currentStepIndex = progress ? 
    steps.findIndex(s => s.name === progress.stepName) : -1;
  const currentStep = currentStepIndex >= 0 ? steps[currentStepIndex] : null;
  const installInfo = INSTALLATION_INFO[deploymentMode];

  return (
    <Box flexDirection="column" paddingX={4} paddingY={2}>
      {/* Header */}
      <Box marginBottom={3}>
        <Text bold color={theme.primary}>
          Setting up {SetupService.getDeploymentModeInfo(deploymentMode).name}
        </Text>
      </Box>

      {/* Time and progress info */}
      <Box flexDirection="row" justifyContent="space-between" marginBottom={3}>
        <Text color={theme.muted}>
          Elapsed: {formatTime(elapsedTime)}
        </Text>
        {progress && (
          <Text color={theme.muted}>
            Step {currentStepIndex + 1}/{steps.length}
          </Text>
        )}
      </Box>

      {/* Installation summary (clean, no emojis, no border) */}
      <Box flexDirection="column" marginBottom={2}>
        <Text color={theme.primary} bold>{installInfo.title}</Text>
        <Box flexDirection="column" marginLeft={1}>
          {installInfo.items.map((item, i) => (
            <Text key={i} color={theme.muted}>
              • {item.replace(/^[^A-Za-z0-9]+\s*/, '')}
            </Text>
          ))}
        </Box>
      </Box>

      {/* Progress steps */}
      <Box flexDirection="column" marginBottom={2}>
        <Text color={theme.info} bold>Progress</Text>
        <Box flexDirection="column" marginTop={1}>
          {steps.map((step, index) => {
            const isActive = index === currentStepIndex;
            const isCompleted = currentStepIndex > index || isComplete;
            const isPending = currentStepIndex < index && !isComplete;
            const hasError = error && index === currentStepIndex;
            
            return (
              <Box key={step.name} flexDirection="column">
                <Box width={3}>
                  {isCompleted && <Text color={theme.success}>✓</Text>}
                  {isActive && !hasError && <Spinner type="dots" />}
                  {isPending && <Text color={theme.muted}>○</Text>}
                  {hasError && <Text color={theme.danger}>✗</Text>}
                </Box>
                <Box flexGrow={1}>
                  <Text color={
                    isCompleted ? theme.success :
                    isActive ? theme.foreground :
                    hasError ? theme.danger :
                    theme.muted
                  }>
                    {step.label}
                  </Text>
                  {isActive && step.detail && (
                    <Box marginLeft={2}>
                      <Text color={theme.muted}>
                        {step.detail}
                      </Text>
                    </Box>
                  )}
                </Box>
              </Box>
            );
          })}
        </Box>
      </Box>

      {/* Progress bar */}
      {progress && !error && (
        <Box flexDirection="column" marginBottom={3}>
          <Text color={theme.info}>{Math.round((progress.current / progress.total) * 100)}% complete</Text>
          <Box width={70} borderStyle="single" borderColor={theme.muted} paddingX={1}>
            <Text color={theme.primary}>
              {'█'.repeat(Math.floor((progress.current / progress.total) * 68))}
              {'░'.repeat(68 - Math.floor((progress.current / progress.total) * 68))}
            </Text>
          </Box>
          {/* Current activity message (trimmed, no emojis) */}
          {progress.message && (
            <Box marginTop={1}>
              <Text color={theme.muted}>
                › {progress.message.replace(/^[^A-Za-z0-9]+\s*/, '')}
              </Text>
            </Box>
          )}
        </Box>
      )}

      {/* Status messages */}
      {error && (
        <Box flexDirection="column" marginBottom={2}>
          <Text color={theme.danger} bold>Setup Failed</Text>
          <Text color={theme.foreground}>{error}</Text>
        </Box>
      )}

      {isComplete && !error && (
        <Box marginBottom={2}>
          <Text color={theme.success} bold>Setup Complete!</Text>
        </Box>
      )}

      {/* Actions */}
      <Box marginTop={1}>
        {error ? (
          <Text color={theme.info}>
            Press <Text bold color={theme.primary}>R</Text> to retry • <Text bold>Esc</Text> to go back
          </Text>
        ) : isComplete ? (
          <Text color={theme.info}>
            Press <Text bold color={theme.primary}>Enter</Text> to continue
          </Text>
        ) : (
          <Text color={theme.muted}>
            Press <Text bold>Esc</Text> to cancel
          </Text>
        )}
      </Box>
    </Box>
  );
});