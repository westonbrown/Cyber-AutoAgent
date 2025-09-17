/**
 * ProgressScreen Component
 * 
 * Clean, informative setup progress display inspired by ink examples
 */

import React, { useState, useEffect, useMemo } from 'react';
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
  terminalWidth?: number;
}

// Step details for each deployment mode
const SETUP_STEPS = {
'local-cli': [
    { name: 'preflight', label: 'Initializing setup', detail: 'Loading configuration and environment checks' },
    { name: 'environment', label: 'Setting up Python environment', detail: 'Creating virtual environment and installing packages' },
    { name: 'dependencies', label: 'Installing dependencies', detail: 'pip install -e . (cyberautoagent, strands-sdk)' },
    { name: 'config', label: 'Configuring CLI', detail: 'Setting up configuration files' },
    { name: 'validation', label: 'Validating setup', detail: 'Testing Python module import' }
  ],
'single-container': [
    { name: 'preflight', label: 'Initializing setup', detail: 'Loading configuration and environment checks' },
    { name: 'docker-check', label: 'Checking Docker', detail: 'Verifying Docker Desktop is running' },
    { name: 'pull', label: 'Images availability', detail: 'Checking/pulling cyberautoagent:latest if missing' },
    { name: 'containers-start', label: 'Starting container', detail: 'docker run cyber-autoagent' },
    { name: 'network-setup', label: 'Setting up network', detail: 'Configuring port mappings' },
    { name: 'validation', label: 'Health check', detail: 'Verifying container is responsive' }
  ],
'full-stack': [
    { name: 'preflight', label: 'Initializing setup', detail: 'Loading configuration and environment checks' },
    { name: 'docker-check', label: 'Checking Docker', detail: 'Verifying Docker Desktop is running' },
    { name: 'pull', label: 'Images availability', detail: 'Checking/pulling required images (Langfuse, PostgreSQL, Redis, MinIO, ClickHouse)' },
    { name: 'containers-start', label: 'Starting services', detail: 'docker-compose up -d (4+ containers)' },
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

// Clean leading status tags and punctuation from a line
// - Removes leading bracketed tags like [OK], [WARN], [ERR] (one or multiple)
// - Then trims any remaining leading non-alphanumeric characters and spaces
function cleanLead(text: string): string {
  if (!text) return text;
  // Remove one or more leading bracketed tags (e.g., [OK] [WARN])
  let cleaned = text.replace(/^\s*(\[[^\]]+\]\s*)+/, '');
  // Remove any remaining leading punctuation/whitespace
  cleaned = cleaned.replace(/^[^A-Za-z0-9]+\s*/, '');
  return cleaned;
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
  terminalWidth,
}) => {
  const theme = themeManager.getCurrentTheme();
  const [elapsedTime, setElapsedTime] = useState(0);
  const startTime = React.useRef(Date.now());
  const width = terminalWidth || process.stdout.columns || 100;
  const divider = useMemo(() => '─'.repeat(Math.max(20, Math.min(width - 4, 120))), [width]);


  useEffect(() => {
    // Update timer every second for responsive display
    const interval = setInterval(() => {
      setElapsedTime(Math.floor((Date.now() - startTime.current) / 1000));
    }, 1000); // Update every second
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
const rawIndex = progress ? steps.findIndex(s => s.name === progress.stepName) : -1;
  const currentIndex = Math.max(0, rawIndex);
  const currentStep = rawIndex >= 0 ? steps[rawIndex] : steps[0];
  const installInfo = INSTALLATION_INFO[deploymentMode];

  return (
    <Box width="100%" flexDirection="column" alignItems="center" paddingY={1}>
      <Box width={width} flexDirection="column">
        {/* Header */}
        <Box marginBottom={1}>
          <Text bold color={theme.primary}>
            Setting up {SetupService.getDeploymentModeInfo(deploymentMode).name}
          </Text>
        </Box>
        <Text color={theme.muted}>This prepares your environment and validates connectivity.</Text>
        <Text color={theme.muted}>{divider}</Text>

        {/* Time and progress info */}
        <Box flexDirection="row" justifyContent="space-between" marginBottom={2}>
          <Text color={theme.muted}>Elapsed: {formatTime(elapsedTime)}</Text>
          {progress && (
<Text color={theme.muted}>Step {currentIndex + 1}/{steps.length}</Text>
          )}
        </Box>

        {/* Installation summary (clean, no emojis, no border) */}
        <Box flexDirection="column" marginBottom={2}>
          <Text color={theme.primary} bold>{installInfo.title}</Text>
          <Box flexDirection="column" marginLeft={1}>
            {installInfo.items.map((item, i) => (
              <Text key={i} color={theme.muted}>• {cleanLead(item)}</Text>
            ))}
          </Box>
        </Box>

        {/* Progress steps */}
        <Box flexDirection="column" marginBottom={2}>
          <Text color={theme.info} bold>Progress</Text>
          {/* Show an initializing spinner before first step kicks in */}
          {progress?.stepName === 'initializing' && (
            <Box marginTop={1} alignItems="center">
              <Box marginRight={2}>
                <Spinner type="dots" />
              </Box>
              <Text color={theme.muted}>Initializing setup…</Text>
            </Box>
          )}
          <Box flexDirection="column" marginTop={1}>
{steps.map((step, index) => {
            const state = (() => {
              const hasError = Boolean(error) && index === rawIndex;
              if (hasError) return 'error' as const;
              if (isComplete) return index <= currentIndex ? 'completed' : 'pending';
              if (index < currentIndex) return 'completed' as const;
              if (index === currentIndex) return 'active' as const;
              return 'pending' as const;
            })();
            
            return (
              <Box key={step.name} flexDirection="row" alignItems="flex-start">
                <Box width={4} marginRight={1}>
                  {state === 'completed' && <Text color={theme.success}>✓</Text>}
                  {state === 'active'    && <Spinner type="dots" />}
                  {state === 'pending'   && <Text color={theme.muted}>○</Text>}
                  {state === 'error'     && <Text color={theme.danger}>✗</Text>}
                </Box>
                <Box flexDirection="column" flexGrow={1}>
                  <Text color={
                    state === 'completed' ? theme.success :
                    state === 'active'    ? theme.foreground :
                    state === 'error'     ? theme.danger :
                                             theme.muted
                  }>
                    {step.label}
                  </Text>
                  {state === 'active' && step.detail && (
                    <Box marginLeft={0}>
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
          <Box flexDirection="column" marginBottom={2}>
            {(() => {
            const maxBar = Math.max(20, Math.min(width - 10, 100));
            const barWidth = maxBar;
            const totalSteps = steps.length;
            const activePhaseRatio = Math.max(0, Math.min(1, Number((progress as any)?.meta?.phaseRatio ?? 0)));
            const completedSteps = Math.max(0, currentIndex);
            // Prevent regression: once ratio increases, clamp to a monotonic non-decreasing local max
            const ratioRaw = (completedSteps + activePhaseRatio) / Math.max(1, totalSteps);
            const ratioNow = Math.max(0, Math.min(1, ratioRaw));
            // Store last ratio in a ref for monotonicity
            const r = (global as any).__SETUP_RATIO__ = Math.max(((global as any).__SETUP_RATIO__ || 0), ratioNow);
            const ratio = r;
            const percent = Math.min(100, Math.max(0, Math.round(ratio * 100)));
            const filled = Math.max(0, Math.min(barWidth, Math.floor(ratio * barWidth)));
            const empty = Math.max(0, barWidth - filled);
            return (
              <>
                <Text color={theme.info}>{percent}% complete</Text>
                <Text color={theme.primary}>
                  {'█'.repeat(filled)}
                  {'░'.repeat(empty)}
                </Text>
              </>
            );
          })()}
          {/* Current activity message (trimmed, no emojis) */}
          {progress.message && (
            <Box marginTop={1}>
              <Text color={theme.muted}>
                › {cleanLead(progress.message)}
              </Text>
            </Box>
          )}
          {/* Optional counters during container startup */}
          {progress.stepName === 'containers-start' && Boolean((progress as any)?.meta?.running) && (
            <Box>
              <Text color={theme.muted}>
                {String((progress as any).meta.running)}/{String((progress as any).meta.required)} services started
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
        <Box marginTop={1} flexDirection="column" alignItems="center">
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
    </Box>
  );
})
;