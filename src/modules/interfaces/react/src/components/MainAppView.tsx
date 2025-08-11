/**
 * Main Application View
 * 
 * Extracts the main application UI logic from App.tsx.
 * Handles the primary interface when not in initialization flow.
 */

import React, { useCallback, useEffect, useState, useMemo } from 'react';
import { Box, Text, useInput, Static } from 'ink';

// Components
import { Header } from './Header.js';
import { Footer } from './Footer.js';
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

  const [hasStreamBegun, setHasStreamBegun] = useState(false);

  // Reset flag when operation changes
  useEffect(() => {
    setHasStreamBegun(false);
  }, [appState.activeOperation?.id]);

  const handleStreamEvent = useCallback((evt: any) => {
    if (hasStreamBegun) return;
    const t = evt?.type;
    // Mark as begun on first meaningful content
    if (t === 'reasoning' || t === 'model_stream_delta' || t === 'content_block_delta' || t === 'output' || t === 'command' || t === 'tool_start' || t === 'tool_invocation_start') {
      setHasStreamBegun(true);
    }
  }, [hasStreamBegun]);

  // Minimal cosmetic autoscroll toggle (UI only for now)
  const [autoScroll, setAutoScroll] = useState(true);
  useInput((input, key) => {
    if (activeModal !== ModalType.NONE) return;
    if ((input?.toLowerCase?.() === 'a') && !key.ctrl && !key.meta) {
      setAutoScroll(prev => !prev);
    }
  });

  return (
    <Box flexDirection="column" width="100%">
      {/* MODAL LAYER: Renders on top of everything else */}
      {activeModal !== ModalType.NONE && (
        <ModalRegistry
          activeModal={activeModal}
          modalContext={modalContext}
          onClose={onModalClose}
          onSafetyConfirm={onSafetyConfirm}
          addOperationHistoryEntry={addOperationHistoryEntry}
          terminalWidth={appState.terminalDisplayWidth}
        />
      )}

      {/* HEADER: Render via Static so it always stays above Static logs */}
      {!hideHeader && !appState.hasCompletedOperation && activeModal === ModalType.NONE && (
        <Static items={[0]}>
          {() => (
            <Header 
              key={`app-header-${staticKey}`}
              version="0.1.3" 
              terminalWidth={appState.terminalDisplayWidth}
              nightly={false}
            />
          )}
        </Static>
      )}

      {/* MAIN CONTENT AREA: This container grows to fill available space. Remove overflow clamp to allow natural scrollback. */}
      <Box flexDirection="column" flexGrow={1}>
        {/* Wrapper for history and terminal to ensure proper layout flow */}
        <Box flexDirection="column" flexGrow={1}>
          {!showOperationStream && !hideHistory && activeModal === ModalType.NONE && (
            <Box key={staticKey} flexDirection="column">
              {filteredOperationHistory.map((entry) => (
                <Box key={entry.id}>
                  <Text color={currentTheme.muted}>[{entry.timestamp.toLocaleTimeString()}] </Text>
                  <Text color={entry.type === 'error' ? currentTheme.error : currentTheme.foreground}>{entry.content}</Text>
                </Box>
              ))}
            </Box>
          )}

          {customContent ? (
            <Box flexDirection="column" marginTop={1}>{customContent}</Box>
          ) : showOperationStream && (
            <UnconstrainedTerminal
              executionService={appState.executionService}
              sessionId={appState.activeOperation!.id}
              terminalWidth={appState.terminalDisplayWidth}
              collapsed={false}
              onEvent={handleStreamEvent}
              onMetricsUpdate={(metrics) => actions.updateMetrics?.(metrics)}
            />
          )}
        </Box>
      </Box>

      {/* INPUT & FOOTER AREA: Static at the bottom */}
      <Box flexDirection="column">
        {!hideInput && activeModal === ModalType.NONE && !showOperationStream && (
          <UnifiedInputPrompt
            flowState={assessmentFlowState}
            onInput={onInput}
            disabled={!isTerminalInteractive}
            userHandoffActive={appState.userHandoffActive}
          />
        )}
        
        {/* Spacer above footer when streaming to preserve breathing room */}
        {showOperationStream && (
          <Box>
            <Text> </Text>
          </Box>
        )}

        {!hideFooter && activeModal === ModalType.NONE && (
          <Footer 
            model={appState.activeOperation?.model || ""}
            operationMetrics={appState.operationMetrics}
            connectionStatus={appState.isDockerServiceAvailable ? 'connected' : 'offline'}
            modelProvider={applicationConfig?.modelProvider || 'bedrock'}
            deploymentMode={applicationConfig?.deploymentMode}
            isOperationRunning={appState.activeOperation ? appState.activeOperation.status === 'running' : false}
            isInputPaused={appState.userHandoffActive}
            operationName={!hasStreamBegun && appState.activeOperation ? (appState.activeOperation.description || 'Running assessment') : undefined}
          />
        )}
      </Box>
    </Box>
  );
};