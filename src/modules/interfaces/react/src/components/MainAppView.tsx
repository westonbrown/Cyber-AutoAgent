/**
 * Main Application View
 * 
 * Extracts the main application UI logic from App.tsx.
 * Handles the primary interface when not in initialization flow.
 */

import React, { useCallback, useEffect, useState, useMemo, useRef } from 'react';
import { Box, Text, useInput, Static, useStdout } from 'ink';
import ansiEscapes from 'ansi-escapes';

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
  actions: any; // Application state actions
  currentTheme: any; // Theme configuration object
  operationHistoryEntries: OperationHistoryEntry[];
  assessmentFlowState: any; // Assessment flow state object
  staticKey: number;
  activeModal: ModalType;
  modalContext: any; // Modal context data
  isTerminalInteractive: boolean;
  onInput: (input: string) => void;
  onModalClose: () => void;
  addOperationHistoryEntry: (type: string, content: string) => void;
  onSafetyConfirm?: () => void;
  hideFooter?: boolean;
  hideInput?: boolean;
  hideHistory?: boolean;
  hideHeader?: boolean;
  customContent?: React.ReactNode;
  applicationConfig?: any; // Application configuration
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

  // Defer mounting the stream until after header is rendered on stream start
  const { stdout } = useStdout();
  const [deferStreamMount, setDeferStreamMount] = useState(false);
  const prevShowStreamRef = useRef<boolean>(false);
  const [hasStreamBegun, setHasStreamBegun] = useState(false);

  useEffect(() => {
    const prev = prevShowStreamRef.current;
    if (!prev && showOperationStream) {
      // Rising edge: operation stream just started
      try { stdout.write(ansiEscapes.clearTerminal); } catch {}
      // Defer stream mount to next tick so header paints first
      setDeferStreamMount(true);
      // Allow React to render header this tick, then enable stream
      setTimeout(() => setDeferStreamMount(false), 0);
      // A new stream is starting; allow header for this run
      setHasAnyOperationEnded(false);
    }
    prevShowStreamRef.current = showOperationStream;
  }, [showOperationStream, stdout]);

  // Reset flag when operation changes
  useEffect(() => {
    setHasStreamBegun(false);
  }, [appState.activeOperation?.id]);

  const hasStreamBegunRef = useRef(false);
  const handleStreamEvent = useCallback((event: any) => {
    if (hasStreamBegunRef.current) return;
    const eventType = event?.type;
    // Mark as begun on first meaningful content
    if (eventType === 'reasoning' || eventType === 'model_stream_delta' || eventType === 'content_block_delta' || eventType === 'output' || eventType === 'command' || eventType === 'tool_start' || eventType === 'tool_invocation_start') {
      hasStreamBegunRef.current = true;
      setHasStreamBegun(true);
    }
  }, []);

  // Once any operation completes or is stopped (ESC), suppress showing the header again
  const [hasAnyOperationEnded, setHasAnyOperationEnded] = useState(false);
  const handleLifecycleEvent = useCallback((event: any) => {
    const type = event?.type;
    if (type === 'operation_complete' || type === 'stopped' || type === 'complete') {
      setHasAnyOperationEnded(true);
    }
  }, []);

  // Also reset header suppression when a brand-new activeOperation appears in running state
  useEffect(() => {
    if (appState.activeOperation && appState.activeOperation.status === 'running') {
      setHasAnyOperationEnded(false);
    }
  }, [appState.activeOperation?.id, appState.activeOperation?.status]);

  // Minimal cosmetic autoscroll toggle (UI only for now)
  const [isAutoScrollEnabled, setIsAutoScrollEnabled] = useState(true);
  useInput((input, key) => {
    if (activeModal !== ModalType.NONE) return;
    if ((input?.toLowerCase?.() === 'a') && !key.ctrl && !key.meta) {
      setIsAutoScrollEnabled(prev => !prev);
    }
  });

  return (
    <Box flexDirection="column" width="100%" height="100%">
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

      {/* HEADER: Render normally. Duplication is prevented by state logic, Static causes layout issues. */}
      {!hideHeader && activeModal === ModalType.NONE && !hasAnyOperationEnded && (
        <Box>
          <Header 
            key={`app-header-${staticKey}`}
            version="0.1.3" 
            terminalWidth={appState.terminalDisplayWidth}
            nightly={false}
          />
        </Box>
      )}

      {/* MAIN CONTENT AREA: A single container for history and stream to enforce render order */}
      <Box flexDirection="column" flexGrow={1}>
        {/* HISTORY LOGS: Render before the stream */}
        {!hideHistory && activeModal === ModalType.NONE && (
          <Box key={staticKey} flexDirection="column">
            {filteredOperationHistory.map((entry) => {
              // Handle divider entries
              if (entry.type === 'divider') {
                return (
                  <Box key={entry.id} marginY={0.5}>
                    <Text color={currentTheme.muted}>{entry.content || '━'.repeat(80)}</Text>
                  </Box>
                );
              }
              
              // Handle other entry types
              const entryColor = 
                entry.type === 'error' ? currentTheme.error :
                entry.type === 'success' ? currentTheme.success :
                currentTheme.foreground;
              
              return (
                <Box key={entry.id} marginBottom={0.5}>
                  <Text color={currentTheme.muted}>[{entry.timestamp.toLocaleTimeString()}] </Text>
                  <Text color={entryColor}>{entry.content}</Text>
                </Box>
              );
            })}
          </Box>
        )}

        {/* STREAM DISPLAY: Renders after history, within the same content block */}
        {showOperationStream && (
          customContent ? (
            <Box flexDirection="column" marginTop={1}>{customContent}</Box>
          ) : (!deferStreamMount) && (
            <UnconstrainedTerminal
              executionService={appState.executionService}
              sessionId={appState.activeOperation!.id}
              terminalWidth={appState.terminalDisplayWidth}
              collapsed={false}
              onEvent={(e:any) => { handleStreamEvent(e); handleLifecycleEvent(e); }}
              onMetricsUpdate={(metrics) => actions.updateMetrics?.(metrics)}
            />
          )
        )}
      </Box>

      {/* INPUT & FOOTER AREA: Static at the bottom */}
      <Box flexDirection="column">
        {!hideInput && activeModal === ModalType.NONE && (!showOperationStream || appState.userHandoffActive) && (
          <UnifiedInputPrompt
            flowState={assessmentFlowState}
            onInput={onInput}
            disabled={!isTerminalInteractive && !appState.userHandoffActive}
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