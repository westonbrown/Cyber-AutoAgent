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
  toolName?: string;
  toolCategory?: string;
  enabled?: boolean;
}

// Fun thinking phrases that cycle through
const THINKING_PHRASES = [
  'Thinking',
  'Analyzing',
  'Processing',
  'Computing',
  'Hacking away',
  'Exploring paths',
  'Crafting strategy',
  'Brewing ideas',
  'Pondering options',
  'Weighing approaches',
  'Scanning possibilities',
  'Plotting next move',
  'Connecting dots',
  'Crunching data',
  'Running scenarios',
  'Mapping vectors',
  'Testing theories',
  'Building game plan',
  'Evaluating angles',
  'Synthesizing intel',
  'Formulating tactics',
  'Calibrating approach',
  'Piecing together',
  'Calculating odds',
  'Assembling strategy',
  'Decoding patterns',
  'Triangulating path',
  'Optimizing route',
  'Spinning up ideas',
  'Cooking up plan'
];

// Context-aware messages
const getContextMessage = (context?: string, phraseIndex?: number): string => {
  switch (context) {
    case 'startup':
      return 'Initializing';
    case 'reasoning':
    case 'tool_preparation':
    case 'tool_execution':
    case 'waiting':
    default:
      // Cycle through fun phrases for non-startup contexts
      return THINKING_PHRASES[phraseIndex || 0];
  }
};

export const ThinkingIndicator: React.FC<ThinkingIndicatorProps> = ({
  context,
  startTime,
  message,
  enabled = true
}) => {
  const theme = themeManager.getCurrentTheme();
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [phraseIndex, setPhraseIndex] = useState(Math.floor(Math.random() * THINKING_PHRASES.length));

  // Elapsed time tracking (single interval)
  useEffect(() => {
    if (!startTime || !enabled) return;

    const updateElapsed = () => {
      setElapsedSeconds(Math.floor((Date.now() - startTime) / 1000));
    };

    updateElapsed();
    const interval = setInterval(updateElapsed, 1000);

    return () => clearInterval(interval);
  }, [startTime, enabled]);

  // Cycle through phrases every 18 seconds (only for non-startup contexts)
  useEffect(() => {
    if (context === 'startup' || !enabled) return;

    const interval = setInterval(() => {
      setPhraseIndex(prev => (prev + 1) % THINKING_PHRASES.length);
    }, 18000);

    return () => clearInterval(interval);
  }, [context, enabled]);

  // Format elapsed time
  const formatElapsed = (seconds: number): string => {
    if (seconds < 60) {
      return `${seconds}s`;
    }
    const minutes = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${minutes}m ${secs}s`;
  };

  const displayMessage = message || getContextMessage(context, phraseIndex);

  return (
    <Box flexDirection="column">
      {/* Add visual breathing room before spinner */}
      <Text>{'\n'}</Text>
      <Box>
        {enabled ? (
          <Text color={theme.primary}>
            <Spinner type="dots" />
          </Text>
        ) : (
          <Text color={theme.muted}>[BUSY]</Text>
        )}
        <Text color={theme.muted}> </Text>
        <Text color={theme.foreground}>
          {displayMessage}
        </Text>
        {startTime && (
          <>
            <Text color={theme.muted}> </Text>
            <Text color={theme.muted}>[{formatElapsed(enabled ? elapsedSeconds : Math.floor(((startTime && Date.now()) ? (Date.now() - startTime) : 0) / 1000))}]</Text>
          </>
        )}
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