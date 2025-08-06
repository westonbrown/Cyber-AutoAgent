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

// Services
import { DirectDockerService } from '../services/DirectDockerService.js';

// Types
import { ApplicationState } from '../hooks/useApplicationState.js';
import { OperationHistoryEntry } from '../hooks/useOperationManager.js';
import { ModalType } from '../hooks/useModalManager.js';

interface MainAppViewProps {
  appState: ApplicationState;
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
  dockerService?: DirectDockerService;
}

export const MainAppView: React.FC<MainAppViewProps> = ({
  appState,
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
  dockerService
}) => {
  
  // Filter operation history for display
  const filteredOperationHistory = operationHistoryEntries.filter(entry => 
    entry.type !== 'command' || !entry.content.startsWith('/')
  );
  
  // Check if we should show the operation stream
  const showOperationStream = appState.activeOperation && dockerService;

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
      {/* Main Application Interface */}
      {showOperationStream ? (
        // Show operation stream when active
        <Box flexDirection="column" width="100%">
          <Static key={`header-${staticKey}`} items={['header']}>
            {(item: string) => (
              <Box key="header" flexDirection="column" width="100%">
                <Header 
                  version="0.1.3" 
                  terminalWidth={appState.terminalDisplayWidth}
                  nightly={false}
                />
                
                {/* Operation Status Display */}
                {appState.activeOperation && (
                  <OperationStatusDisplay 
                    flowState={assessmentFlowState}
                    currentOperation={{
                      id: appState.activeOperation.id,
                      currentStep: 1,
                      totalSteps: 1,
                      description: appState.activeOperation.description || 'Running assessment',
                      startTime: new Date(),
                      status: appState.activeOperation.status || 'running'
                    }}
                    showFlowProgress={false}  // Hide flow progress when operation is running
                  />
                )}
              </Box>
            )}
          </Static>
          
          {/* Operation Stream Display */}
          <Box flexDirection="column" flexGrow={1}>
            <UnconstrainedTerminal
              dockerService={dockerService}
              sessionId={appState.activeOperation.id}
              terminalWidth={appState.terminalDisplayWidth}
              collapsed={false}
              onEvent={(event) => {
                // Events are already being handled by useOperationManager
              }}
              onMetricsUpdate={(metrics) => {
                // Metrics updates if needed
              }}
            />
          </Box>
        </Box>
      ) : (
        // Show normal interface when no operation
        <Static
          key={staticKey}
          items={[
            ...(appState.hasCompletedOperation ? [] : ['header']), // Hide header if operation completed
            ...filteredOperationHistory.map(item => `history_${item.id}`)
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
                  {appState.activeOperation && (
                    <OperationStatusDisplay 
                      flowState={assessmentFlowState}
                      currentOperation={{
                        id: appState.activeOperation.id,
                        currentStep: 1,
                        totalSteps: 1,
                        description: appState.activeOperation.description || 'Running assessment',
                        startTime: new Date(),
                        status: appState.activeOperation.status || 'running'
                      }}
                      showFlowProgress={false}  // Hide flow progress when operation is running
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
      )}

      {/* Input Interface - hide during active operations unless user handoff is active */}
      {(!appState.activeOperation || appState.userHandoffActive) && (
        <UnifiedInputPrompt
          flowState={assessmentFlowState}
          onInput={onInput}
          disabled={!isTerminalInteractive}
          userHandoffActive={appState.userHandoffActive}
        />
      )}
      
      {/* Footer */}
      <Footer 
        model=""
        contextRemaining={appState.contextUsage || 100}
        directory={process.cwd()}
        operationStatus={appState.activeOperation ? {
          step: 1,
          totalSteps: 1,
          description: appState.activeOperation.description || 'Running assessment',
          isRunning: appState.activeOperation.status === 'running'
        } : undefined}
      />
      
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