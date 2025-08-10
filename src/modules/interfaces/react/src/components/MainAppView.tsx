/**
 * Main Application View
 * 
 * Extracts the main application UI logic from App.tsx.
 * Handles the primary interface when not in initialization flow.
 */

import React, { useCallback, useEffect } from 'react';
import { Box, Text, Static } from 'ink';

// Components
import { Header } from './Header.js';
import { Footer } from './Footer.js';
import { OperationStatusDisplay } from './OperationStatusDisplay.js';
import { UnifiedInputPrompt } from './UnifiedInputPrompt.js';
import { UnconstrainedTerminal } from './UnconstrainedTerminal.js';
import { ModalRegistry } from './ModalRegistry.js';

// Types
import { ApplicationState } from '../hooks/useApplicationState.js';
import { OperationHistoryEntry } from '../hooks/useOperationManager.js';
import { ModalType } from '../hooks/useModalManager.js';

interface MainAppViewProps {
  appState: ApplicationState;
  actions: any;
  currentTheme: any;
  operationHistoryEntries: OperationHistoryEntry[];
  assessmentFlowState: any;
  staticKey: number;
  activeModal: ModalType;
  modalContext: any;
  isTerminalInteractive: boolean;
  onInput: (input: string) => void;
  onModalClose: () => void;
  addOperationHistoryEntry: (type: string, content: string) => void;
  onSafetyConfirm?: () => void;
  hideFooter?: boolean;
  hideInput?: boolean;
  hideHistory?: boolean;
  hideHeader?: boolean; // Add this to hide header when showing setup
  customContent?: React.ReactNode;
  applicationConfig?: any; // Add config to get modelProvider
}

export const MainAppView: React.FC<MainAppViewProps> = ({
  appState,
  actions,
  currentTheme,
  operationHistoryEntries,
  assessmentFlowState,
  staticKey,
  activeModal,
  modalContext,
  isTerminalInteractive,
  onInput,
  onModalClose,
  addOperationHistoryEntry,
  onSafetyConfirm,
  hideFooter = false,
  hideInput = false,
  hideHistory = false,
  hideHeader = false,
  customContent,
  applicationConfig
}) => {
  // Filter operation history for display
  const filteredOperationHistory = operationHistoryEntries.filter(entry => 
    entry.type !== 'command' || !entry.content.startsWith('/')
  );
  
  // Check if we should show the operation stream
  const showOperationStream = !!(appState.activeOperation && appState.executionService);

  // Handle terminal size changes
  useEffect(() => {
    const handleResize = () => {
      if (process.stdout.columns && process.stdout.rows) {
        // Update terminal dimensions if needed
      }
    };
    
    process.stdout.on('resize', handleResize);
    return () => {
      process.stdout.off('resize', handleResize);
    };
  }, []);

  return (
    <>
      {/* Main Application Interface - Single unified view */}
      <Static
        key={staticKey}
        items={[
          // Hide header whenever any modal is open to avoid duplicate ASCII banner under modals (e.g., Safety Warning)
          ...(hideHeader || appState.hasCompletedOperation || activeModal !== ModalType.NONE ? [] : ['header']),
          // Suppress history when a modal is open to keep modal screens clean
          ...(!showOperationStream && !hideHistory && activeModal === ModalType.NONE ? filteredOperationHistory.map(item => `history_${item.id}`) : [])
        ]}
      >
        {(item: string) => {
          if (item === 'header') {
            return (
              <Box key="header" flexDirection="column" width="100%">
                <Header 
                  version="0.1.3" 
                  terminalWidth={appState.terminalDisplayWidth}
                  nightly={false}
                />
                
                {/* Operation Status Display */}
                {assessmentFlowState.step !== 'idle' && (
                  <OperationStatusDisplay 
                    flowState={assessmentFlowState}
                    currentOperation={appState.activeOperation ? {
                      id: appState.activeOperation.id,
                      currentStep: 1,
                      totalSteps: 1,
                      description: appState.activeOperation.description || 'Running assessment',
                      startTime: new Date(),
                      status: appState.activeOperation.status || 'running'
                    } : undefined}
                    showFlowProgress={false}  // Flow progress disabled
                  />
                )}
              </Box>
            );
          }
          
          // Render operation history entries
          if (item.startsWith('history_')) {
            const entryId = item.replace('history_', '');
            const entry = filteredOperationHistory.find(e => e.id === entryId);
            
            if (!entry) return <Box key={item} />;
            
            return (
              <Box key={item} flexDirection="column">
                <Box>
                  <Text color={currentTheme.muted}>
                    [{entry.timestamp.toLocaleTimeString()}]{' '}
                  </Text>
                  <Text color={entry.type === 'error' ? currentTheme.error : currentTheme.foreground}>
                    {entry.content}
                  </Text>
                </Box>
              </Box>
            );
          }
          
          return <Box key={item} />;
        }}
      </Static>
      
      {/* Custom Content - renders instead of operation stream if provided */}
      {customContent && (
        <Box flexDirection="column" marginTop={1}>
          {customContent}
        </Box>
      )}
      
      {/* Operation Stream Display - Shows underneath the static content (only if no custom content) */}
      {!customContent && showOperationStream && (
        <Box flexDirection="column" flexGrow={1} marginBottom={2}>
          <UnconstrainedTerminal
            executionService={appState.executionService}
            sessionId={appState.activeOperation!.id}
            terminalWidth={appState.terminalDisplayWidth}
            collapsed={false}
            onEvent={(event) => {
              // Events are already being handled by useOperationManager
            }}
            onMetricsUpdate={(metrics) => {
              // Update the app state with real-time metrics from the stream
              if (actions && actions.updateMetrics) {
                actions.updateMetrics(metrics);
              }
            }}
          />
        </Box>
      )}

      {/* Input Interface - hide during active operations unless user handoff is active */}
      {/* Also hide during initialization flow (setup wizard) or when hideInput is true */}
      {!hideInput && (!appState.activeOperation || appState.userHandoffActive) && 
       !appState.isInitializationFlowActive && (
        <Box marginTop={showOperationStream ? 2 : 1} marginBottom={1}>
          <UnifiedInputPrompt
            flowState={assessmentFlowState}
            onInput={onInput}
            disabled={!isTerminalInteractive}
            userHandoffActive={appState.userHandoffActive}
          />
        </Box>
      )}
      
      {/* Footer - hide when hideFooter is true or specific modals are open */}
      {!hideFooter && 
       activeModal !== ModalType.CONFIG && 
       activeModal !== ModalType.MODULE_SELECTOR && 
       activeModal !== ModalType.DOCUMENTATION &&
       activeModal !== ModalType.SAFETY_WARNING && (
        <Box marginTop={1}>
          <Footer 
            model={appState.activeOperation?.model || ""}
            contextRemaining={appState.contextUsage || 100}
            directory={process.cwd()}
            operationStatus={appState.activeOperation ? {
              step: 1,
              totalSteps: 1,
              description: appState.activeOperation.description || 'Running assessment',
              isRunning: appState.activeOperation.status === 'running'
            } : undefined}
            operationMetrics={appState.operationMetrics}
            connectionStatus={appState.activeOperation ? 'connected' : (appState.isDockerServiceAvailable ? 'connected' : 'offline')}
            modelProvider={applicationConfig?.modelProvider || 'bedrock'}
          />
        </Box>
      )}
      
      {/* Modal System */}
      <ModalRegistry
        activeModal={activeModal}
        modalContext={modalContext}
        onClose={onModalClose}
        terminalWidth={appState.terminalDisplayWidth}
        onSafetyConfirm={onSafetyConfirm}
      />
    </>
  );
};