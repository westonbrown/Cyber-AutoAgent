/**
 * Module Selector Component
 * Interactive module selection UI for Cyber-AutoAgent
 * Provides arrow key navigation and descriptions for each security module
 */

import React, { useState, useEffect } from 'react';
import { Box, Text, useInput } from 'ink';
import { useModule } from '../contexts/ModuleContext.js';
import { themeManager } from '../themes/theme-manager.js';

interface ModuleSelectorProps {
  onClose: () => void;
  onSelect?: (module: string) => void;
}

interface ModuleOption {
  id: string;
  name: string;
  description: string;
  isCurrent: boolean;
}

export const ModuleSelector: React.FC<ModuleSelectorProps> = React.memo(({ onClose, onSelect }) => {
  const { availableModules, currentModule, switchModule } = useModule();
  const theme = themeManager.getCurrentTheme();
  const [selectedIndex, setSelectedIndex] = useState(0);
  
  // Build module options list - show raw module names (memoized for performance)
  const moduleOptions: ModuleOption[] = React.useMemo(() => 
    Object.entries(availableModules).map(([id, info]) => ({
      id,
      name: id,  // Show raw module name
      description: info.description,
      isCurrent: id === currentModule
    })), [availableModules, currentModule]
  );
  
  // Set initial selection to current module
  useEffect(() => {
    const currentIndex = moduleOptions.findIndex(m => m.isCurrent);
    if (currentIndex >= 0) {
      setSelectedIndex(currentIndex);
    }
  }, []);
  
  // Handle keyboard input with stable callbacks
  const handleKeyInput = React.useCallback((input: string, key: any) => {
    if (key.escape) {
      onClose();
      return;
    }
    
    if (key.upArrow) {
      setSelectedIndex(prev => Math.max(0, prev - 1));
      return;
    }
    
    if (key.downArrow) {
      setSelectedIndex(prev => Math.min(moduleOptions.length - 1, prev + 1));
      return;
    }
    
    if (key.return) {
      const selected = moduleOptions[selectedIndex];
      if (selected && selected.id !== currentModule) {
        switchModule(selected.id).then(() => {
          if (onSelect) {
            onSelect(selected.id);
          }
          onClose();
        });
      } else {
        onClose();
      }
      return;
    }
  }, [moduleOptions, selectedIndex, currentModule, switchModule, onSelect, onClose]);
  
  useInput(handleKeyInput);
  
  return (
    <Box
      flexDirection="column"
      borderStyle="round"
      borderColor={theme.primary}
      paddingX={3}
      paddingY={2}
      width="60%"
    >
      {/* Header */}
      <Box marginBottom={2}>
        <Text color={theme.primary} bold>
          Select Security Module
        </Text>
      </Box>
      
      {/* Module List */}
      <Box flexDirection="column">
        {moduleOptions.map((module, index) => {
          const isSelected = index === selectedIndex;
          const isCurrent = module.isCurrent;
          
          return (
            <Box key={module.id} flexDirection="column" marginBottom={1}>
              {/* Module name line */}
              <Box width="100%" marginBottom={0}>
                <Text
                  color={isSelected ? theme.accent : theme.foreground}
                  bold={isSelected}
                >
                  {isSelected ? '▸ ' : '  '}
                  {module.name}
                  {isCurrent ? ' (current)' : ''}
                </Text>
              </Box>
              
              {/* Description line with proper indentation */}
              <Box marginLeft={4} width="100%">
                <Text color={theme.muted}>
                  {module.description}
                </Text>
              </Box>
            </Box>
          );
        })}
      </Box>
      
      {/* Footer Instructions */}
      <Box marginTop={2} borderStyle="single" borderColor={theme.muted} paddingX={1}>
        <Text color={theme.muted}>
          ↑↓ Navigate • Enter to select • Esc to cancel
        </Text>
      </Box>
    </Box>
  );
});