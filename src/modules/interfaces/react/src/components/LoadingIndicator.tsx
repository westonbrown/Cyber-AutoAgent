/**
 * Loading Indicator Component
 * 
 * Provides comprehensive visual feedback during long-running operations
 * with dynamic status messages and progress indication.
 */

import React, { useState, useEffect } from 'react';
import { Box, Text } from 'ink';
import Spinner from 'ink-spinner';

interface LoadingPhrase {
  text: string;
  duration: number;
}

const LOADING_PHRASES: LoadingPhrase[] = [
  { text: 'Analyzing security posture', duration: 3000 },
  { text: 'Scanning network services', duration: 2500 },
  { text: 'Evaluating vulnerabilities', duration: 3500 },
  { text: 'Collecting evidence', duration: 2000 },
  { text: 'Generating insights', duration: 2500 },
  { text: 'Correlating findings', duration: 3000 },
];

interface LoadingIndicatorProps {
  text?: string;
  showPhases?: boolean;
  spinnerType?: any;
  color?: string;
}

export const LoadingIndicator: React.FC<LoadingIndicatorProps> = ({
  text = 'Processing',
  showPhases = true,
  spinnerType = 'dots',
  color = 'cyan'
}) => {
  const [currentPhraseIndex, setCurrentPhraseIndex] = useState(0);
  const [dots, setDots] = useState('');

  useEffect(() => {
    if (!showPhases) return;

    const interval = setInterval(() => {
      setCurrentPhraseIndex((prev) => (prev + 1) % LOADING_PHRASES.length);
    }, LOADING_PHRASES[currentPhraseIndex].duration);

    return () => clearInterval(interval);
  }, [currentPhraseIndex, showPhases]);

  useEffect(() => {
    const dotsInterval = setInterval(() => {
      setDots((prev) => (prev.length >= 3 ? '' : prev + '.'));
    }, 500);

    return () => clearInterval(dotsInterval);
  }, []);

  const displayText = showPhases 
    ? LOADING_PHRASES[currentPhraseIndex].text 
    : text;

  return (
    <Box>
      <Text color={color}>
        <Spinner type={spinnerType} />
      </Text>
      <Text> {displayText}{dots}</Text>
    </Box>
  );
};

export default LoadingIndicator;