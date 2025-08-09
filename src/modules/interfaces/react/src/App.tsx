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
  
  // Configuration and theme management
  const { config: applicationConfig } = useConfig();
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
    staticKey,
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
  const isTerminalInteractive = activeModal === ModalType.NONE && !appState.userHandoffActive;
  
  // Only allow global ESC when no modals are open - modals should handle their own ESC behavior
  const allowGlobalEscape = activeModal === ModalType.NONE && !appState.userHandoffActive;
  
  const handleEscapeExit = useCallback(() => {
    // Show exit notification in operation history
    operationManager.addOperationHistoryEntry('info', '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
    operationManager.addOperationHistoryEntry('info', '🔴 ESC Key Pressed - Exiting Cyber-AutoAgent...');
    operationManager.addOperationHistoryEntry('info', '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
    operationManager.addOperationHistoryEntry('info', 'Thank you for using Cyber-AutoAgent. Goodbye!');
    
    // Delay exit slightly to show the message
    setTimeout(() => {
      exit();
    }, 1000);
  }, [operationManager, exit]);
  
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
        console.error('Config loading error:', error);
        actions.setConfigLoaded(true);
      }
    };
    
    if (!appState.isConfigLoaded) {
      loadConfig();
    }
  }, [appState.isConfigLoaded, actions]);
  
  // Separate effect to check if setup wizard is needed AFTER config is loaded
  useEffect(() => {
    // Only check after config is loaded and we haven't already dismissed init
    if (appState.isConfigLoaded && !appState.hasUserDismissedInit && !appState.isInitializationFlowActive) {
      // Check if this is truly a first-time setup
      const needsSetup = !applicationConfig.isConfigured || 
                        (!applicationConfig.hasSeenWelcome && !applicationConfig.deploymentMode);
      
      if (needsSetup) {
        console.log('First-time setup detected - showing setup wizard');
        actions.setInitializationFlow(true);
      } else {
        console.log('Configuration found - skipping setup wizard');
      }
    }
  }, [appState.isConfigLoaded, appState.hasUserDismissedInit, appState.isInitializationFlowActive, 
      applicationConfig.isConfigured, applicationConfig.hasSeenWelcome, applicationConfig.deploymentMode, actions]);
  
  // Main app view props
  const mainAppViewProps = {
    appState,
    actions,
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
    applicationConfig
  };
  
  
  // Handle autoRun mode - bypass interactive flow and start assessment immediately
  useEffect(() => {
    if (autoRun && target && module && appState.isConfigLoaded) {
      // Skip initialization flow
      actions.dismissInit();
      
      // Apply CLI parameter overrides to config if provided
      const configUpdates: Partial<typeof applicationConfig> = {};
      if (iterations && iterations !== applicationConfig.iterations) {
        configUpdates.iterations = iterations;
      }
      if (provider && provider !== applicationConfig.modelProvider) {
        configUpdates.modelProvider = provider as 'bedrock' | 'ollama' | 'litellm';
      }
      if (model && model !== applicationConfig.modelId) {
        configUpdates.modelId = model;
      }
      if (region && region !== applicationConfig.awsRegion) {
        configUpdates.awsRegion = region;
      }
      
      // Update config with CLI overrides if any
      if (Object.keys(configUpdates).length > 0) {
        // Note: This would need a updateConfig function in ConfigContext to persist changes
        console.log('CLI overrides applied:', configUpdates);
      }
      
      // Set assessment parameters using the flow manager's processUserInput method
      operationManager.assessmentFlowManager.processUserInput(`target ${target}`);
      if (objective) {
        operationManager.assessmentFlowManager.processUserInput(`objective ${objective}`);
      } else {
        // Use empty string to trigger default objective
        operationManager.assessmentFlowManager.processUserInput('');
      }
      
      // Start assessment execution automatically
      setTimeout(() => {
        operationManager.startAssessmentExecution();
      }, 100); // Small delay to ensure state is set
    }
  }, [autoRun, target, module, objective, iterations, provider, model, region, appState.isConfigLoaded, actions, operationManager, applicationConfig]);
  
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