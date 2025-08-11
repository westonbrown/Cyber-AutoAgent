/**
 * Initialization Wrapper Component
 * 
 * Handles the initialization flow display logic extracted from App.tsx.
 * Shows setup wizard when needed, otherwise renders main application.
 */

import React from 'react';
import { Box } from 'ink';

// Components
import { SetupWizard } from './SetupWizard.js';
import { MainAppView } from './MainAppView.js';

// Types
import { ApplicationState } from '../hooks/useApplicationState.js';

interface InitializationWrapperProps {
  appState: ApplicationState;
  applicationConfig: any;
  onInitializationComplete: (completionMessage?: string) => void;
  onConfigOpen: () => void;
  mainAppViewProps: any; // Props to pass through to MainAppView
}

export const InitializationWrapper: React.FC<InitializationWrapperProps> = ({
  appState,
  applicationConfig,
  onInitializationComplete,
  onConfigOpen,
  mainAppViewProps
}) => {

  // Config loading state
  if (!appState.isConfigLoaded) {
    return <Box />; // Empty box while loading config
  }

  // When initialization flow is active, show setup wizard.
  if (appState.isInitializationFlowActive && !appState.hasUserDismissedInit) {
    return (
      <SetupWizard 
        terminalWidth={appState.terminalDisplayWidth}
        onComplete={(completionMessage?: string) => {
          // Call the completion handler first to dismiss initialization
          onInitializationComplete(completionMessage);
          
          // Only show config editor if model configuration is incomplete
          if (!applicationConfig.modelId || !applicationConfig.modelProvider) {
            setTimeout(() => {
              onConfigOpen();
            }, 100);
          }
        }}
      />
    );
  }

  // Render main application (force remount on staticKey to avoid stale tree post-clear)
  return <MainAppView key={`main-view-${appState.staticKey}`} {...mainAppViewProps} />;
};