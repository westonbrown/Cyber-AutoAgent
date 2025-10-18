/**
 * HITLInterventionPanel - Human-in-the-Loop Intervention Interface
 *
 * Interactive panel for reviewing and providing feedback on tool executions
 * before they run. Enables human oversight of potentially destructive operations.
 */

import React, { useState } from 'react';
import { Box, Text } from 'ink';
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
  /** Agent interpretation awaiting approval */
  interpretation?: {
    text: string;
    modifiedParameters: Record<string, any>;
  };
  /** Whether panel is currently active */
  isActive: boolean;
  /** Callback for submitting feedback */
  onSubmitFeedback: (feedbackType: string, content: string) => void;
  /** Callback for confirming interpretation */
  onConfirmInterpretation: (approved: boolean) => void;
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
  interpretation,
  isActive,
  onSubmitFeedback,
  onConfirmInterpretation,
}) => {
  const [mode, setMode] = useState<'review' | 'feedback' | 'confirm'>('review');
  const [feedbackText, setFeedbackText] = useState('');

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

  // Review mode - show tool details and options
  if (mode === 'review' && !interpretation) {
    return (
      <Box flexDirection="column" borderStyle="round" borderColor="yellow" padding={1}>
        <Box marginBottom={1}>
          <Text bold color="yellow">
            ⚠️  HITL INTERVENTION REQUIRED
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

        {confidence !== undefined && (
          <Box marginBottom={1}>
            <Text>
              Confidence: <Text color={confidence < 50 ? 'red' : confidence < 70 ? 'yellow' : 'green'}>
                {confidence}%
              </Text>
            </Text>
          </Box>
        )}

        <Box marginBottom={1} flexDirection="column">
          <Text bold>Parameters:</Text>
          <Text color="gray">{formatParameters(parameters)}</Text>
        </Box>

        <Box marginBottom={1} flexDirection="column">
          <Text bold>Options:</Text>
          <Text>  [a] Approve - proceed with tool execution</Text>
          <Text>  [c] Correction - provide modified parameters</Text>
          <Text>  [s] Suggestion - suggest alternative approach</Text>
          <Text>  [r] Reject - cancel this tool execution</Text>
        </Box>

        <Box>
          <Text dimColor>Press a key to choose an option...</Text>
        </Box>
      </Box>
    );
  }

  // Feedback input mode
  if (mode === 'feedback') {
    return (
      <Box flexDirection="column" borderStyle="round" borderColor="cyan" padding={1}>
        <Box marginBottom={1}>
          <Text bold color="cyan">
            💬 Provide Feedback
          </Text>
        </Box>

        <Box marginBottom={1}>
          <Text>
            Tool: <Text bold>{toolName}</Text>
          </Text>
        </Box>

        <Box marginBottom={1} flexDirection="column">
          <Text>Enter your feedback (press Enter to submit):</Text>
          <Box marginTop={1}>
            <Text color="cyan">&gt; </Text>
            <TextInput
              value={feedbackText}
              onChange={setFeedbackText}
              onSubmit={(value) => {
                if (value.trim()) {
                  // Determine feedback type based on earlier selection
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

  // Confirmation mode - review agent interpretation
  if (mode === 'confirm' && interpretation) {
    return (
      <Box flexDirection="column" borderStyle="round" borderColor="green" padding={1}>
        <Box marginBottom={1}>
          <Text bold color="green">
            ✓ Agent Interpretation
          </Text>
        </Box>

        <Box marginBottom={1} flexDirection="column">
          <Text bold>Interpretation:</Text>
          <Text color="green">{interpretation.text}</Text>
        </Box>

        <Box marginBottom={1} flexDirection="column">
          <Text bold>Modified Parameters:</Text>
          <Text color="gray">{formatParameters(interpretation.modifiedParameters)}</Text>
        </Box>

        <Box marginBottom={1} flexDirection="column">
          <Text bold>Options:</Text>
          <Text>  [y] Yes - approve and proceed</Text>
          <Text>  [n] No - reject and provide new feedback</Text>
        </Box>

        <Box>
          <Text dimColor>Press y or n to choose...</Text>
        </Box>
      </Box>
    );
  }

  return null;
};
