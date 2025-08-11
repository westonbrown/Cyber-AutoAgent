/**
 * Cyber-AutoAgent React Application
 * 
 * Main entry point for the React-based CLI interface.
 * Manages application state, services, and UI rendering.
 */

import React, { useCallback, useEffect } from 'react';
import { useStdout, useApp } from 'ink';
import ansiEscapes from 'ansi-escapes';

// State Management
import { useApplicationState } from './hooks/useApplicationState.js';
import { useModalManager, ModalType } from './hooks/useModalManager.js';
import { useOperationManager } from './hooks/useOperationManager.js';
import { useKeyboardHandlers } from './hooks/useKeyboardHandlers.js';

// Core Services  
import { InputParser } from './services/InputParser.js';

// Context Providers
import { ConfigProvider, useConfig } from './contexts/ConfigContext.js';
import { ModuleProvider, useModule } from './contexts/ModuleContext.js';

// Command Handler
import { useCommandHandler } from './hooks/useCommandHandler.js';
import { useDeploymentDetection } from './hooks/useDeploymentDetection.js';
import { useAutoRun } from './hooks/useAutoRun.js';

// Components
import { InitializationWrapper } from './components/InitializationWrapper.js';
import { ErrorBoundary } from './components/ErrorBoundary.js';

// Theme System
import { themeManager } from './themes/theme-manager.js';

/**
 * Main Application Component Properties
 */
interface AppProps {
  module?: string;
  target?: string;
  objective?: string;
  autoRun?: boolean;
  iterations?: number;
  provider?: string;
  model?: string;
  region?: string;
}

/**
 * AppContent - Main Application Logic
 */
