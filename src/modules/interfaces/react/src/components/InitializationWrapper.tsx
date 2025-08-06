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

  // Main application layout
  // When initialization flow is active, render ONLY that - nothing else
  if (appState.isInitializationFlowActive && !appState.hasUserDismissedInit) {
    // Only perform terminal clearing once when setup wizard is first activated
    // This prevents flickering during React re-renders
    if (!hasInitialClear.current) {
      // Use clearScreen for full terminal reset including scrollback buffer
      stdout.write(ansiEscapes.clearScreen);
      hasInitialClear.current = true;
    }
    // No clearing on subsequent renders to prevent flicker
    
    return (
      <Box flexDirection="column" width="100%">
        {/* Preserve the Header component to keep the logo and branding */}
        <Header 
          version="0.1.3" 
          terminalWidth={appState.terminalDisplayWidth}
          nightly={false}
        />
        
        {/* Setup Wizard - Full Screen */}
        <SetupWizard 
          terminalWidth={appState.terminalDisplayWidth}
          onComplete={(completionMessage?: string) => {
            // Don't add to operation history here - let the main completion handler do it
            // This prevents duplicate messages
            
            // Refresh the static content to show main interface
            refreshStatic();
            
            // Show config editor after initialization if not configured
            if (!applicationConfig.isConfigured) {
              // Clear terminal and open config for clean transition
              setTimeout(() => {
                stdout.write(ansiEscapes.clearTerminal);
                onConfigOpen();
              }, 500);
            }
            
            // Call the completion handler (this will add the message to operation history)
            onInitializationComplete(completionMessage);
          }}
        />
      </Box>
    );
  }

  // Render main application
  return <MainAppView {...mainAppViewProps} />;
};