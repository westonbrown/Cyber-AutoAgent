/**
 * Deployment Warning Component
 * 
 * Shows warnings when multiple deployments are active but only one is being used.
 * Helps users understand which environment is active and suggests cleanup.
 */

import React from 'react';
import { Box, Text } from 'ink';
import { DeploymentStatus } from '../services/DeploymentDetector.js';
import { themeManager } from '../themes/theme-manager.js';

interface DeploymentWarningProps {
  activeDeployments: DeploymentStatus[];
  configuredMode: string;
}

export const DeploymentWarning: React.FC<DeploymentWarningProps> = ({
  activeDeployments,
  configuredMode
}) => {
  const theme = themeManager.getCurrentTheme();
  
  // Check if multiple deployments are active
  if (activeDeployments.length <= 1) {
    return null;
  }
  
  // Find which ones are NOT being used
  const unusedDeployments = activeDeployments.filter(d => d.mode !== configuredMode);
  
  if (unusedDeployments.length === 0) {
    return null;
  }
  
  return (
    <Box flexDirection="column" borderStyle="single" borderColor={theme.warning} paddingX={1} marginY={1}>
      <Text color={theme.warning} bold>
        ⚠️  Multiple Deployments Detected
      </Text>
      
      <Box marginTop={1}>
        <Text color={theme.info}>
          Active: {configuredMode} (in use)
        </Text>
      </Box>
      
      <Box marginTop={1}>
        <Text color={theme.muted}>
          Also running but not in use:
        </Text>
        {unusedDeployments.map(dep => (
          <Text key={dep.mode} color={theme.muted}>
            • {dep.mode}
          </Text>
        ))}
      </Box>
      
      <Box marginTop={1}>
        <Text color={theme.muted} italic>
          💡 Tip: Use /config to switch modes or stop unused services to save resources
        </Text>
      </Box>
    </Box>
  );
};