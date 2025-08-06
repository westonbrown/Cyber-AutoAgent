/**
 * useApplicationState Hook
 * 
 * Consolidates all application state management into a single reducer-based hook.
 * This replaces the 24+ individual useState calls in App.tsx with a single,
 * manageable state object and dispatch pattern.
 */

import { useReducer, useCallback, useRef, useEffect, useMemo } from 'react';
import { Operation } from '../services/OperationManager.js';
import { ModalType } from './useModalManager.js';

// State shape definition
export interface ApplicationState {
  // Core application state
  isInitialized: boolean;
  isConfigLoaded: boolean;
  sessionId: string;
  sessionErrorCount: number;
  
  // UI state
  isFirstRunExperience: boolean;
  isInitializationFlowActive: boolean;
  hasUserDismissedInit: boolean;
  isDockerServiceAvailable: boolean;
  isTerminalVisible: boolean;
  staticKey: number;
  staticNeedsRefresh: boolean;
  hasCompletedOperation: boolean;  // Track if operation completed but not cleared
  
  // Assessment flow state
  activeOperation: Operation | null;
  userHandoffActive: boolean;
  contextUsage: number;
  operationMetrics: any | null;
  
  // Recent activity  
  recentTargets: string[];
  
  // Terminal dimensions
  terminalDisplayHeight: number;
  terminalDisplayWidth: number;
}

// Action types
export enum ActionType {
  // Initialization actions
  INITIALIZE_APP = 'INITIALIZE_APP',
  SET_CONFIG_LOADED = 'SET_CONFIG_LOADED',
  SET_INITIALIZATION_FLOW = 'SET_INITIALIZATION_FLOW',
  DISMISS_INIT = 'DISMISS_INIT',
  
  // UI actions
  SET_TERMINAL_VISIBLE = 'SET_TERMINAL_VISIBLE',
  REFRESH_STATIC = 'REFRESH_STATIC',
  SET_STATIC_NEEDS_REFRESH = 'SET_STATIC_NEEDS_REFRESH',
  UPDATE_TERMINAL_SIZE = 'UPDATE_TERMINAL_SIZE',
  SET_HAS_COMPLETED_OPERATION = 'SET_HAS_COMPLETED_OPERATION',
  CLEAR_COMPLETED_OPERATION = 'CLEAR_COMPLETED_OPERATION',
  
  // Operation actions
  SET_ACTIVE_OPERATION = 'SET_ACTIVE_OPERATION',
  UPDATE_OPERATION = 'UPDATE_OPERATION',
  SET_USER_HANDOFF = 'SET_USER_HANDOFF',
  UPDATE_METRICS = 'UPDATE_METRICS',
  
  // Target management
  ADD_RECENT_TARGET = 'ADD_RECENT_TARGET',
  
  // Error handling
  INCREMENT_ERROR_COUNT = 'INCREMENT_ERROR_COUNT',
  RESET_ERROR_COUNT = 'RESET_ERROR_COUNT',
  
  // Docker status
  SET_DOCKER_AVAILABLE = 'SET_DOCKER_AVAILABLE',
  
  // Context usage
  UPDATE_CONTEXT_USAGE = 'UPDATE_CONTEXT_USAGE',
}

// Action definitions
type Action =
  | { type: ActionType.INITIALIZE_APP; payload: { sessionId: string } }
  | { type: ActionType.SET_CONFIG_LOADED; payload: boolean }
  | { type: ActionType.SET_INITIALIZATION_FLOW; payload: boolean }
  | { type: ActionType.DISMISS_INIT }
  | { type: ActionType.SET_TERMINAL_VISIBLE; payload: boolean }
  | { type: ActionType.REFRESH_STATIC }
  | { type: ActionType.SET_STATIC_NEEDS_REFRESH; payload: boolean }
  | { type: ActionType.UPDATE_TERMINAL_SIZE; payload: { width: number; height: number } }
  | { type: ActionType.SET_HAS_COMPLETED_OPERATION; payload: boolean }
  | { type: ActionType.CLEAR_COMPLETED_OPERATION }
  | { type: ActionType.SET_ACTIVE_OPERATION; payload: Operation | null }
  | { type: ActionType.UPDATE_OPERATION; payload: Partial<Operation> }
  | { type: ActionType.SET_USER_HANDOFF; payload: boolean }
  | { type: ActionType.UPDATE_METRICS; payload: any }
  | { type: ActionType.ADD_RECENT_TARGET; payload: string }
  | { type: ActionType.INCREMENT_ERROR_COUNT }
  | { type: ActionType.RESET_ERROR_COUNT }
  | { type: ActionType.SET_DOCKER_AVAILABLE; payload: boolean }
  | { type: ActionType.UPDATE_CONTEXT_USAGE; payload: number };

