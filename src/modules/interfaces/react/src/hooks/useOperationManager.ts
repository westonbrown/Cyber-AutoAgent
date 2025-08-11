/**
 * Operation Manager Hook
 * 
 * Extracts operation management logic from App.tsx including:
 * - Assessment operations (pause, cancel, execution)
 * - Operation history tracking
 * - Assessment flow state management
 */

import React, { useState, useCallback, useRef } from 'react';
import { Operation, OperationManager } from '../services/OperationManager.js';
import { AssessmentFlow } from '../services/AssessmentFlow.js';
import { ApplicationState } from './useApplicationState.js';
import { useDebouncedState } from './useDebouncedState.js';
import { ExecutionServiceFactory, ServiceSelectionResult } from '../services/ExecutionServiceFactory.js';
import { ExecutionService, ExecutionHandle, DEFAULT_EXECUTION_CONFIG } from '../services/ExecutionService.js';
import { useConfig } from '../contexts/ConfigContext.js';

export interface OperationHistoryEntry {
  id: string;
  timestamp: Date;
  type: 'operation' | 'command' | 'info' | 'error';
  content: string;
  operation?: Operation;
}

interface AssessmentFlowState {
  step: 'idle' | 'module' | 'target' | 'objective' | 'ready';
  module?: string;
  target?: string;
  objective?: string;
}

interface UseOperationManagerProps {
  appState: ApplicationState;
  actions: any;
  applicationConfig: any;
  activeModal?: any; // Optional modal state to prevent updates during modal display
}

