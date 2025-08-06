/**
 * DeploymentSelectionScreen Component
 * 
 * Screen for selecting deployment mode. Shows available options with descriptions
 * and requirements. Handles keyboard navigation and selection.
 */

import React, { useState } from 'react';
import { Box, Text, useInput } from 'ink';
import { themeManager } from '../../themes/theme-manager.js';
import { DeploymentMode, SetupService } from '../../services/SetupService.js';

interface DeploymentSelectionScreenProps {
  onSelect: (mode: DeploymentMode) => void;
  onBack: () => void;
}

export const DeploymentSelectionScreen: React.FC<DeploymentSelectionScreenProps> = ({
  onSelect,
  onBack,
}) => {
  const theme = themeManager.getCurrentTheme();
  const [selectedIndex, setSelectedIndex] = useState(1); // Default to full-stack

  const deploymentModes: DeploymentMode[] = ['local-cli', 'single-container', 'full-stack'];

  useInput((input, key) => {
    if (key.upArrow) {
      setSelectedIndex(prev => prev > 0 ? prev - 1 : deploymentModes.length - 1);
    } else if (key.downArrow) {
      setSelectedIndex(prev => prev < deploymentModes.length - 1 ? prev + 1 : 0);
    } else if (key.return) {
      onSelect(deploymentModes[selectedIndex]);
    } else if (key.escape) {
      onBack();
    }
  });

  const renderModeOption = (mode: DeploymentMode, index: number) => {
    const modeInfo = SetupService.getDeploymentModeInfo(mode);
    const isSelected = index === selectedIndex;

    return (
      <Box
        key={mode}
        borderStyle={isSelected ? 'double' : 'single'}
        borderColor={isSelected ? theme.primary : theme.muted}
        paddingX={2}
        paddingY={1}
        marginY={0.5}
      >
        <Box flexDirection="row" width="100%">
          {/* Icon */}
          <Box width={8} justifyContent="center" alignItems="center">
            <Text color={isSelected ? theme.primary : theme.muted}>
              {modeInfo.icon}
            </Text>
          </Box>

          {/* Content */}
          <Box flexDirection="column" flexGrow={1}>
            <Box>
              <Text bold color={isSelected ? theme.primary : theme.foreground}>
                {modeInfo.name}
              </Text>
              {mode === 'full-stack' && (
                <Text color={theme.success} bold> (Recommended)</Text>
              )}
            </Box>

            <Box marginTop={0.5}>
              <Text color={theme.muted}>
                {modeInfo.description}
              </Text>
            </Box>

            <Box marginTop={0.5}>
              <Text color={theme.info}>Requirements: </Text>
              <Text color={theme.muted}>
                {modeInfo.requirements.join(', ')}
              </Text>
            </Box>
          </Box>
        </Box>
      </Box>
    );
  };

  return (
    <Box flexDirection="column" paddingX={2} paddingY={1}>
      {/* Title */}
      <Box marginBottom={2}>
        <Text bold color={theme.primary}>
          Choose Your Deployment Mode
        </Text>
      </Box>

      {/* Deployment modes */}
      <Box flexDirection="column" marginBottom={2}>
        {deploymentModes.map((mode, index) => renderModeOption(mode, index))}
      </Box>

      {/* Instructions */}
      <Box justifyContent="center" marginTop={1}>
        <Text color={theme.info}>
          Use <Text bold>↑↓</Text> to navigate, <Text bold color={theme.primary}>Enter</Text> to select, {' '}
          <Text bold color={theme.muted}>Esc</Text> to go back
        </Text>
      </Box>
    </Box>
  );
};