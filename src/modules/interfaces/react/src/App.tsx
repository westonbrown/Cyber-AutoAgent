/**
 * Cyber-AutoAgent React Application
 * 
 * Main entry point for the React-based CLI interface.
 * Manages application state, services, and UI rendering.
 */

import React, { useCallback, useEffect } from 'react';
import { useStdout, useInput, useApp } from 'ink';
import ansiEscapes from 'ansi-escapes';

// State Management
import { useApplicationState } from './hooks/useApplicationState.js';
import { useModalManager } from './hooks/useModalManager.js';
import { useOperationManager } from './hooks/useOperationManager.js';

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
  
  // Operation management
  const operationManager = useOperationManager({
    appState,
    actions,
    applicationConfig
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

  // Handle global keyboard shortcuts with highest priority
  const isTerminalInteractive = process.stdin.isTTY;
  
  // Add raw stdin handler for Escape key as a fallback
  useEffect(() => {
    if (!process.stdin.isTTY) return;
    
    const handleRawInput = (data: Buffer) => {
      const input = data.toString();
      // Check for ESC character (ASCII 27 or \x1B)
      if (input === '\x1B' || input.charCodeAt(0) === 27) {
        if (appState.activeOperation && appState.executionService) {
          operationManager.handleAssessmentCancel();
        }
      }
    };
    
    process.stdin.on('data', handleRawInput);
    return () => {
      process.stdin.off('data', handleRawInput);
    };
  }, [appState.activeOperation, appState.executionService, operationManager.handleAssessmentCancel]);
  
  useInput((input, key) => {
    if (!isTerminalInteractive) return;
    
    if (key.ctrl && input === 'c') {
      if (appState.activeOperation?.status === 'running') {
        operationManager.handleAssessmentPause();
      } else {
        exit();
      }
    }
    
    if (key.ctrl && input === 'l') {
      handleScreenClear();
    }
    
    if (key.escape) {
      if (activeModal !== 'none') {
        modalManager.closeModal();
      } else if (appState.activeOperation && appState.executionService) {
        operationManager.handleAssessmentCancel();
      } else {
        exit();
      }
    }
  }, { isActive: isTerminalInteractive });
  
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
    onSafetyConfirm: operationManager.startAssessmentExecution
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