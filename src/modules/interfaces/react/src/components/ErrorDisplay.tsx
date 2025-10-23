/**
 * ErrorDisplay - Consistent error banner component
 *
 * Provides standardized error rendering across the application with
 * non-blocking display under burst conditions.
 */

import React from 'react';
import { Box, Text } from 'ink';

export interface ErrorDisplayProps {
  /** Error message to display */
  message: string;
  /** Optional error details or stack trace */
  details?: string;
  /** Error type for visual categorization */
  type?: 'error' | 'warning' | 'timeout' | 'auth' | 'config' | 'network';
  /** Whether to show full details */
  expanded?: boolean;
  /** Optional action hint for user */
  actionHint?: string;
}

/**
 * Get error type prefix and color
 */
function getErrorStyle(type: ErrorDisplayProps['type'] = 'error'): { prefix: string; color: string } {
  switch (type) {
    case 'warning':
      return { prefix: '⚠', color: 'yellow' };
    case 'timeout':
      return { prefix: '⏱', color: 'yellow' };
    case 'auth':
      return { prefix: '🔒', color: 'red' };
    case 'config':
      return { prefix: '⚙', color: 'yellow' };
    case 'network':
      return { prefix: '🌐', color: 'red' };
    case 'error':
    default:
      return { prefix: '✗', color: 'red' };
  }
}

/**
 * ErrorDisplay Component
 *
 * Renders errors in a consistent, visually distinct format that won't
 * overwhelm the UI during event bursts.
 */
export const ErrorDisplay: React.FC<ErrorDisplayProps> = ({
  message,
  details,
  type = 'error',
  expanded = false,
  actionHint
}) => {
  const { prefix, color } = getErrorStyle(type);

  return (
    <Box flexDirection="column" borderStyle="round" borderColor={color} paddingX={1}>
      <Box>
        <Text bold color={color}>
          {prefix} {type.toUpperCase()}:
        </Text>
        <Text> {message}</Text>
      </Box>

      {expanded && details && (
        <Box marginTop={1} paddingLeft={2}>
          <Text dimColor>{details}</Text>
        </Box>
      )}

      {actionHint && (
        <Box marginTop={1}>
          <Text dimColor italic>
            💡 {actionHint}
          </Text>
        </Box>
      )}
    </Box>
  );
};

/**
 * Compact error list for displaying multiple errors without overwhelming the UI
 */
export interface ErrorListProps {
  errors: Array<{
    id: string;
    message: string;
    type?: ErrorDisplayProps['type'];
    timestamp?: string;
  }>;
  /** Maximum errors to display */
  maxDisplay?: number;
}

export const ErrorList: React.FC<ErrorListProps> = ({ errors, maxDisplay = 5 }) => {
  const displayErrors = errors.slice(-maxDisplay);
  const hiddenCount = errors.length - displayErrors.length;

  return (
    <Box flexDirection="column">
      {hiddenCount > 0 && (
        <Box marginBottom={1}>
          <Text dimColor>... {hiddenCount} earlier errors hidden</Text>
        </Box>
      )}
      {displayErrors.map((error, idx) => (
        <Box key={error.id || idx} marginBottom={idx < displayErrors.length - 1 ? 1 : 0}>
          <ErrorDisplay message={error.message} type={error.type} />
        </Box>
      ))}
    </Box>
  );
};
