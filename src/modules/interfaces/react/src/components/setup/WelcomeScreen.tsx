/**
 * WelcomeScreen Component
 * 
 * Clean welcome screen for initial setup
 */

import React, { useMemo } from 'react';
import { Box, Text, useInput } from 'ink';
import { themeManager } from '../../themes/theme-manager.js';

interface WelcomeScreenProps {
  onContinue: () => Promise<void> | void;
  onSkip: () => void;
  terminalWidth?: number;
}

export const WelcomeScreen: React.FC<WelcomeScreenProps> = ({
  onContinue,
  onSkip,
  terminalWidth,
}) => {
  const theme = themeManager.getCurrentTheme();

  // Centered width with stable content to reduce flicker
  const width = terminalWidth || process.stdout.columns || 100;
  const divider = useMemo(() => '─'.repeat(Math.max(20, Math.min(width - 4, 120))), [width]);
  const subtitle = useMemo(
    () => 'Let\'s set up your security assessment environment.',
    []
  );

  useInput((input, key) => {
    if (key.return || input === ' ') {
      onContinue();
    } else if (key.escape) {
      onSkip();
    }
  });

  return (
    <Box width="100%" flexDirection="column" alignItems="center" paddingY={1}>
      <Box width={width} flexDirection="column">
        <Box marginBottom={1}>
          <Text bold color={theme.primary}>Welcome to Cyber-AutoAgent</Text>
        </Box>
        <Text color={theme.muted}>{subtitle}</Text>
        <Text color={theme.muted}>{divider}</Text>

        <Box flexDirection="column" marginTop={1} marginBottom={2}>
          <Text color={theme.info}>Setup will:</Text>
          <Box marginLeft={2} marginTop={1} flexDirection="column">
            <Text color={theme.muted}>• Detect your system configuration</Text>
            <Text color={theme.muted}>• Configure deployment mode</Text>
            <Text color={theme.muted}>• Install required components</Text>
            <Text color={theme.muted}>• Validate everything is working</Text>
          </Box>
        </Box>

        <Box marginTop={1}>
          <Text color={theme.muted}>
            Tip: You can revisit this setup later from the configuration menu.
          </Text>
        </Box>

        <Box marginTop={1}>
          <Text color={theme.info}>
            Press <Text bold color={theme.primary}>Enter</Text> to begin • <Text bold>Esc</Text> to skip
          </Text>
        </Box>
      </Box>
    </Box>
  );
}
;