// Reducer function
function applicationReducer(state: ApplicationState, action: Action): ApplicationState {
  switch (action.type) {
    case ActionType.INITIALIZE_APP:
      return {
        ...state,
        isInitialized: true,
        sessionId: action.payload.sessionId,
      };
      
    case ActionType.SET_CONFIG_LOADED:
      return { ...state, isConfigLoaded: action.payload };
      
    case ActionType.SET_INITIALIZATION_FLOW:
      return { 
        ...state, 
        isInitializationFlowActive: action.payload,
        // Reset dismissal state when activating initialization flow
        hasUserDismissedInit: action.payload ? false : state.hasUserDismissedInit
      };
      
    case ActionType.DISMISS_INIT:
      return {
        ...state,
        hasUserDismissedInit: true,
        isInitializationFlowActive: false,
      };
      
    case ActionType.SET_TERMINAL_VISIBLE:
      return { ...state, isTerminalVisible: action.payload };
      
    case ActionType.REFRESH_STATIC:
      return { ...state, staticKey: state.staticKey + 1 };
      
    case ActionType.SET_STATIC_NEEDS_REFRESH:
      return { ...state, staticNeedsRefresh: action.payload };
      
    case ActionType.UPDATE_TERMINAL_SIZE:
      return {
        ...state,
        terminalDisplayWidth: action.payload.width,
        terminalDisplayHeight: action.payload.height,
      };
      
    case ActionType.SET_HAS_COMPLETED_OPERATION:
      return { ...state, hasCompletedOperation: action.payload };
      
    case ActionType.CLEAR_COMPLETED_OPERATION:
      return { ...state, hasCompletedOperation: false };
      
    case ActionType.SET_ACTIVE_OPERATION:
      return { ...state, activeOperation: action.payload };
      
    case ActionType.UPDATE_OPERATION:
      if (!state.activeOperation) return state;
      return {
        ...state,
        activeOperation: { ...state.activeOperation, ...action.payload },
      };
      
    case ActionType.SET_USER_HANDOFF:
      return { ...state, userHandoffActive: action.payload };
      
    case ActionType.UPDATE_METRICS:
      return { ...state, operationMetrics: action.payload };
      
    case ActionType.ADD_RECENT_TARGET:
      const targets = [action.payload, ...state.recentTargets.filter(t => t !== action.payload)];
      return { ...state, recentTargets: targets.slice(0, 5) };
      
    case ActionType.INCREMENT_ERROR_COUNT:
      return { ...state, sessionErrorCount: state.sessionErrorCount + 1 };
      
    case ActionType.RESET_ERROR_COUNT:
      return { ...state, sessionErrorCount: 0 };
      
    case ActionType.SET_DOCKER_AVAILABLE:
      return { ...state, isDockerServiceAvailable: action.payload };
      
    case ActionType.UPDATE_CONTEXT_USAGE:
      return { ...state, contextUsage: action.payload };
      
    default:
      return state;
  }
}

// Initial state factory
function getInitialState(): ApplicationState {
  return {
    isInitialized: false,
    isConfigLoaded: false,
    sessionId: `session-${Date.now()}`,
    sessionErrorCount: 0,
    isFirstRunExperience: true,
    isInitializationFlowActive: false,
    hasUserDismissedInit: false,
    isDockerServiceAvailable: false,
    isTerminalVisible: false,
    staticKey: 0,
    staticNeedsRefresh: false,
    hasCompletedOperation: false,
    activeOperation: null,
    userHandoffActive: false,
    contextUsage: 0,
    operationMetrics: null,
    recentTargets: [],
    terminalDisplayHeight: process.stdout.rows || 24,
    terminalDisplayWidth: process.stdout.columns || 80,
  };
}

/**
 * Custom hook for managing application state
 */
