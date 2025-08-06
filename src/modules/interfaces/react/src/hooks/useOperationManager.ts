/**
 * Operation Manager Hook
 * 
 * Extracts operation management logic from App.tsx including:
 * - Assessment operations (pause, cancel, execution)
 * - Operation history tracking
 * - Assessment flow state management
 */

import { useState, useCallback, useRef } from 'react';
import { Operation, OperationManager } from '../services/OperationManager.js';
import { AssessmentFlow } from '../services/AssessmentFlow.js';
import { ApplicationState } from './useApplicationState.js';

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
  dockerService?: any;
}

export function useOperationManager({
  appState,
  actions,
  applicationConfig,
  dockerService
}: UseOperationManagerProps) {
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

  // Track if we've already added initial messages
  const hasAddedInitialMessage = useRef(false);

  // Operation history management
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
    
    setOperationHistoryEntries(prev => [...prev, entry]);
  }, []);

  // Assessment pause handler (implements documented Ctrl+C behavior)
  const handleAssessmentPause = useCallback(() => {
    if (appState.activeOperation) {
      const pauseSuccess = operationManager.pauseOperation(appState.activeOperation.id);
      if (pauseSuccess) {
        actions.updateOperation({ status: 'paused' });
        addOperationHistoryEntry('info', 'Operation paused. Type "resume" to continue.');
      }
    }
  }, [appState.activeOperation, operationManager, actions, addOperationHistoryEntry]);

  // Assessment cancel handler
  const handleAssessmentCancel = useCallback(async () => {
    if (appState.activeOperation) {
      try {
        // Stop the operation using pause functionality
        operationManager.pauseOperation(appState.activeOperation.id);
        actions.setActiveOperation(null);
        actions.setUserHandoff(false);
        addOperationHistoryEntry('info', 'Assessment cancelled by user.');
      } catch (error) {
        addOperationHistoryEntry('error', `Failed to cancel assessment: ${error.message}`);
      }
    }
  }, [appState.activeOperation, operationManager, actions, addOperationHistoryEntry]);

  // Clear operation history
  const clearOperationHistory = useCallback(() => {
    setOperationHistoryEntries([]);
  }, []);

  // Start assessment execution after safety confirmation
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
      
      // Add to operation history
      addOperationHistoryEntry('info', `Starting ${assessmentParams.module} assessment on ${assessmentParams.target}`);
      addOperationHistoryEntry('info', `Operation ID: ${operation.id}`);
      
      // Reset the assessment flow for next operation
      assessmentFlowManager.resetCompleteWorkflow();
      
      // Execute the assessment via Docker/Python backend
      if (dockerService) {
        addOperationHistoryEntry('info', 'Launching assessment execution...');
        
        // Set up minimal event listeners for operation status updates only
        // The UnconstrainedTerminal component will handle the actual event display
        const handleDockerEvent = (event: any) => {
          // Only update operation progress, don't duplicate events in history
          if (event.step && event.total_steps) {
            operationManager.updateOperation(operation.id, {
              currentStep: event.step,
              totalSteps: event.total_steps,
              description: event.content || operation.description
            });
          }
          
          // Handle critical errors
          if (event.type === 'error' && event.content && event.content.includes('CRITICAL')) {
            addOperationHistoryEntry('error', event.content);
          }
        };
        
        const handleDockerComplete = () => {
          addOperationHistoryEntry('info', 'Assessment completed');
          operationManager.updateOperation(operation.id, {
            status: 'completed',
            description: 'Assessment completed successfully'
          });
          actions.setActiveOperation(null);
          actions.setHasCompletedOperation(true); // Mark that operation completed
          // Clean up listeners
          dockerService.removeListener('event', handleDockerEvent);
          dockerService.removeListener('complete', handleDockerComplete);
        };
        
        // Attach event listeners
        dockerService.on('event', handleDockerEvent);
        dockerService.on('complete', handleDockerComplete);
        
        // Execute in background - don't await to avoid blocking UI
        dockerService.executeAssessment(assessmentParams, applicationConfig).catch((error: any) => {
          addOperationHistoryEntry('error', `Docker execution failed: ${error.message}`);
          // Mark operation as failed
          operationManager.updateOperation(operation.id, {
            status: 'error',
            description: `Execution failed: ${error.message}`
          });
          actions.setActiveOperation(null);
          actions.setHasCompletedOperation(true); // Mark that operation completed (even if failed)
          // Clean up listeners
          dockerService.removeListener('event', handleDockerEvent);
          dockerService.removeListener('complete', handleDockerComplete);
        });
      } else {
        addOperationHistoryEntry('error', 'Docker service not available - unable to execute assessment');
      }
      
    } catch (error) {
      addOperationHistoryEntry('error', `Failed to start assessment: ${error.message}`);
    }
  }, [assessmentFlowManager, operationManager, applicationConfig, actions, addOperationHistoryEntry, dockerService]);

  return {
    // Services
    assessmentFlowManager,
    operationManager,
    
    // State
    operationHistoryEntries,
    assessmentFlowState,
    setAssessmentFlowState,
    
    // Actions
    addOperationHistoryEntry,
    handleAssessmentPause,
    handleAssessmentCancel,
    clearOperationHistory,
    startAssessmentExecution
  };
}