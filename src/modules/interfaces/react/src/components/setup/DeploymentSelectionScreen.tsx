/**
 * DeploymentSelectionScreen Component
 * 
 * Clean deployment mode selection using production patterns from gemini-cli
 */

import React, { useState, useEffect } from 'react';
import { Box, Text, useInput } from 'ink';
import Spinner from 'ink-spinner';
import { themeManager } from '../../themes/theme-manager.js';
import { DeploymentMode, SetupService } from '../../services/SetupService.js';
import { DeploymentDetector, DeploymentStatus } from '../../services/DeploymentDetector.js';
import { RadioSelect, RadioSelectItem } from '../shared/RadioSelect.js';
import { useConfig } from '../../contexts/ConfigContext.js';

interface DeploymentSelectionScreenProps {
  onSelect: (mode: DeploymentMode) => void;
  onBack: () => Promise<void> | void;
}

export const DeploymentSelectionScreen: React.FC<DeploymentSelectionScreenProps> = ({
  onSelect,
  onBack,
}) => {
  const theme = themeManager.getCurrentTheme();
  const { config } = useConfig();
  const [activeDeployments, setActiveDeployments] = useState<DeploymentStatus[]>([]);
  const [isDetecting, setIsDetecting] = useState(true);

  useEffect(() => {
    const detectActive = async () => {
      setIsDetecting(true);
      try {
        const detector = DeploymentDetector.getInstance();
        const result = await detector.detectDeployments(config);
        setActiveDeployments(result.availableDeployments.filter(d => d.isHealthy));
      } catch (error) {
        console.error('Failed to detect deployments:', error);
      } finally {
        setIsDetecting(false);
      }
    };
    
    detectActive();
  }, [config]);

  useInput((_, key) => {
    if (key.escape) {
      onBack();
    }
  });

  // Build radio select items with improved layout
  const deploymentItems: RadioSelectItem<DeploymentMode>[] = [
    'local-cli',
    'single-container', 
    'full-stack'
  ].map((mode) => {
    const modeInfo = SetupService.getDeploymentModeInfo(mode as DeploymentMode);
    const isActive = activeDeployments.some(d => d.mode === mode && d.isHealthy);
    
    let badge: string | undefined;
    if (isActive) {
      badge = '✓ Active';
    } else if (mode === 'full-stack') {
      badge = '★ Recommended';
    }

    // Multi-line description with icon and bullet list of requirements
    const fullDescription = [
      modeInfo.icon.trim(),
      `${modeInfo.description}`,
      `Requirements:`,
      ...modeInfo.requirements.map(r => `• ${r}`)
    ].join('\n');

    return {
      label: `${modeInfo.name}`,
      value: mode as DeploymentMode,
      description: fullDescription,
      disabled: false, // Allow switching to any mode, including active ones
      badge
    };
  });

  const handleSelect = (mode: DeploymentMode) => {
    // Always allow selection - the wizard will handle switching logic
    onSelect(mode);
  };

  return (
    <Box flexDirection="column" paddingX={2} paddingY={1}>
      {/* Header - compact */}
      <Box marginBottom={1}>
        <Text color={theme.muted}>
          Select deployment mode
        </Text>
        <Text>  </Text>
        {isDetecting && (
          <Box>
            <Spinner type="dots" />
            <Text color={theme.muted}> Detecting</Text>
          </Box>
        )}
      </Box>

      {/* Active deployments notification */}
      {!isDetecting && activeDeployments.length > 0 && (
        <Box marginBottom={1}>
          <Text color={theme.info}>
            Active: {activeDeployments.map(d => 
              SetupService.getDeploymentModeInfo(d.mode).name
            ).join(', ')}
          </Text>
          <Text>  </Text>
          <Text color={theme.muted}>
            Select active to reconfigure, or choose a different mode to switch
          </Text>
        </Box>
      )}

      {/* Radio selection */}
      <Box marginBottom={1}>
        <RadioSelect
          items={deploymentItems}
          initialIndex={2} // Default to full-stack (recommended)
          onSelect={handleSelect}
          isFocused={!isDetecting}
          showNumbers={true}
        />
      </Box>

      {/* Instructions */}
      <Box marginTop={0}>
        <Text color={theme.muted}>
          <Text bold>↑↓</Text> navigate • <Text bold>1-3</Text> select • <Text bold color={theme.primary}>Enter</Text> confirm • <Text bold>Esc</Text> back
        </Text>
      </Box>
    </Box>
  );
};