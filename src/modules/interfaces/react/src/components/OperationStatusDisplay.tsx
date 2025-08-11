/**
 * Operation Status Display Component
 * Shows flow progress (module→target→objective→ready) and current operation status
 */
import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Box, Text } from 'ink';
import { themeManager } from '../themes/theme-manager.js';

interface FlowState {
  step: 'idle' | 'module' | 'target' | 'objective' | 'ready';
  module?: string;
  target?: string;
  objective?: string;
}

interface CurrentOperation {
  id: string;
  currentStep: number;
  totalSteps: number;
  description: string;
  startTime: Date;
  status: 'running' | 'paused' | 'completed' | 'error' | 'cancelled';
  findings?: number;
}

interface OperationStatusDisplayProps {
  flowState: FlowState;
  currentOperation?: CurrentOperation;
  showFlowProgress?: boolean;
  terminalWidth?: number; // optional width hint from parent to constrain layout
}

export const OperationStatusDisplay: React.FC<OperationStatusDisplayProps> = ({
  flowState,
  currentOperation,
  showFlowProgress = true,
  terminalWidth
}) => {
  const theme = themeManager.getCurrentTheme();

  if (!showFlowProgress && !currentOperation) return null;

  const getFlowStepStatus = (step: string) => {
    switch (step) {
      case 'module':
        return flowState.module ? '✓' : '○';
      case 'target':
        return flowState.target ? '✓' : '○';
      case 'objective':
        return flowState.objective !== undefined ? '✓' : '○';
      case 'ready':
        return flowState.step === 'ready' ? '✓' : '○';
      default:
        return '○';
    }
  };

  const getFlowStepColor = (step: string) => {
    const status = getFlowStepStatus(step);
    return status === '✓' ? theme.success : theme.muted;
  };

  const formatDuration = (startTime: Date) => {
    const elapsed = Math.floor((Date.now() - startTime.getTime()) / 1000);
    const minutes = Math.floor(elapsed / 60);
    const seconds = elapsed % 60;
    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
  };

  // Spinner for running status
  const spinnerFrames = ['-', '\\', '|', '/'];
  const [spinIndex, setSpinIndex] = useState(0);
  const spinTimerRef = useRef<NodeJS.Timeout | null>(null);
  useEffect(() => {
    if (currentOperation?.status === 'running') {
      spinTimerRef.current = setInterval(() => {
        setSpinIndex((i) => (i + 1) % spinnerFrames.length);
      }, 120);
      return () => {
        if (spinTimerRef.current) {
          clearInterval(spinTimerRef.current);
          spinTimerRef.current = null;
        }
      };
    }
    return () => {
      if (spinTimerRef.current) {
        clearInterval(spinTimerRef.current);
        spinTimerRef.current = null;
      }
    };
  }, [currentOperation?.status]);

  // ETA estimation based on steps
  const etaText = useMemo(() => {
    if (!currentOperation) return undefined;
    const { currentStep, totalSteps, startTime } = currentOperation;
    if (!totalSteps || totalSteps <= 0 || currentStep <= 0) return undefined;
    const elapsedSec = Math.max(1, Math.floor((Date.now() - startTime.getTime()) / 1000));
    const perStep = elapsedSec / currentStep;
    const remaining = Math.max(0, Math.round(perStep * (totalSteps - currentStep)));
    const m = Math.floor(remaining / 60);
    const s = remaining % 60;
    return `${m}:${s.toString().padStart(2, '0')}`;
  }, [currentOperation?.currentStep, currentOperation?.totalSteps, currentOperation?.startTime]);

  // Constrain inner width for readability (80–100 cols)
  const innerWidth = useMemo(() => {
    const maxCols = 100;
    const preferred = 90;
    if (!terminalWidth || terminalWidth <= 0) return preferred;
    return Math.min(maxCols, Math.max(60, terminalWidth));
  }, [terminalWidth]);

  // Width-aware divider and memoized subtitle to reduce flicker
  const divider = useMemo(() => {
    const width = Math.max(20, Math.min(innerWidth, 100));
    return '─'.repeat(Math.min(width, 60));
  }, [innerWidth]);

  const subtitle = useMemo(() => {
    if (!showFlowProgress) return '';
    const parts: string[] = [];
    parts.push(flowState.module ? `Module: ${flowState.module}` : 'Select module');
    parts.push(flowState.target ? `Target: ${flowState.target}` : 'Select target');
    parts.push(flowState.objective ? `Objective: ${flowState.objective}` : 'Define objective');
    return parts.join(' • ');
  }, [showFlowProgress, flowState.module, flowState.target, flowState.objective]);

  // Compact progress bar for steps
  const progressBar = useMemo(() => {
    if (!currentOperation || !currentOperation.totalSteps) return null;
    const width = 20; // fixed small bar width for stability
    const ratio = Math.max(0, Math.min(1, currentOperation.currentStep / currentOperation.totalSteps));
    const filled = Math.round(width * ratio);
    const empty = width - filled;
    return `${'█'.repeat(filled)}${'░'.repeat(empty)}`;
  }, [currentOperation?.currentStep, currentOperation?.totalSteps]);

  return (
    <Box width="100%" alignItems="center" marginBottom={1}>
      <Box width={innerWidth} flexDirection="column">
        {/* Title + Subtitle */}
        {showFlowProgress && (flowState.module || flowState.target || flowState.objective) && (
          <Box flexDirection="column">
            <Text color={theme.primary} bold>Setup</Text>
            <Text color={theme.muted}>{subtitle}</Text>
            <Text color={theme.muted}>{divider}</Text>
          </Box>
        )}

        {/* Current Operation */}
        {currentOperation && (
          <Box flexDirection="column">
            {/* Status line with spinner */}
            <Box>
              {currentOperation.status === 'running' && (
                <Text color={theme.info}>{spinnerFrames[spinIndex]} </Text>
              )}
              <Text color={theme.foreground} bold>
                {currentOperation.description}
              </Text>
            </Box>

            {/* Progress + elapsed + ETA */}
            <Box>
              <Text color={theme.warning}>Step {currentOperation.currentStep}/{currentOperation.totalSteps}</Text>
              {progressBar && (
                <>
                  <Text color={theme.muted}> • </Text>
                  <Text color={theme.muted}>[{progressBar}]</Text>
                </>
              )}
              <Text color={theme.muted}> • </Text>
              <Text color={theme.muted}>Elapsed {formatDuration(currentOperation.startTime)}</Text>
              {etaText && (
                <>
                  <Text color={theme.muted}> • </Text>
                  <Text color={theme.muted}>ETA {etaText}</Text>
                </>
              )}
            </Box>

            {/* Badges */}
            <Box>
              {currentOperation.findings !== undefined && (
                <>
                  <Text color={theme.success}>Findings: {currentOperation.findings}</Text>
                  <Text color={theme.muted}> • </Text>
                </>
              )}
              <Text color={currentOperation.status === 'running' ? theme.info : 
                             currentOperation.status === 'paused' ? theme.warning :
                             currentOperation.status === 'error' ? theme.danger : theme.success}>
                {currentOperation.status.toUpperCase()}
              </Text>
            </Box>

            {/* Tips */}
            <Text color={theme.muted}>[ESC] Kill Switch</Text>
          </Box>
        )}
      </Box>
    </Box>
  );
}
;