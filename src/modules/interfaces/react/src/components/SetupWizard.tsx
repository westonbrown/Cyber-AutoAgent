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
import { Header } from './Header.js';

interface SetupWizardProps {
  onComplete: (completionMessage?: string) => void;
  terminalWidth?: number;
  showHeader?: boolean;
}

export const SetupWizard: React.FC<SetupWizardProps> = React.memo(({
  onComplete,
  terminalWidth = 80,
  showHeader = true,
}) => {
  const { state, actions } = useSetupWizard();
  const { config, updateConfig, saveConfig } = useConfig();

  // Handle setup completion
  const handleSetupComplete = useCallback(async () => {
    if (state.selectedMode) {
      try {
        // Update configuration with selected deployment mode
        updateConfig({ 
          deploymentMode: state.selectedMode,
          hasSeenWelcome: true,
          isConfigured: true 
        });
        
        // Save configuration to disk
        await saveConfig();
        
        // Clear the deployment detector cache after setup
        const { DeploymentDetector } = await import('../services/DeploymentDetector.js');
        DeploymentDetector.getInstance().clearCache();
        
        // Provide completion message
        const modeDisplayName = 
          state.selectedMode === 'local-cli' ? 'Local CLI' :
          state.selectedMode === 'single-container' ? 'Agent Container' :
          'Enterprise Stack';
        
        // Clear the setup flag
        delete process.env.CYBER_SHOW_SETUP;
        
        onComplete(`${modeDisplayName} setup completed successfully`);
      } catch (error) {
        actions.setError('Failed to save configuration');
      }
    } else {
      onComplete();
    }
  }, [state.selectedMode, updateConfig, saveConfig, onComplete, actions.setError]);

  // Handle deployment mode selection and start setup
  const handleModeSelection = useCallback(async (mode: DeploymentMode) => {
    // Check if this deployment is already active
    const { DeploymentDetector } = await import('../services/DeploymentDetector.js');
    const detector = DeploymentDetector.getInstance();
    const detection = await detector.detectDeployments(config);
    const isAlreadyActive = detection.availableDeployments.some(
      d => d.mode === mode && d.isHealthy
    );
    
    if (isAlreadyActive) {
      // Skip setup for already active deployments
      actions.selectMode(mode);
      
      // Update configuration to use this deployment
      updateConfig({ 
        deploymentMode: mode,
        hasSeenWelcome: true,
        isConfigured: true 
      });
      await saveConfig();
      
      // Clear cache after config update
      detector.clearCache();
      
      // Complete immediately without progress screen
      const modeDisplayName = 
        mode === 'local-cli' ? 'Local CLI' :
        mode === 'single-container' ? 'Agent Container' :
        'Enterprise Stack';
      
      // Clear the setup flag
      delete process.env.CYBER_SHOW_SETUP;
      
      onComplete(`Switched to ${modeDisplayName} deployment`);
    } else {
      // Proceed with normal setup for non-active deployments
      actions.selectMode(mode);
      actions.nextStep(); // Move to progress screen
      
      // Pass the mode directly to avoid state timing issues
      await actions.startSetup(mode);
    }
  }, [actions, config, updateConfig, saveConfig, onComplete]);

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

  // Terminal clearing is handled by modalManager.refreshStatic() and parent components
  // Removed problematic useEffect with require() that caused race conditions

  return (
    <Box flexDirection="column" width="100%">
      {/* Render header only if showHeader is true */}
      {showHeader && (
        <Header 
          key="setup-header"
          version="0.1.3" 
          terminalWidth={terminalWidth}
          nightly={false}
        />
      )}
      
      {/* Current setup screen */}
      <Box key="setup-content">
        {renderCurrentScreen()}
      </Box>
    </Box>
  );
});