/**
 * useSetupWizard Hook
 * 
 * Centralized state management for the setup wizard.
 * Manages setup flow state, progress tracking, and setup operations.
 */

import { useReducer, useCallback, useMemo } from 'react';
import { SetupService, DeploymentMode, SetupProgress, SetupResult } from '../services/SetupService.js';

export type SetupStep = 'welcome' | 'deployment' | 'progress';

export interface SetupState {
  currentStep: SetupStep;
  selectedMode: DeploymentMode | null;
  isLoading: boolean;
  error: string | null;
  progress: SetupProgress | null;
  isComplete: boolean;
  lastProgressUpdate: number;
}

type SetupAction =
  | { type: 'NEXT_STEP' }
  | { type: 'PREVIOUS_STEP' }
  | { type: 'SELECT_MODE'; payload: DeploymentMode }
  | { type: 'START_SETUP' }
  | { type: 'UPDATE_PROGRESS'; payload: SetupProgress }
  | { type: 'COMPLETE_SETUP'; payload: SetupResult }
  | { type: 'SET_ERROR'; payload: string }
  | { type: 'RESET_ERROR' }
  | { type: 'RESET_WIZARD' };

const getInitialStep = (): SetupStep => {
  // If user explicitly triggered setup (via /setup command), skip welcome
  if (typeof process !== 'undefined' && process.env.CYBER_SHOW_SETUP === 'true') {
    return 'deployment';
  }
  return 'welcome';
};

const initialState: SetupState = {
  currentStep: getInitialStep(),
  selectedMode: null,
  isLoading: false,
  error: null,
  progress: null,
  isComplete: false,
  lastProgressUpdate: 0,
};

function setupReducer(state: SetupState, action: SetupAction): SetupState {
  switch (action.type) {
    case 'NEXT_STEP':
      const stepOrder: SetupStep[] = ['welcome', 'deployment', 'progress'];
      const currentIndex = stepOrder.indexOf(state.currentStep);
      const nextStep = stepOrder[currentIndex + 1] || state.currentStep;
      return { ...state, currentStep: nextStep };

    case 'PREVIOUS_STEP':
      const prevStepOrder: SetupStep[] = ['welcome', 'deployment', 'progress'];
      const prevCurrentIndex = prevStepOrder.indexOf(state.currentStep);
      const prevStep = prevStepOrder[prevCurrentIndex - 1] || state.currentStep;
      return { ...state, currentStep: prevStep, error: null };

    case 'SELECT_MODE':
      return { ...state, selectedMode: action.payload, error: null };

    case 'START_SETUP':
      return { 
        ...state, 
        currentStep: 'progress',
        isLoading: true, 
        error: null, 
        progress: null,
        isComplete: false 
      };

    case 'UPDATE_PROGRESS':
      // Immediate progress updates for responsive UI
      return { ...state, progress: action.payload, lastProgressUpdate: Date.now() };

    case 'COMPLETE_SETUP':
      return {
        ...state,
        isLoading: false,
        isComplete: action.payload.success,
        error: action.payload.success ? null : action.payload.error || 'Setup failed',
      };

    case 'SET_ERROR':
      return { ...state, error: action.payload, isLoading: false };

    case 'RESET_ERROR':
      return { ...state, error: null };

    case 'RESET_WIZARD':
      return initialState;

    default:
      return state;
  }
}

export interface UseSetupWizardResult {
  state: SetupState;
  actions: {
    nextStep: () => void;
    previousStep: () => void;
    selectMode: (mode: DeploymentMode) => void;
    startSetup: (modeOverride?: DeploymentMode) => Promise<void>;
    setError: (error: string) => void;
    resetError: () => void;
    resetWizard: () => void;
  };
}

/**
 * Hook for managing setup wizard state and operations
 */
export function useSetupWizard(): UseSetupWizardResult {
  const [state, dispatch] = useReducer(setupReducer, initialState);
  const setupService = useMemo(() => new SetupService(), []);

  const nextStep = useCallback(() => {
    dispatch({ type: 'NEXT_STEP' });
  }, []);

  const previousStep = useCallback(() => {
    dispatch({ type: 'PREVIOUS_STEP' });
  }, []);

  const selectMode = useCallback((mode: DeploymentMode) => {
    dispatch({ type: 'SELECT_MODE', payload: mode });
  }, []);

  const startSetup = useCallback(async (modeOverride?: DeploymentMode) => {
    // Use mode override if provided, otherwise get from current state
    const currentMode = modeOverride || state.selectedMode;
    
    if (!currentMode) {
      dispatch({ type: 'SET_ERROR', payload: 'No deployment mode selected' });
      return;
    }

    dispatch({ type: 'START_SETUP' });

    try {
      const result = await setupService.setupDeploymentMode(
        currentMode,
        (progress) => {
          dispatch({ type: 'UPDATE_PROGRESS', payload: progress });
        }
      );

      dispatch({ type: 'COMPLETE_SETUP', payload: result });
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Setup failed';
      dispatch({ type: 'SET_ERROR', payload: errorMessage });
    }
  }, [setupService, state.selectedMode]); // Keep dependency for proper updates

  const setError = useCallback((error: string) => {
    dispatch({ type: 'SET_ERROR', payload: error });
  }, []);

  const resetError = useCallback(() => {
    dispatch({ type: 'RESET_ERROR' });
  }, []);

  const resetWizard = useCallback(() => {
    dispatch({ type: 'RESET_WIZARD' });
  }, []);

  const actions = useMemo(() => ({
    nextStep,
    previousStep,
    selectMode,
    startSetup,
    setError,
    resetError,
    resetWizard,
  }), [nextStep, previousStep, selectMode, startSetup, setError, resetError, resetWizard]);

  return {
    state,
    actions,
  };
}