/**
 * Thinking Indicator Component
 * Shows animated thinking state between tool calls
 * Inspired by Codex's bouncing ball and contextual messages
 */

import React, { useState, useEffect } from 'react';
import { Box, Text } from 'ink';
import { themeManager } from '../themes/theme-manager.js';

interface ThinkingIndicatorProps {
  context?: 'reasoning' | 'tool_preparation' | 'tool_execution' | 'waiting' | 'startup';
  startTime?: number;
  message?: string;
}

// Bouncing ball animation frames (inspired by Codex)
const ballFrames = [
  '( ●    )',
  '(  ●   )',
  '(   ●  )',
  '(    ● )',
  '(     ●)',
  '(    ● )',
  '(   ●  )',
  '(  ●   )',
  '( ●    )',
  '(●     )'
];

// Ellipsis animation for text
const ellipsisFrames = ['', '.', '..', '...'];

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
  const [ballFrame, setBallFrame] = useState(0);
  const [ellipsisFrame, setEllipsisFrame] = useState(0);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  // Ball animation (500ms interval for better performance)
  useEffect(() => {
    const interval = setInterval(() => {
      setBallFrame(prev => (prev + 1) % ballFrames.length);
    }, 500);  // Reduced to 500ms (2 updates/sec) for minimal CPU usage

    return () => clearInterval(interval);
  }, []);

  // Ellipsis animation (500ms interval)
  useEffect(() => {
    const interval = setInterval(() => {
      setEllipsisFrame(prev => (prev + 1) % ellipsisFrames.length);
    }, 500);

    return () => clearInterval(interval);
  }, []);

  // Elapsed time tracking
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
    <Box flexDirection="column">
      <Box marginY={0}>
        <Text color={theme.primary}>{ballFrames[ballFrame]}</Text>
        <Text color={theme.muted}> </Text>
        {startTime && (
          <>
            <Text color={theme.warning}>{formatElapsed(elapsedSeconds)}</Text>
            <Text color={theme.muted}> </Text>
          </>
        )}
        <Text color={theme.foreground}>
          {displayMessage}{ellipsisFrames[ellipsisFrame]}
        </Text>
      </Box>
      
      {/* Add spacing after thinking animation for better footer separation */}
      <Box marginTop={2}>
        <Text> </Text>
        <Text> </Text>
        <Text> </Text>
        <Text> </Text>
      </Box>
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