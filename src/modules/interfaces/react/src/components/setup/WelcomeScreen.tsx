/**
 * WelcomeScreen Component
 * 
 * First screen of the setup wizard. Provides welcome message and setup overview.
 * Keeps it simple and focused on getting user ready for deployment selection.
 */

import React from 'react';
import { Box, Text, useInput } from 'ink';
import { themeManager } from '../../themes/theme-manager.js';

interface WelcomeScreenProps {
  onContinue: () => void;
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
    <Box flexDirection="column" paddingX={4} paddingY={2}>
      {/* Title */}
      <Box marginBottom={2}>
        <Text bold color={theme.primary}>
          Setup Wizard
        </Text>
      </Box>

      {/* Welcome message */}
      <Box 
        borderStyle="round" 
        borderColor={theme.primary} 
        paddingX={2}
        paddingY={1}
        marginBottom={3}
      >
        <Box flexDirection="column">
          <Text bold color={theme.foreground}>
            Welcome to Cyber-AutoAgent Setup
          </Text>
          
          <Box marginTop={1}>
            <Text color={theme.muted}>
              Configure your deployment environment and AI providers for security assessments
            </Text>
          </Box>

          <Box flexDirection="column" marginTop={2} marginLeft={1}>
            <Text color={theme.success}>→ Choose deployment mode</Text>
            <Text color={theme.success}>→ Configure environment</Text>
            <Text color={theme.success}>→ Validate system requirements</Text>
            <Text color={theme.success}>→ Initialize services</Text>
          </Box>
        </Box>
      </Box>

      {/* Setup benefits */}
      <Box flexDirection="column" marginBottom={3}>
        <Text color={theme.info} bold>What you'll get:</Text>
        <Box marginLeft={2} flexDirection="column" marginTop={1}>
          <Text color={theme.muted}>• Automated security assessment capabilities</Text>
          <Text color={theme.muted}>• Multiple deployment options (CLI, Container, Enterprise)</Text>
          <Text color={theme.muted}>• Integrated observability and evaluation metrics</Text>
          <Text color={theme.muted}>• Comprehensive documentation and help system</Text>
        </Box>
      </Box>

      {/* Action instructions */}
      <Box justifyContent="center">
        <Text color={theme.info}>
          Press <Text bold color={theme.primary}>Enter</Text> to begin setup or{' '}
          <Text bold color={theme.muted}>Esc</Text> to skip
        </Text>
      </Box>
    </Box>
  );
};