/**
 * Initialization Wrapper Component
 * 
 * Handles the initialization flow display logic extracted from App.tsx.
 * Shows setup wizard when needed, otherwise renders main application.
 */

import React from 'react';
import { Box, Text } from 'ink';

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

  // Config loading state - show a loading indicator to prevent black screen
  if (!appState.isConfigLoaded) {
    return (
      <Box flexDirection="column" paddingY={1} flexGrow={1}>
        <Box justifyContent="center">
          <Text color="cyan">Loading configuration...</Text>
        </Box>
      </Box>
    );
  }

  // When initialization flow is active, show setup wizard.
  if (appState.isInitializationFlowActive && !appState.hasUserDismissedInit) {
    return (
      <SetupWizard 
        terminalWidth={appState.terminalDisplayWidth}
        onComplete={(completionMessage?: string) => {
          // Call the completion handler first to dismiss initialization
          onInitializationComplete(completionMessage);
          
          // If the user explicitly skipped the setup (e.g., pressed Esc on the welcome screen),
          // return to the main screen without auto-opening the config editor.
          const skipped = (completionMessage || '').toLowerCase().includes('skip');
          
          // Only show config editor if model configuration is incomplete AND the flow was not skipped
          if (!skipped && (!applicationConfig.modelId || !applicationConfig.modelProvider)) {
            setTimeout(() => {
              onConfigOpen();
            }, 100);
          }
        }}
      />
    );
  }

  // Render main application (force remount on staticKey to avoid stale tree post-clear)
  // Add a minimum height to prevent collapse during transitions
  return (
    <Box minHeight={10} flexGrow={1}>
      <MainAppView key={`main-view-${appState.staticKey}`} {...mainAppViewProps} />
    </Box>
  );
};