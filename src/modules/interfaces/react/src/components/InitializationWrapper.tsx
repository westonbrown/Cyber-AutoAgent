/**
 * Initialization Wrapper Component
 * 
 * Handles the initialization flow display logic extracted from App.tsx.
 * Shows setup wizard when needed, otherwise renders main application.
 */

import React, { useRef, useEffect } from 'react';
import { Box, useStdout } from 'ink';
import ansiEscapes from 'ansi-escapes';

// Components
import { Header } from './Header.js';
import { SetupWizard } from './SetupWizard.js';
import { MainAppView } from './MainAppView.js';

// Types
import { ApplicationState } from '../hooks/useApplicationState.js';

interface InitializationWrapperProps {
  appState: ApplicationState;
  applicationConfig: any;
  onInitializationComplete: (completionMessage?: string) => void;
  onConfigOpen: () => void;
  refreshStatic: () => void;
  mainAppViewProps: any; // Props to pass through to MainAppView
}

export const InitializationWrapper: React.FC<InitializationWrapperProps> = ({
  appState,
  applicationConfig,
  onInitializationComplete,
  onConfigOpen,
  refreshStatic,
  mainAppViewProps
}) => {
  const { stdout } = useStdout();
  const hasInitialRefresh = useRef(false);
  const hasInitialClear = useRef(false);

  // Reset clear flag when initialization flow is deactivated
  useEffect(() => {
    if (!appState.isInitializationFlowActive || appState.hasUserDismissedInit) {
      hasInitialClear.current = false;
    }
  }, [appState.isInitializationFlowActive, appState.hasUserDismissedInit]);

  // Config loading state
  if (!appState.isConfigLoaded) {
    return <Box />; // Empty box while loading config
  }

  // When initialization flow is active, show setup wizard without duplicate header
  if (appState.isInitializationFlowActive && !appState.hasUserDismissedInit) {
    // Render just the setup wizard content - no duplicate header
    return (
      <SetupWizard 
        terminalWidth={appState.terminalDisplayWidth}
        showHeader={true} // SetupWizard handles its own header
        onComplete={(completionMessage?: string) => {
          // Call the completion handler first to dismiss initialization
          onInitializationComplete(completionMessage);
          
          // Only show config editor if model configuration is incomplete
          if (!applicationConfig.modelId || !applicationConfig.modelProvider) {
            setTimeout(() => {
              console.log('Setup wizard completed, opening config editor for model configuration...');
              onConfigOpen();
            }, 100);
          }
        }}
      />
    );
  }

  // Render main application
  return <MainAppView {...mainAppViewProps} />;
};