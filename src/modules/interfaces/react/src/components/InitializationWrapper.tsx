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

  // Main application layout with setup overlay
  // When initialization flow is active, show main view with setup wizard overlay
  if (appState.isInitializationFlowActive && !appState.hasUserDismissedInit) {
    // Show main view with header but hide footer and input, then show setup wizard below
    
    return (
      <Box flexDirection="column" width="100%">
        {/* Render main app view but with setup mode flag to hide footer */}
        <MainAppView 
          {...mainAppViewProps}
          hideFooter={true}
          hideInput={true}
        />
        
        {/* Setup Wizard appears below the main view */}
        <Box marginTop={1}>
          <SetupWizard 
            terminalWidth={appState.terminalDisplayWidth}
            onComplete={(completionMessage?: string) => {
              // Show config editor after initialization if not configured  
              if (!applicationConfig.isConfigured) {
                // Open config without clearing
                setTimeout(() => {
                  onConfigOpen();
                }, 500);
              }
              
              // Call the completion handler (this will add the message to operation history)
              onInitializationComplete(completionMessage);
            }}
          />
        </Box>
      </Box>
    );
  }

  // Render main application
  return <MainAppView {...mainAppViewProps} />;
};