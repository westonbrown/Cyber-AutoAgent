/**
 * Safety Warning Component
 * 
 * Critical safety and legal authorization warning that appears before
 * any security assessment execution to ensure proper authorization.
 */

import React, { useState } from 'react';
import { Box, Text, useInput } from 'ink';
import { themeManager } from '../themes/theme-manager.js';

interface SafetyWarningProps {
  target: string;
  module: string;
  onConfirm: () => void;
  onCancel: () => void;
}

export const SafetyWarning: React.FC<SafetyWarningProps> = ({ 
  target, 
  module, 
  onConfirm, 
  onCancel 
}) => {
  const theme = themeManager.getCurrentTheme();
  const [acknowledged, setAcknowledged] = useState(false);

  useInput((input, key) => {
    if (key.escape) {
      onCancel();
      return;
    }
    
    if (input === 'y' || input === 'Y') {
      if (acknowledged) {
        onConfirm();
      } else {
        setAcknowledged(true);
      }
      return;
    }
    
    if (input === 'n' || input === 'N') {
      onCancel();
      return;
    }
  });

  return (
    <Box 
      flexDirection="column" 
      borderStyle="double" 
      borderColor={theme.danger} 
      padding={1}
      width="80%"
    >
      {/* Header */}
      <Box marginBottom={1}>
        <Text color={theme.danger} bold>
          ⚠️  SECURITY ASSESSMENT AUTHORIZATION WARNING
        </Text>
      </Box>

      {/* Warning Content */}
      <Box flexDirection="column" marginBottom={1}>
        <Text color={theme.foreground}>
          You are about to execute a <Text color={theme.accent} bold>{module}</Text> security assessment against:
        </Text>
        <Text color={theme.primary} bold>
          Target: {target}
        </Text>
        
        <Box marginTop={1} marginBottom={1}>
          <Text color={theme.warning}>
            IMPORTANT: Only proceed if you have:
          </Text>
        </Box>
        
        <Box flexDirection="column" paddingLeft={2}>
          <Text color={theme.foreground}>
            • <Text color={theme.accent}>EXPLICIT WRITTEN AUTHORIZATION</Text> to test this target
          </Text>
          <Text color={theme.foreground}>
            • <Text color={theme.accent}>LEGAL PERMISSION</Text> from the target owner/organization
          </Text>
          <Text color={theme.foreground}>
            • <Text color={theme.accent}>PROPER SAFETY MEASURES</Text> in place to prevent damage
          </Text>
          <Text color={theme.foreground}>
            • <Text color={theme.accent}>APPROPRIATE SCOPE</Text> and testing boundaries defined
          </Text>
        </Box>

        <Box marginTop={1}>
          <Text color={theme.danger}>
            Unauthorized security testing may violate local, state, and federal laws.
            You assume full legal responsibility for this cyber operation.
          </Text>
        </Box>
      </Box>

      {/* Confirmation Steps */}
      {!acknowledged ? (
        <Box flexDirection="column">
          <Text color={theme.info}>
            Do you acknowledge that you have proper authorization? (y/N)
          </Text>
        </Box>
      ) : (
        <Box flexDirection="column">
          <Text color={theme.success}>
            ✓ Authorization acknowledged
          </Text>
          <Box marginTop={1}>
            <Text color={theme.info}>
              Proceed with cyber operation? (y/N)
            </Text>
          </Box>
        </Box>
      )}

      {/* Footer */}
      <Box marginTop={1} borderTop borderColor={theme.muted} paddingTop={1}>
        <Text color={theme.muted}>
          Press 'y' to continue, 'n' to cancel, or Esc to abort
        </Text>
      </Box>
    </Box>
  );
};