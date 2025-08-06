/**
 * Cyber-AutoAgent React Application
 * 
 * Main entry point for the React-based CLI interface.
 * Manages application state, services, and UI rendering.
 */

import React, { useCallback, useEffect } from 'react';
import { useStdout } from 'ink';
import ansiEscapes from 'ansi-escapes';

// State Management
import { useApplicationState } from './hooks/useApplicationState.js';
import { useModalManager } from './hooks/useModalManager.js';
import { useOperationManager } from './hooks/useOperationManager.js';
import { useKeyboardHandlers } from './hooks/useKeyboardHandlers.js';

// Core Services  
import { DirectDockerService } from './services/DirectDockerService.js';
import { InputParser } from './services/InputParser.js';

// Context Providers
import { ConfigProvider, useConfig } from './contexts/ConfigContext.js';
import { ModuleProvider, useModule } from './contexts/ModuleContext.js';

// Command Handler
import { useCommandHandler } from './hooks/useCommandHandler.js';

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
}

/**
 * AppContent - Main Application Logic
 */
const AppContent: React.FC<AppProps> = () => {
  const { stdout } = useStdout();
  
  // Configuration and theme management
  const { config: applicationConfig } = useConfig();
  const currentTheme = themeManager.getCurrentTheme();
  
  // Consolidated state management
  const { state: appState, actions } = useApplicationState();
  
  // Services
  const [dockerService] = React.useState(() => new DirectDockerService());
  const [commandParser] = React.useState(() => new InputParser());
  
  // Operation management
  const operationManager = useOperationManager({
    appState,
    actions,
    applicationConfig,
    dockerService
  });
  
  // Modal management
  const modalManager = useModalManager();
  const { 
    activeModal, 
    modalContext,
    staticKey,
    openConfig,
    closeModal
  } = modalManager;
  
  // Terminal refresh function
  const refreshStatic = useCallback(() => {
    if (!appState.isInitializationFlowActive) {
      stdout.write(ansiEscapes.clearTerminal);
    }
    modalManager.refreshStatic();
  }, [stdout, modalManager, appState.isInitializationFlowActive]);
  
  // Screen clear handler
  const handleScreenClear = useCallback(() => {
    operationManager.clearOperationHistory();
    actions.resetErrorCount();
    actions.setTerminalVisible(false);
    actions.setActiveOperation(null);
    actions.clearCompletedOperation(); // Clear the completed operation flag
    refreshStatic();
  }, [refreshStatic, actions, operationManager]);

  // Keyboard handlers
  const isTerminalInteractive = activeModal === 'none' && !appState.userHandoffActive;
  
  useKeyboardHandlers({
    activeOperation: appState.activeOperation,
    isTerminalInteractive,
    onAssessmentPause: operationManager.handleAssessmentPause,
    onScreenClear: handleScreenClear
  });
  
  // Command handler
  const { handleUnifiedInput } = useCommandHandler({
    commandParser,
    assessmentFlowManager: operationManager.assessmentFlowManager,
    operationManager: operationManager.operationManager,
    dockerService,
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
  
  // Configuration loading effect
  useEffect(() => {
    const loadConfig = async () => {
      try {
        // Configuration loading logic here
        actions.setConfigLoaded(true);
      } catch (error) {
        console.error('Config loading error:', error);
        actions.setConfigLoaded(true);
      }
    };
    
    if (!appState.isConfigLoaded) {
      loadConfig();
    }
  }, [appState.isConfigLoaded, actions]);
  
  // Main app view props
  const mainAppViewProps = {
    appState,
    currentTheme,
    operationHistoryEntries: operationManager.operationHistoryEntries,
    assessmentFlowState: operationManager.assessmentFlowState,
    staticKey,
    activeModal,
    modalContext,
    isTerminalInteractive,
    onInput: handleUnifiedInput,
    onModalClose: closeModal,
    addOperationHistoryEntry: operationManager.addOperationHistoryEntry,
    onSafetyConfirm: operationManager.startAssessmentExecution,
    dockerService
  };
  
  return (
    <InitializationWrapper
      appState={appState}
      applicationConfig={applicationConfig}
      onInitializationComplete={(completionMessage) => {
        actions.dismissInit();
        if (completionMessage) {
          operationManager.addOperationHistoryEntry('info', completionMessage);
        }
      }}
      onConfigOpen={() => openConfig()}
      refreshStatic={refreshStatic}
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