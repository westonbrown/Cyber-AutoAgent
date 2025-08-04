/**
 * Operation Status Display Component
 * Shows flow progress (module→target→objective→ready) and current operation status
 */
import React from 'react';
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
}

export const OperationStatusDisplay: React.FC<OperationStatusDisplayProps> = ({
  flowState,
  currentOperation,
  showFlowProgress = true
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

  return (
    <Box flexDirection="column" marginBottom={1}>
      {/* Flow Progress */}
      {showFlowProgress && (flowState.module || flowState.target || flowState.objective) && (
        <Box borderStyle="single" borderColor={theme.muted} paddingX={1}>
          <Text color={theme.info} bold>Flow Progress: </Text>
          <Text color={getFlowStepColor('module')}>
            Module {getFlowStepStatus('module')}
          </Text>
          <Text color={theme.muted}> → </Text>
          <Text color={getFlowStepColor('target')}>
            Target {getFlowStepStatus('target')}
          </Text>
          <Text color={theme.muted}> → </Text>
          <Text color={getFlowStepColor('objective')}>
            Objective {getFlowStepStatus('objective')}
          </Text>
          <Text color={theme.muted}> → </Text>
          <Text color={getFlowStepColor('ready')}>
            Ready {getFlowStepStatus('ready')}
          </Text>
        </Box>
      )}

      {/* Current Values */}
      {(flowState.module || flowState.target || flowState.objective) && (
        <Box flexDirection="column" borderStyle="round" borderColor={theme.secondary} paddingX={1}>
          <Text color={theme.warning} bold>Current Configuration:</Text>
          {flowState.module && (
            <Box>
              <Text color={theme.muted}>Module: </Text>
              <Text color={theme.info}>{flowState.module}</Text>
            </Box>
          )}
          {flowState.target && (
            <Box>
              <Text color={theme.muted}>Target: </Text>
              <Text color={theme.success}>{flowState.target}</Text>
            </Box>
          )}
          {flowState.objective && (
            <Box>
              <Text color={theme.muted}>Objective: </Text>
              <Text color={theme.foreground}>{flowState.objective}</Text>
            </Box>
          )}
        </Box>
      )}

      {/* Current Operation */}
      {currentOperation && (
        <Box borderStyle="double" borderColor={theme.primary} paddingX={1}>
          <Box flexDirection="column">
            <Box>
              <Text color={theme.primary} bold>🔄 Operation {currentOperation.id} </Text>
              <Text color={theme.muted}>({formatDuration(currentOperation.startTime)})</Text>
            </Box>
            <Box>
              <Text color={theme.warning}>
                Step {currentOperation.currentStep}/{currentOperation.totalSteps}: 
              </Text>
              <Text color={theme.foreground}> {currentOperation.description}</Text>
            </Box>
            {currentOperation.findings !== undefined && (
              <Box>
                <Text color={theme.success}>
                  Findings: {currentOperation.findings}
                </Text>
                <Text color={theme.muted}> • </Text>
                <Text color={currentOperation.status === 'running' ? theme.info : 
                              currentOperation.status === 'paused' ? theme.warning :
                              currentOperation.status === 'error' ? theme.danger : theme.success}>
                  {currentOperation.status.toUpperCase()}
                </Text>
              </Box>
            )}
          </Box>
        </Box>
      )}
    </Box>
  );
};