/**
 * WelcomeScreen Component
 * 
 * Clean welcome screen inspired by gemini-cli patterns
 */

import React from 'react';
import { Box, Text, useInput } from 'ink';
import { themeManager } from '../../themes/theme-manager.js';

interface WelcomeScreenProps {
  onContinue: () => Promise<void> | void;
  onSkip: () => void;
}

export const WelcomeScreen: React.FC<WelcomeScreenProps> = ({
  onContinue,
  onSkip,
}) => {
  const theme = themeManager.getCurrentTheme();

  useInput((input, key) => {
    if (key.return || input === ' ') {
      onContinue();
    } else if (key.escape) {
      onSkip();
    }
  });

  return (
    <Box flexDirection="column" paddingX={2} paddingY={2}>
      <Box marginBottom={3}>
        <Text bold color={theme.primary}>
          Welcome to Cyber-AutoAgent
        </Text>
      </Box>

      <Box flexDirection="column" marginBottom={3}>
        <Text>Let's set up your security assessment environment.</Text>
        <Box marginTop={1}>
          <Text color={theme.muted}>This will take just a few moments.</Text>
        </Box>
      </Box>

      <Box flexDirection="column" marginBottom={3}>
        <Text color={theme.info}>Setup will:</Text>
        <Box marginLeft={2} marginTop={1} flexDirection="column">
          <Text color={theme.muted}>• Detect your system configuration</Text>
          <Text color={theme.muted}>• Configure deployment mode</Text>
          <Text color={theme.muted}>• Install required components</Text>
          <Text color={theme.muted}>• Validate everything is working</Text>
        </Box>
      </Box>

      <Box marginTop={2}>
        <Text color={theme.info}>
          Press <Text bold color={theme.primary}>Enter</Text> to begin or{' '}
          <Text bold>Esc</Text> to skip
        </Text>
      </Box>
    </Box>
  );
};