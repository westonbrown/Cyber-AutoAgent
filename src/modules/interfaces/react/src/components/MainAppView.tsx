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
import { Terminal } from './Terminal.js';
import { ModalRegistry } from './ModalRegistry.js';
import { HITLInterventionPanel } from './HITLInterventionPanel.js';
import { submitFeedback } from '../utils/hitlCommands.js';

// Types
import { ApplicationState, ActionType } from '../hooks/useApplicationState.js';
import { OperationHistoryEntry } from '../hooks/useOperationManager.js';
import { ModalType } from '../hooks/useModalManager.js';

interface MainAppViewProps {
  appState: ApplicationState;
  actions: any; // Application state actions
  dispatch?: any; // Application state dispatch function
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
  terminalCleanupRef?: React.MutableRefObject<(() => void) | null>;
}

export const MainAppView: React.FC<MainAppViewProps> = ({
  appState,
  actions,
  dispatch,
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
  terminalCleanupRef,
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
      // Do not clear the terminal here; it resets scrollback and scroll position,
      // causing the viewport to jump to the top and the footer to disappear briefly.
      // Instead, only defer the stream mount so the header paints first on this tick.
      setDeferStreamMount(true);
      setTimeout(() => setDeferStreamMount(false), 0);
      // A new stream is starting; allow header for this run
      setHasAnyOperationEnded(false);
    }

    if (prev && !showOperationStream) {
      // Falling edge: stream ended. Do NOT clear the terminal.
      // We keep scrollback so users can review the previous operation's output
      // while returning to the main screen. If duplicate headers are a concern,
      // we can address them by adjusting header rendering, not by clearing.
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

  // Memoize event and metrics handlers to prevent Terminal useEffect re-runs
  const handleEvent = useCallback((e: any) => {
    handleStreamEvent(e);
    handleLifecycleEvent(e);
  }, [handleStreamEvent, handleLifecycleEvent]);

  // Use ref to completely eliminate dependency on actions object
  const actionsRef = useRef(actions);
  useEffect(() => {
    actionsRef.current = actions;
  }, [actions]);

  const handleMetricsUpdate = useCallback((metrics: any) => {
    actionsRef.current.updateMetrics?.(metrics);
  }, []); // No dependencies - uses ref to prevent re-creation

  // Also reset header suppression when a brand-new activeOperation appears in running state
  useEffect(() => {
    if (appState.activeOperation && appState.activeOperation.status === 'running') {
      setHasAnyOperationEnded(false);
      
      // Pause health monitoring to prevent scroll jumps during operations
      import('../services/HealthMonitor.js').then(({ HealthMonitor }) => {
        HealthMonitor.getInstance().pauseMonitoring();
      });
    } else {
      // Resume health monitoring when operations end with immediate check
      import('../services/HealthMonitor.js').then(({ HealthMonitor }) => {
        const monitor = HealthMonitor.getInstance();
        monitor.resumeMonitoring();
        // Trigger immediate check to reduce delay
        monitor.checkHealth();
      });
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
    <Box flexDirection="column" flexGrow={1}>
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

      {/* HEADER: Use Static during streaming so it stays above stream output */}
      {!hideHeader && activeModal === ModalType.NONE && (
        showOperationStream ? (
          <Static items={[`app-header-${staticKey}`]}>
            {(item) => (
              <Box key={item}>
                <Header 
                  key={`app-header-${staticKey}`}
                  version="0.1.3" 
                  terminalWidth={appState.terminalDisplayWidth}
                  nightly={false}
                  exitNotice={Boolean((appState as any).exitNotice)}
                />
              </Box>
            )}
          </Static>
        ) : (
          <Box>
            <Header 
              key={`app-header-${staticKey}`}
              version="0.1.3" 
              terminalWidth={appState.terminalDisplayWidth}
              nightly={false}
              exitNotice={Boolean((appState as any).exitNotice)}
            />
          </Box>
        )
      )}

      {/* MAIN CONTENT AREA: A single container for history and stream to enforce render order */}
      <Box flexDirection="column" flexGrow={1}>
        {/* HISTORY LOGS: Render before the stream. Suppress during active stream */}
        {!hideHistory && activeModal === ModalType.NONE && !showOperationStream && (
          <Box key={staticKey} flexDirection="column">
            {(() => {
              const MAX_HISTORY_RENDERED = (() => {
                const env = Number(process.env.CYBER_MAX_HISTORY_RENDERED);
                if (Number.isFinite(env) && env > 50) return Math.floor(env);
                return 200;
              })();
              const start = Math.max(0, filteredOperationHistory.length - MAX_HISTORY_RENDERED);
              const historyToRender = filteredOperationHistory.slice(start);
              const omitted = start;
              return (
                <>
                  {omitted > 0 && (
                    <Box marginBottom={0.5}>
                      <Text dimColor>… {omitted} earlier log entries omitted</Text>
                    </Box>
                  )}
                  {historyToRender.map((entry) => {
                    if (entry.type === 'divider') {
                      return null;
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
                </>
              );
            })()}
          </Box>
        )}

        {/* STREAM DISPLAY: Renders after history, within the same content block */}
        {showOperationStream && (
          customContent ? (
            <Box flexDirection="column" marginTop={1}>{customContent}</Box>
          ) : (!deferStreamMount) && (
            <Terminal
              key={appState.activeOperation!.id}
              executionService={appState.executionService}
              sessionId={appState.activeOperation!.id}
              terminalWidth={appState.terminalDisplayWidth}
              collapsed={activeModal !== ModalType.NONE}
              onEvent={handleEvent}
              onMetricsUpdate={handleMetricsUpdate}
              animationsEnabled={isAutoScrollEnabled && activeModal === ModalType.NONE}
              cleanupRef={terminalCleanupRef}
              dispatch={dispatch}
              hitlEnabled={appState.hitlEnabled}
              hitlPendingTool={appState.hitlPendingTool}
              hitlInterpretation={appState.hitlInterpretation}
            />
          )
        )}
      </Box>

      {/* INPUT & FOOTER AREA: Static at the bottom */}
      <Box flexDirection="column">
        {/* HITL Intervention Panel - Pinned above footer */}
        {appState.hitlEnabled && activeModal === ModalType.NONE && (
          <HITLInterventionPanel
            toolName={appState.hitlPendingTool?.toolName || ''}
            toolId={appState.hitlPendingTool?.toolId || ''}
            parameters={appState.hitlPendingTool?.parameters || {}}
            reason={appState.hitlPendingTool?.reason}
            confidence={appState.hitlPendingTool?.confidence}
            timeoutSeconds={appState.hitlPendingTool?.timeoutSeconds}
            isActive={!!appState.hitlPendingTool}
            onSubmitFeedback={(feedbackType: string, content: string) => {
              if (appState.hitlPendingTool) {
                submitFeedback(feedbackType as any, content, appState.hitlPendingTool.toolId);
              }
            }}
          />
        )}

        {!hideInput && activeModal === ModalType.NONE &&
         !appState.hitlPendingTool &&
         (!showOperationStream || appState.userHandoffActive) && (
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
            modelProvider={applicationConfig?.modelProvider}
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