export function useOperationManager({
  appState,
  actions,
  applicationConfig,
  activeModal
}: UseOperationManagerProps) {
  const { config } = useConfig();
  // Core service initialization (singleton pattern)
  const [assessmentFlowManager] = useState(() => new AssessmentFlow());
  const [operationManager] = useState(() => new OperationManager(applicationConfig));
  
  // Local operation state
  const [operationHistoryEntries, setOperationHistoryEntries] = useState<OperationHistoryEntry[]>([]);
  const [assessmentFlowState, setAssessmentFlowState] = useState<AssessmentFlowState>(() => {
    // Initialize state from the AssessmentFlow service
    const initialState = assessmentFlowManager.getState();
    return {
      step: initialState.stage === 'ready' ? 'ready' : 
            initialState.stage === 'objective' ? 'objective' :
            initialState.stage === 'target' ? 'target' :
            initialState.stage === 'module' ? 'module' : 'idle',
      module: initialState.module,
      target: initialState.target,
      objective: initialState.objective
    };
  });

  // Debouncing for operation history to prevent UI flicker from rapid updates
  const [debouncedHistoryEntries, setDebouncedHistoryEntries, flushHistoryEntries] = useDebouncedState<OperationHistoryEntry[]>([], 100);
  
  // Track if we've already added initial messages
  const hasAddedInitialMessage = useRef(false);
  const historyUpdateTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const isMountedRef = useRef(true);
  const metricsIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const currentExecutionServiceRef = useRef<ExecutionService | null>(null);
  const lastMetricsUpdateRef = useRef<number>(0);

  // Throttled metrics updater to avoid excessive re-renders during streaming
  const updateMetricsThrottled = useCallback((metrics: {
    tokens: number;
    cost: number;
    duration: string;
    memoryOps: number;
    evidence: number;
  }) => {
    const now = Date.now();
    if (now - (lastMetricsUpdateRef.current || 0) < 300) {
      return;
    }
    lastMetricsUpdateRef.current = now;
    actions.updateMetrics(metrics);
  }, [actions]);

  React.useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
      // Clear debounced history timeout
      if (historyUpdateTimeoutRef.current) {
        clearTimeout(historyUpdateTimeoutRef.current);
        historyUpdateTimeoutRef.current = null;
      }
      // Clear metrics interval if active
      if (metricsIntervalRef.current) {
        clearInterval(metricsIntervalRef.current);
        metricsIntervalRef.current = null;
      }
      // Detach and cleanup any lingering execution service
      if (currentExecutionServiceRef.current) {
        try {
          currentExecutionServiceRef.current.removeAllListeners();
          currentExecutionServiceRef.current.cleanup();
        } catch {}
        currentExecutionServiceRef.current = null;
      }
    };
  }, []);

  // Operation history management with debouncing for rapid updates
  const addOperationHistoryEntry = useCallback((
    type: OperationHistoryEntry['type'], 
    content: string, 
    operation?: Operation
  ) => {
    const entry: OperationHistoryEntry = {
      id: `${Date.now()}-${Math.random()}`,
      timestamp: new Date(),
      type,
      content,
      operation
    };
    
    // For critical messages (errors), update immediately
    if (type === 'error') {
      if (!isMountedRef.current) return; // don't set state after unmount
      setOperationHistoryEntries(prev => {
        const newEntries = [...prev, entry];
        if (isMountedRef.current) {
          setDebouncedHistoryEntries(newEntries); // Update debounced state immediately for errors
        }
        return newEntries;
      });
      return;
    }
    
    // For other messages, debounce the updates to prevent UI flicker
    if (!isMountedRef.current) return;
    setOperationHistoryEntries(prev => {
      const newEntries = [...prev, entry];
      
      // Clear any existing timeout
      if (historyUpdateTimeoutRef.current) {
        clearTimeout(historyUpdateTimeoutRef.current);
      }
      
      // Set debounced update
      historyUpdateTimeoutRef.current = setTimeout(() => {
        if (isMountedRef.current) {
          setDebouncedHistoryEntries(newEntries);
        }
        historyUpdateTimeoutRef.current = null;
      }, 100);
      
      return newEntries;
    });
  }, [setDebouncedHistoryEntries]);

  // Assessment pause handler (implements documented Ctrl+C and ESC behavior)
  const handleAssessmentPause = useCallback(async () => {
    if (appState.activeOperation) {
      try {
        // First, stop the execution service to kill the running Python process
        if (appState.executionService) {
          addOperationHistoryEntry('info', 'Stopping operation...');
          await (appState.executionService as any).stop();
        }
        
        // Then update the operation manager state
        const pauseSuccess = operationManager.pauseOperation(appState.activeOperation.id);
        if (pauseSuccess) {
          actions.updateOperation({ status: 'paused' });
          actions.setActiveOperation(null); // Clear the active operation since it's been stopped
          actions.setExecutionService(null); // Clear the execution service reference
          addOperationHistoryEntry('info', 'Operation stopped.');
        }
      } catch (error) {
        addOperationHistoryEntry('error', `Failed to stop operation: ${error.message}`);
      }
    }
  }, [appState.activeOperation, appState.executionService, operationManager, actions, addOperationHistoryEntry]);

  // Assessment cancel handler
  const handleAssessmentCancel = useCallback(async () => {
    if (appState.activeOperation) {
      try {
        // First, stop the execution using the executionHandle stored on the operation
        const executionHandle = (appState.activeOperation as any).executionHandle;
        if (executionHandle && executionHandle.stop) {
          await executionHandle.stop();
        } else if (appState.executionService) {
          // Fallback: emit stop event to the service
          appState.executionService.emit('stop');
        }
        
        // Then update the operation manager state
        operationManager.pauseOperation(appState.activeOperation.id);
        actions.setActiveOperation(null);
        actions.setExecutionService(null); // Clear the execution service reference
        actions.setUserHandoff(false);
        actions.setHasCompletedOperation(true); // Mark as completed to show the message
        
        // Reset the assessment flow for next operation (fixes issue with same target)
        assessmentFlowManager.resetCompleteWorkflow();
        
        // Add simple termination message (avoid duplicate with handleExecutionStopped)
        addOperationHistoryEntry('error', '🛑 ESC Kill Switch activated');
        addOperationHistoryEntry('info', 'Operation terminated. Start a new assessment or review partial results.');
        // Ensure messages are visible immediately (bypass debounce)
        try { (flushHistoryEntries as any)?.(); } catch {}
      } catch (error) {
        addOperationHistoryEntry('error', `Failed to cancel assessment: ${error.message}`);
      }
    }
  }, [appState.activeOperation, appState.executionService, operationManager, actions, addOperationHistoryEntry]);

  // Clear operation history
  const clearOperationHistory = useCallback(() => {
    setOperationHistoryEntries([]);
    setDebouncedHistoryEntries([]);
    // Clear any pending timeout
    if (historyUpdateTimeoutRef.current) {
      clearTimeout(historyUpdateTimeoutRef.current);
      historyUpdateTimeoutRef.current = null;
    }
  }, [setDebouncedHistoryEntries]);

  // Start assessment execution using unified execution service architecture
  const startAssessmentExecution = useCallback(async () => {
    const assessmentParams = assessmentFlowManager.getValidatedAssessmentParameters();
    if (!assessmentParams) {
      addOperationHistoryEntry('error', 'Assessment parameters not properly configured');
      return;
    }

    try {
      // Start the operation
      const operation = operationManager.startOperation(
        assessmentParams.module,
        assessmentParams.target,
        assessmentParams.objective || `Comprehensive ${assessmentParams.module} security assessment`,
        applicationConfig.modelId
      );

      // Set as active operation
      actions.setActiveOperation(operation);
      
      // Initialize metrics in app state (preserve existing if re-running)
      actions.updateMetrics({
        tokens: appState.operationMetrics?.tokens || 0,
        cost: appState.operationMetrics?.cost || 0,
        duration: '0s',
        memoryOps: appState.operationMetrics?.memoryOps || 0,
        evidence: appState.operationMetrics?.evidence || 0
      });
      
      // Add to operation history with deployment mode
      const deploymentModeDisplay = 
        config.deploymentMode === 'local-cli' ? 'Local Python CLI' :
        config.deploymentMode === 'single-container' ? 'Single Container' :
        config.deploymentMode === 'full-stack' ? 'Full Stack' : 'Auto';
      
      addOperationHistoryEntry('info', `Starting ${assessmentParams.module} assessment on ${assessmentParams.target}`);
      addOperationHistoryEntry('info', `Operation ID: ${operation.id}`);
      addOperationHistoryEntry('info', `Execution Mode: ${deploymentModeDisplay}`);
      
      // Select and validate execution service using the factory
      addOperationHistoryEntry('info', 'Selecting execution service...');
      
      let serviceSelection: ServiceSelectionResult;
      try {
        // Map deploymentMode to execution mode
        const getExecutionMode = (deploymentMode: string) => {
          switch (deploymentMode) {
            case 'single-container': return 'docker-single';
            case 'full-stack': return 'docker-stack';
            case 'local-cli': return 'python-cli';
            default: return undefined;
          }
        };

        // Create execution config with user preferences from setup
        const executionConfig = {
          ...DEFAULT_EXECUTION_CONFIG,
          preferredMode: getExecutionMode(config.deploymentMode) as any,
          fallbackModes: [] // Enforce strict mode selection - no fallbacks
        };
        
        serviceSelection = await ExecutionServiceFactory.selectService(config, executionConfig);
        
        // Enforce strict mode selection - fail if preferred mode not available
        if (!serviceSelection.isPreferred && config.deploymentMode) {
          throw new Error(`Selected ${config.deploymentMode} mode is not available. Please check your setup and try again.`);
        }
        
        if (serviceSelection.validation.warnings.length > 0) {
          serviceSelection.validation.warnings.forEach(warning => 
            addOperationHistoryEntry('info', `Warning: ${warning}`)
          );
        }
        
        addOperationHistoryEntry('info', `Selected execution mode: ${serviceSelection.mode}`);
        
      } catch (error) {
        addOperationHistoryEntry('error', `Failed to select execution service: ${error.message}`);
        operationManager.updateOperation(operation.id, {
          status: 'error',
          description: 'Failed to initialize execution environment'
        });
        actions.setActiveOperation(null);
        return;
      }
      
      const executionService = serviceSelection.service;
      
      // Store the execution service for UI components to use
      actions.setExecutionService(executionService);
      
      // Set up unified event handlers for all execution services
      const handleExecutionEvent = (event: any) => {
        // Handle progress updates
        if (event.step && event.total_steps) {
          operationManager.updateOperation(operation.id, {
            currentStep: event.step,
            totalSteps: event.total_steps,
            description: event.content || operation.description
          });
        }
        
        // Handle token usage updates
        if (event.tokens || event.inputTokens || event.outputTokens || event.cost) {
          const inputTokens = event.inputTokens || 0;
          const outputTokens = event.outputTokens || 0;
          
          if (inputTokens > 0 || outputTokens > 0) {
            operationManager.updateTokenUsage(operation.id, inputTokens, outputTokens);
            
            const currentOp = operationManager.getOperation(operation.id);
            if (currentOp) {
              updateMetricsThrottled({
                tokens: currentOp.cost.tokensUsed,
                cost: currentOp.cost.estimatedCost,
                duration: operationManager.getOperationDuration(operation.id),
                memoryOps: currentOp.findings,
                evidence: currentOp.findings
              });
            }
          }
        }
        
        // Handle critical errors
        if (event.type === 'error' && event.content && event.content.includes('CRITICAL')) {
          addOperationHistoryEntry('error', event.content);
        }
      };
      
      const handleExecutionComplete = (result: any) => {
        addOperationHistoryEntry('info', `Assessment completed (${serviceSelection.mode})`);
        operationManager.updateOperation(operation.id, {
          status: 'completed',
          description: 'Assessment completed successfully'
        });
        
        // Update final metrics
        const currentOp = operationManager.getOperation(operation.id);
        if (currentOp) {
          actions.updateMetrics({
            tokens: currentOp.cost.tokensUsed,
            cost: currentOp.cost.estimatedCost,
            duration: operationManager.getOperationDuration(operation.id),
            memoryOps: currentOp.findings,
            evidence: currentOp.findings
          });
        }
        
        actions.setActiveOperation(null);
        actions.setHasCompletedOperation(true);
        
        // Reset the assessment flow for next operation
        assessmentFlowManager.resetCompleteWorkflow();
        
        cleanupExecution();
      };
      
      const handleExecutionError = (error: any) => {
        addOperationHistoryEntry('error', `Execution error (${serviceSelection.mode}): ${error.message}`);
        operationManager.updateOperation(operation.id, {
          status: 'error',
          description: `Execution failed: ${error.message}`
        });
        actions.setActiveOperation(null);
        actions.setHasCompletedOperation(true);
        cleanupExecution();
      };
      
      const handleExecutionStopped = () => {
        // Just update the operation status, don't add duplicate messages
        // The ESC handler in handleAssessmentCancel already adds the user-facing messages
        operationManager.updateOperation(operation.id, {
          status: 'cancelled',
          description: 'Assessment stopped by user'
        });
        actions.setActiveOperation(null);
        cleanupExecution();
      };
      
      // Cleanup function for event listeners and intervals
      const cleanupExecution = () => {
        try {
          executionService.removeAllListeners();
          executionService.cleanup();
        } catch {}
        if (metricsIntervalRef.current) {
          clearInterval(metricsIntervalRef.current);
          metricsIntervalRef.current = null;
        }
        currentExecutionServiceRef.current = null;
        // Clear the execution service from state when done
        actions.setExecutionService(null);
      };
      
      // Attach unified event listeners
      executionService.on('event', handleExecutionEvent);
      executionService.on('complete', handleExecutionComplete);
      executionService.on('error', handleExecutionError);
      executionService.on('stopped', handleExecutionStopped);
      currentExecutionServiceRef.current = executionService;
      
      // Set up periodic metrics update with additional safeguards
      metricsIntervalRef.current = setInterval(() => {
        const currentOp = operationManager.getOperation(operation.id);
        // Only update metrics if operation is truly running, we're not in a modal,
        // and the operation is still the active one in both manager and app state
        const isModalActive = activeModal && activeModal !== 'none'; // Check if any modal is open
        if (currentOp && 
            currentOp.status === 'running' && 
            appState.activeOperation?.id === operation.id &&
            appState.activeOperation?.status === 'running' &&
            !appState.userHandoffActive && // Don't update when user handoff is active
            !isModalActive) { // Don't update when modals are open to prevent header re-renders
          actions.updateMetrics({
            tokens: currentOp.cost.tokensUsed,
            cost: currentOp.cost.estimatedCost,
            duration: operationManager.getOperationDuration(operation.id),
            memoryOps: currentOp.findings,
            evidence: currentOp.findings
          });
        }
      }, 5000) as unknown as NodeJS.Timeout;
      
      // Execute assessment through the selected service
      addOperationHistoryEntry('info', `Launching ${serviceSelection.mode} assessment execution...`);
      
      try {
        const executionHandle = await executionService.execute(assessmentParams, config);
        
        // Store handle for potential cancellation
        (operation as any).executionHandle = executionHandle;
        
        // Also update the active operation in state with the execution handle
        actions.updateOperation({ executionHandle });
        
        // Handle execution result in background
        executionHandle.result.catch(handleExecutionError);
        
      } catch (error) {
        handleExecutionError(error);
      }
      
    } catch (error) {
      addOperationHistoryEntry('error', `Failed to start assessment: ${error.message}`);
    }
  }, [assessmentFlowManager, operationManager, applicationConfig, actions, addOperationHistoryEntry, config]);

  // Cleanup timeout on unmount
  React.useEffect(() => {
    return () => {
      if (historyUpdateTimeoutRef.current) {
        clearTimeout(historyUpdateTimeoutRef.current);
      }
      flushHistoryEntries(); // Flush any pending updates
    };
  }, [flushHistoryEntries]);

  return {
    // Services
    assessmentFlowManager,
    operationManager,
    
    // State
    operationHistoryEntries,
    assessmentFlowState,
    setAssessmentFlowState,
    
    // Debounced state for UI performance
    debouncedHistoryEntries,
    flushHistoryEntries,
    
    // Actions
    addOperationHistoryEntry,
    handleAssessmentPause,
    handleAssessmentCancel,
    clearOperationHistory,
    startAssessmentExecution
  };
}