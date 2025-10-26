/**
 * HITLInterventionPanel - Human-in-the-Loop Intervention Interface
 *
 * Interactive panel for reviewing and providing feedback on tool executions
 * before they run. Enables human oversight of potentially destructive operations.
 */

import React, { useState } from 'react';
import { Box, Text, useInput } from 'ink';
import TextInput from 'ink-text-input';

interface HITLInterventionPanelProps {
  /** Tool name being reviewed */
  toolName: string;
  /** Unique tool invocation ID */
  toolId: string;
  /** Tool parameters to review */
  parameters: Record<string, any>;
  /** Reason for pause (e.g., "destructive_operation") */
  reason?: string;
  /** Confidence score if available (0-100) */
  confidence?: number;
  /** Whether panel is currently active */
  isActive: boolean;
  /** Callback for submitting feedback */
  onSubmitFeedback: (feedbackType: string, content: string) => void;
}

/**
 * HITLInterventionPanel Component
 */
export const HITLInterventionPanel: React.FC<HITLInterventionPanelProps> = ({
  toolName,
  toolId,
  parameters,
  reason,
  confidence,
  isActive,
  onSubmitFeedback,
}) => {
  const isManualIntervention = toolName === 'manual_intervention';
  const [feedbackText, setFeedbackText] = useState('');
  const [mode, setMode] = useState<'review' | 'feedback'>('review');

  // Keyboard handler for destructive operations
  useInput((input, key) => {
    if (!isActive || isManualIntervention) return;

    // Switch to feedback mode when [c] pressed for destructive operations
    if (mode === 'review' && input === 'c') {
      setMode('feedback');
    }

    // Escape to go back to review mode
    if (mode === 'feedback' && key.escape) {
      setMode('review');
      setFeedbackText('');
    }
  });

  // Show idle state when HITL is enabled but no intervention needed
  if (!isActive) {
    return (
      <Box flexDirection="column" borderStyle="round" borderColor="green" paddingX={1} marginBottom={1}>
        <Text color="green">
          ✓ HITL: Active - monitoring operations (press [i] for manual intervention)
        </Text>
      </Box>
    );
  }

  // Format parameters for display
  const formatParameters = (params: Record<string, any>): string => {
    try {
      return JSON.stringify(params, null, 2);
    } catch {
      return String(params);
    }
  };

  // Manual Intervention - Direct text input
  if (isManualIntervention) {
    return (
      <Box flexDirection="column" borderStyle="round" borderColor="cyan" padding={1}>
        <Box marginBottom={1}>
          <Text bold color="cyan">
            💬 Provide Feedback to Agent
          </Text>
        </Box>

        <Box marginBottom={1} flexDirection="column">
          <Box marginTop={1}>
            <Text color="cyan">&gt; </Text>
            <TextInput
              value={feedbackText}
              onChange={setFeedbackText}
              placeholder="Type your feedback and press Enter..."
              onSubmit={(value) => {
                if (value.trim()) {
                  onSubmitFeedback('suggestion', value);
                  setFeedbackText('');
                }
              }}
            />
          </Box>
        </Box>

        <Box>
          <Text dimColor>Press [Esc] to cancel</Text>
        </Box>
      </Box>
    );
  }

  // Auto-pause (Destructive Operation) - Show tool details with approval options
  if (!isManualIntervention) {
    const hasParameters = parameters && Object.keys(parameters).length > 0;

    return (
      <Box flexDirection="column" borderStyle="round" borderColor="yellow" padding={1}>
        <Box marginBottom={1}>
          <Text bold color="yellow">
            ⚠️  DESTRUCTIVE OPERATION - REVIEW REQUIRED
          </Text>
        </Box>

        <Box marginBottom={1}>
          <Text>
            Tool: <Text bold color="cyan">{toolName}</Text>
          </Text>
        </Box>

        {reason && (
          <Box marginBottom={1}>
            <Text>
              Reason: <Text color="yellow">{reason}</Text>
            </Text>
          </Box>
        )}

        {hasParameters && (
          <Box marginBottom={1} flexDirection="column">
            <Text bold>Parameters:</Text>
            <Text color="gray">{formatParameters(parameters)}</Text>
          </Box>
        )}

        <Box marginBottom={1} flexDirection="column">
          <Text bold>Options:</Text>
          <Text>  [a] Approve - proceed with operation</Text>
          <Text>  [c] Correction - provide modified parameters</Text>
          <Text>  [r] Reject - cancel this operation</Text>
          <Text dimColor>  [Esc] Cancel and resume</Text>
        </Box>

        <Box>
          <Text dimColor>Press a key to choose...</Text>
        </Box>
      </Box>
    );
  }

  // Feedback input mode (for destructive operations when user presses [c])
  if (mode === 'feedback') {
    return (
      <Box flexDirection="column" borderStyle="round" borderColor="cyan" padding={1}>
        <Box marginBottom={1}>
          <Text bold color="cyan">
            💬 Provide Correction
          </Text>
        </Box>

        <Box marginBottom={1}>
          <Text>
            Tool: <Text bold>{toolName}</Text>
          </Text>
        </Box>

        <Box marginBottom={1} flexDirection="column">
          <Text>Enter modified parameters or instructions:</Text>
          <Box marginTop={1}>
            <Text color="cyan">&gt; </Text>
            <TextInput
              value={feedbackText}
              onChange={setFeedbackText}
              onSubmit={(value) => {
                if (value.trim()) {
                  onSubmitFeedback('correction', value);
                  setFeedbackText('');
                  setMode('review');
                }
              }}
            />
          </Box>
        </Box>

        <Box>
          <Text dimColor>Press Esc to cancel</Text>
        </Box>
      </Box>
    );
  }

  return null;
};
