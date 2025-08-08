/**
 * Thinking Indicator Component
 * Shows animated thinking state between tool calls
 * Optimized using ink-spinner for better performance
 */

import React, { useState, useEffect } from 'react';
import { Box, Text } from 'ink';
import Spinner from 'ink-spinner';
import { themeManager } from '../themes/theme-manager.js';

interface ThinkingIndicatorProps {
  context?: 'reasoning' | 'tool_preparation' | 'tool_execution' | 'waiting' | 'startup';
  startTime?: number;
  message?: string;
}

// Context-aware messages
const getContextMessage = (context?: string): string => {
  switch (context) {
    case 'startup':
      return 'Initializing';
    case 'reasoning':
      return 'Analyzing';
    case 'tool_preparation':
      return 'Preparing tools';
    case 'tool_execution':
      return 'Executing';
    case 'waiting':
      return 'Waiting for response';
    default:
      return 'Thinking';
  }
};

export const ThinkingIndicator: React.FC<ThinkingIndicatorProps> = ({
  context,
  startTime,
  message
}) => {
  const theme = themeManager.getCurrentTheme();
  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  // Elapsed time tracking (single interval)
  useEffect(() => {
    if (!startTime) return;

    const updateElapsed = () => {
      setElapsedSeconds(Math.floor((Date.now() - startTime) / 1000));
    };

    updateElapsed();
    const interval = setInterval(updateElapsed, 1000);

    return () => clearInterval(interval);
  }, [startTime]);

  // Format elapsed time
  const formatElapsed = (seconds: number): string => {
    if (seconds < 60) {
      return `${seconds}s`;
    }
    const minutes = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${minutes}m ${secs}s`;
  };

  const displayMessage = message || getContextMessage(context);

  return (
    <Box>
      <Text color={theme.primary}>
        <Spinner type="dots" />
      </Text>
      <Text color={theme.muted}> </Text>
      <Text color={theme.foreground}>
        {displayMessage}
      </Text>
      {startTime && (
        <>
          <Text color={theme.muted}> </Text>
          <Text color={theme.muted}>[{formatElapsed(elapsedSeconds)}]</Text>
        </>
      )}
    </Box>
  );
};

// Minimal inline thinking indicator for between events
export const InlineThinking: React.FC<{ message?: string }> = ({ message = 'thinking' }) => {
  const theme = themeManager.getCurrentTheme();
  const [dots, setDots] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setDots(prev => (prev + 1) % 4);
    }, 400);

    return () => clearInterval(interval);
  }, []);

  return (
    <Text color={theme.muted} italic>
      {message}{'.'.repeat(dots)}
    </Text>
  );
};