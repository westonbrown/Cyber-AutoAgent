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
    () => 'Initialize your environment for secure, reliable assessments.',
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
    <Box flexDirection="column" alignItems="center" paddingY={1} flexGrow={1}>
      <Box width={width} flexDirection="column">
        <Box marginBottom={1}>
          <Text bold color={theme.primary}>Welcome to Cyber-AutoAgent</Text>
        </Box>
        <Text color={theme.muted}>{subtitle}</Text>
        <Text color={theme.muted}>{divider}</Text>

        <Box flexDirection="column" marginTop={1} marginBottom={2}>
          <Text color={theme.info}>This setup will:</Text>
          <Box marginLeft={2} marginTop={1} flexDirection="column">
            <Text color={theme.muted}>• Detect your system configuration</Text>
            <Text color={theme.muted}>• Select a deployment mode (Local CLI, Single Container, Full Stack)</Text>
            <Text color={theme.muted}>• Install or pull required components</Text>
            <Text color={theme.muted}>• Verify the environment is ready</Text>
          </Box>
        </Box>

        <Box marginTop={1}>
          <Text color={theme.muted}>
            Tip: You can re-run setup anytime from Configuration.
          </Text>
        </Box>

        <Box marginTop={1} width={width} flexDirection="column">
          <Box>
            <Text color={theme.muted}>{divider}</Text>
          </Box>
          <Box justifyContent="flex-start">
            <Text color={theme.info}>
              Press <Text bold color={theme.primary}>Enter</Text> to begin • <Text bold>Esc</Text> to skip
            </Text>
          </Box>
        </Box>
      </Box>
    </Box>
  );
}
;