export function useApplicationState() {
  const [state, dispatch] = useReducer(applicationReducer, getInitialState());
  
  // Refs for cleanup
  const cleanupFunctions = useRef<(() => void)[]>([]);
  
  // Actions - all useCallback calls must be at top level (Rules of Hooks)
  const initializeApp = (sessionId: string) => {
    dispatch({ type: ActionType.INITIALIZE_APP, payload: { sessionId } });
  };
  
  const setConfigLoaded = (loaded: boolean) => {
    dispatch({ type: ActionType.SET_CONFIG_LOADED, payload: loaded });
  };
  
  const setInitializationFlow = (active: boolean) => {
    dispatch({ type: ActionType.SET_INITIALIZATION_FLOW, payload: active });
  };
  
  const dismissInit = () => {
    dispatch({ type: ActionType.DISMISS_INIT });
  };
  
  const setTerminalVisible = (visible: boolean) => {
    dispatch({ type: ActionType.SET_TERMINAL_VISIBLE, payload: visible });
  };
  
  const refreshStatic = () => {
    dispatch({ type: ActionType.REFRESH_STATIC });
  };
  
  const setStaticNeedsRefresh = (needsRefresh: boolean) => {
    dispatch({ type: ActionType.SET_STATIC_NEEDS_REFRESH, payload: needsRefresh });
  };
  
  const updateTerminalSize = (width: number, height: number) => {
    dispatch({ type: ActionType.UPDATE_TERMINAL_SIZE, payload: { width, height } });
  };
  
  const setHasCompletedOperation = (completed: boolean) => {
    dispatch({ type: ActionType.SET_HAS_COMPLETED_OPERATION, payload: completed });
  };
  
  const clearCompletedOperation = () => {
    dispatch({ type: ActionType.CLEAR_COMPLETED_OPERATION });
  };
  
  const setActiveOperation = (operation: Operation | null) => {
    dispatch({ type: ActionType.SET_ACTIVE_OPERATION, payload: operation });
  };
  
  const updateOperation = (updates: Partial<Operation>) => {
    dispatch({ type: ActionType.UPDATE_OPERATION, payload: updates });
  };
  
  const setUserHandoff = (active: boolean) => {
    dispatch({ type: ActionType.SET_USER_HANDOFF, payload: active });
  };
  
  const updateMetrics = (metrics: any) => {
    dispatch({ type: ActionType.UPDATE_METRICS, payload: metrics });
  };
  
  const addRecentTarget = (target: string) => {
    dispatch({ type: ActionType.ADD_RECENT_TARGET, payload: target });
  };
  
  const incrementErrorCount = () => {
    dispatch({ type: ActionType.INCREMENT_ERROR_COUNT });
  };
  
  const resetErrorCount = () => {
    dispatch({ type: ActionType.RESET_ERROR_COUNT });
  };
  
  const setDockerAvailable = (available: boolean) => {
    dispatch({ type: ActionType.SET_DOCKER_AVAILABLE, payload: available });
  };
  
  const updateContextUsage = (usage: number) => {
    dispatch({ type: ActionType.UPDATE_CONTEXT_USAGE, payload: usage });
  };
  
  const registerCleanup = (cleanup: () => void) => {
    cleanupFunctions.current.push(cleanup);
  };

  // CRITICAL FIX: Use useMemo for actions object to prevent recreation
  const actions = useMemo(() => ({
    initializeApp,
    setConfigLoaded,
    setInitializationFlow,
    dismissInit,
    setTerminalVisible,
    refreshStatic,
    setStaticNeedsRefresh,
    updateTerminalSize,
    setHasCompletedOperation,
    clearCompletedOperation,
    setActiveOperation,
    updateOperation,
    setUserHandoff,
    updateMetrics,
    addRecentTarget,
    incrementErrorCount,
    resetErrorCount,
    setDockerAvailable,
    updateContextUsage,
    registerCleanup
  }), [
    initializeApp, setConfigLoaded, setInitializationFlow, dismissInit,
    setTerminalVisible, refreshStatic, setStaticNeedsRefresh, updateTerminalSize,
    setHasCompletedOperation, clearCompletedOperation,
    setActiveOperation, updateOperation, setUserHandoff, updateMetrics,
    addRecentTarget, incrementErrorCount, resetErrorCount, setDockerAvailable, 
    updateContextUsage, registerCleanup
  ]);
  
  // Cleanup on unmount
  useEffect(() => {
    return () => {
      cleanupFunctions.current.forEach(cleanup => cleanup());
    };
  }, []);
  
  // CRITICAL FIX: Use useMemo to prevent infinite re-renders
  // Without this, the return object gets recreated on every render, causing all consumers to re-render
  return useMemo(() => ({
    state,
    actions,
    dispatch,
  }), [state, actions, dispatch]);
}