/**
 * SetupWizard Component
 * 
 * Main setup wizard orchestrator. Manages the flow between welcome, deployment selection,
 * and progress screens. Replaces the complex InitializationFlow with a simplified architecture.
 */

import React, { useCallback, useEffect } from 'react';
import { Box } from 'ink';
import { useSetupWizard } from '../hooks/useSetupWizard.js';
import { useConfig } from '../contexts/ConfigContext.js';
import { WelcomeScreen } from './setup/WelcomeScreen.js';
import { DeploymentSelectionScreen } from './setup/DeploymentSelectionScreen.js';
import { ProgressScreen } from './setup/ProgressScreen.js';
import { DeploymentMode } from '../services/SetupService.js';

interface SetupWizardProps {
  onComplete: (completionMessage?: string) => void;
  terminalWidth?: number;
}

export const SetupWizard: React.FC<SetupWizardProps> = ({
  onComplete,
  terminalWidth = 80,
}) => {
  const { state, actions } = useSetupWizard();
  const { updateConfig, saveConfig } = useConfig();

  // Handle setup completion
  const handleSetupComplete = useCallback(async () => {
    if (state.selectedMode) {
      try {
        // Update configuration with selected deployment mode
        await updateConfig({ 
          deploymentMode: state.selectedMode,
          hasSeenWelcome: true,
          isConfigured: true 
        });
        
        // Save configuration to disk
        await saveConfig();
        
        // Provide completion message
        const modeDisplayName = 
          state.selectedMode === 'local-cli' ? 'Local CLI' :
          state.selectedMode === 'single-container' ? 'Agent Container' :
          'Enterprise Stack';
        
        onComplete(`✓ ${modeDisplayName} setup completed successfully!`);
      } catch (error) {
        actions.setError('Failed to save configuration');
      }
    } else {
      onComplete();
    }
  }, [state.selectedMode, updateConfig, saveConfig, onComplete, actions.setError]);

  // Handle deployment mode selection and start setup
  const handleModeSelection = useCallback(async (mode: DeploymentMode) => {
    actions.selectMode(mode);
    actions.nextStep(); // Move to progress screen
    
    // Pass the mode directly to avoid state timing issues
    await actions.startSetup(mode);
  }, [actions]);

  // Handle setup retry
  const handleRetry = useCallback(async () => {
    actions.resetError();
    await actions.startSetup();
  }, [actions.resetError, actions.startSetup]);

  // Auto-complete when setup finishes successfully
  useEffect(() => {
    if (state.isComplete && !state.error) {
      // Small delay to show completion state
      const timer = setTimeout(() => {
        handleSetupComplete();
      }, 1500);
      
      return () => clearTimeout(timer);
    }
  }, [state.isComplete, state.error, handleSetupComplete]);

  const renderCurrentScreen = () => {
    switch (state.currentStep) {
      case 'welcome':
        return (
          <WelcomeScreen
            onContinue={actions.nextStep}
            onSkip={() => onComplete('Setup skipped')}
          />
        );

      case 'deployment':
        return (
          <DeploymentSelectionScreen
            onSelect={handleModeSelection}
            onBack={actions.previousStep}
          />
        );

      case 'progress':
        return (
          <ProgressScreen
            deploymentMode={state.selectedMode!}
            progress={state.progress}
            isComplete={state.isComplete}
            isLoading={state.isLoading}
            error={state.error}
            onComplete={handleSetupComplete}
            onRetry={handleRetry}
            onBack={actions.previousStep}
          />
        );

      default:
        return null;
    }
  };

  return (
    <Box flexDirection="column" width="100%">
      {renderCurrentScreen()}
    </Box>
  );
};