const AppContent: React.FC<AppProps> = ({ 
  module, 
  target, 
  objective, 
  autoRun, 
  iterations, 
  provider, 
  model, 
  region 
}) => {
  const { stdout } = useStdout();
  const { exit } = useApp();
  // Track timeouts to ensure proper cleanup on unmount
  const timeoutsRef = React.useRef<NodeJS.Timeout[]>([]);
  const registerTimeout = useCallback((fn: () => void, ms: number) => {
    const id = setTimeout(fn, ms) as unknown as NodeJS.Timeout;
    timeoutsRef.current.push(id);
    return id;
  }, []);
  
  // Configuration and theme management
  const { config: applicationConfig, isConfigLoading } = useConfig();
  const currentTheme = themeManager.getCurrentTheme();
  
  // Consolidated state management
  const { state: appState, actions } = useApplicationState();
  
  // Command parser service
  const commandParser = React.useMemo(() => new InputParser(), []);
  
  // Modal management
  const modalManager = useModalManager();
  const { 
    activeModal, 
    modalContext,
    staticKey: modalStaticKey,
    openConfig,
    closeModal
  } = modalManager;
  
  // Operation management
  const operationManager = useOperationManager({
    appState,
    actions,
    applicationConfig,
    activeModal
  });
  
  // Terminal refresh function - fixed to prevent duplicate updates
  const refreshStatic = useCallback(() => {
    // Only call modalManager.refreshStatic() to avoid duplicate static key updates
    // modalManager handles both the terminal clear and static key increment
    modalManager.refreshStatic();
  }, [modalManager]);

  // Cleanup any pending timeouts on unmount
  useEffect(() => {
    return () => {
      for (const t of timeoutsRef.current) {
        try { clearTimeout(t); } catch {}
      }
      timeoutsRef.current = [];
    };
  }, []);
  
  // Screen clear handler - fixed to prevent race condition
  const handleScreenClear = useCallback(() => {
    // Batch all state updates together to minimize re-renders
    operationManager.clearOperationHistory();
    actions.resetErrorCount();
    actions.setTerminalVisible(false);
    actions.setActiveOperation(null);
    actions.clearCompletedOperation(); // Clear the completed operation flag
    
    // Schedule on next tick to ensure state updates are processed
    // before clearing the terminal, preventing the black screen issue
    const schedule = typeof setImmediate === 'function'
      ? setImmediate
      : (fn: (...args: any[]) => void) => setTimeout(fn, 0);
    schedule(() => {
      // Only use modalManager's refresh to avoid double clear
      modalManager.refreshStatic();
    });
  }, [actions, operationManager, modalManager]);

  // Keyboard handlers
  // Disable terminal-level handlers during initialization flow so Setup Wizard owns ESC/back behavior
  const isTerminalInteractive = activeModal === ModalType.NONE && !appState.userHandoffActive && !appState.isInitializationFlowActive;
  
  // Only allow global ESC when no modals are open and not in setup wizard - modals and setup handle their own ESC behavior
  const allowGlobalEscape = activeModal === ModalType.NONE && !appState.userHandoffActive && !appState.isInitializationFlowActive;
  
  const handleEscapeExit = useCallback(() => {
    // Show exit notification in operation history
    operationManager.addOperationHistoryEntry('info', '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
    operationManager.addOperationHistoryEntry('info', '🔴 ESC Key Pressed - Exiting Cyber-AutoAgent...');
    operationManager.addOperationHistoryEntry('info', '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
    operationManager.addOperationHistoryEntry('info', 'Thank you for using Cyber-AutoAgent. Goodbye!');
    
    // Delay exit slightly to show the message
    registerTimeout(() => {
      exit();
    }, 1000);
  }, [operationManager, exit, registerTimeout]);
  
  useKeyboardHandlers({
    activeOperation: appState.activeOperation,
    isTerminalInteractive: isTerminalInteractive,
    onAssessmentPause: operationManager.handleAssessmentPause,
    onAssessmentCancel: operationManager.handleAssessmentCancel, // Kill switch with notification
    onScreenClear: handleScreenClear,
    onEscapeExit: handleEscapeExit,
    allowGlobalEscape: allowGlobalEscape // Only allow ESC to exit when no modals are open
  });
  
  // Command handler
  const { handleUnifiedInput } = useCommandHandler({
    commandParser,
    assessmentFlowManager: operationManager.assessmentFlowManager,
    operationManager: operationManager.operationManager,
    appState,
    actions,
    applicationConfig,
    addOperationHistoryEntry: operationManager.addOperationHistoryEntry,
    openConfig: modalManager.openConfig,
    openMemorySearch: modalManager.openMemorySearch,
    openModuleSelector: modalManager.openModuleSelector,
    openSafetyWarning: modalManager.openSafetyWarning,
    openDocumentation: modalManager.openDocumentation,
    handleScreenClear,
    refreshStatic,
    modalManager,
    setAssessmentFlowState: operationManager.setAssessmentFlowState
  });
  
  // Module context
  const { availableModules } = useModule();
  
  // Sync available modules with InputParser
  useEffect(() => {
    commandParser.setAvailableModules(Object.keys(availableModules));
  }, [availableModules, commandParser]);
  
  // Configuration loading effect - mark as loaded
  useEffect(() => {
    const loadConfig = async () => {
      try {
        // Configuration loading logic here
        actions.setConfigLoaded(true);
      } catch (error) {
        // Config loading failed - continue with defaults
        actions.setConfigLoaded(true);
      }
    };
    
    if (!appState.isConfigLoaded) {
      loadConfig();
    }
  }, [appState.isConfigLoaded, actions]);
  
  // Smart deployment detection (extracted to hook)
  useDeploymentDetection({
    isConfigLoading,
    appState,
    actions,
    applicationConfig,
    activeModal,
    openConfig
  });
  
  // Main app view props
  const mainAppViewProps = React.useMemo(() => ({
    appState,
    actions,
    currentTheme,
    operationHistoryEntries: operationManager.operationHistoryEntries,
    assessmentFlowState: operationManager.assessmentFlowState,
    staticKey: appState.staticKey,
    activeModal,
    modalContext,
    isTerminalInteractive,
    onInput: handleUnifiedInput,
    onModalClose: closeModal,
    addOperationHistoryEntry: operationManager.addOperationHistoryEntry,
    onSafetyConfirm: operationManager.startAssessmentExecution,
    applicationConfig
  }), [
    appState,
    actions,
    currentTheme,
    operationManager.operationHistoryEntries,
    operationManager.assessmentFlowState,
    appState.staticKey,
    activeModal,
    modalContext,
    isTerminalInteractive,
    handleUnifiedInput,
    closeModal,
    operationManager.addOperationHistoryEntry,
    operationManager.startAssessmentExecution,
    applicationConfig
  ]);
  
  
  // Auto-run behavior (extracted to hook)
  useAutoRun({
    autoRun,
    target,
    module,
    objective,
    iterations,
    provider,
    model,
    region,
    appState,
    actions,
    applicationConfig,
    operationManager,
    registerTimeout
  });
  
  return (
    <InitializationWrapper
      appState={appState}
      applicationConfig={applicationConfig}
      onInitializationComplete={(completionMessage) => {
        // Dismiss initialization first, then clear the screen after state updates,
        // so refreshStatic actually clears (it skips clearing during init flow)
        actions.dismissInit();
        setTimeout(() => {
          refreshStatic();
        }, 0);
        // Avoid adding setup completion messages to operation history
      }}
      onConfigOpen={() => openConfig()}
      mainAppViewProps={mainAppViewProps}
    />
  );
};

/**
 * Main App Component with Context Providers
 */
export const App: React.FC<AppProps> = (props) => {
  return (
    <ErrorBoundary>
      <ConfigProvider>
        <ModuleProvider>
          <AppContent {...props} />
        </ModuleProvider>
      </ConfigProvider>
    </ErrorBoundary>
  );
};

export default App;