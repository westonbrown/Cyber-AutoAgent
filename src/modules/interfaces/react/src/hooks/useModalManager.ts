/**
 * Centralized Modal Management Hook
 * 
 * Provides a unified interface for managing all modal states and transitions
 * in the application. Uses professional screen clearing techniques to 
 * prevent UI artifacts and context bleed.
 * 
 * Features:
 * - Single source of truth for modal state
 * - Professional screen transition handling
 * - Type-safe modal management
 * - Event-driven architecture support
 */

import { useState, useCallback, useRef } from 'react';
import { useStdout } from 'ink';
import ansiEscapes from 'ansi-escapes';

export enum ModalType {
  NONE = 'none',
  CONFIG = 'config',
  MEMORY_SEARCH = 'memorySearch',
  MODULE_SELECTOR = 'moduleSelector',
  SAFETY_WARNING = 'safetyWarning',
  INITIALIZATION = 'initialization',
  DOCUMENTATION = 'documentation'
}

interface ModalContext {
  // Configuration modal
  configError?: string;
  
  // Safety warning modal
  pendingExecution?: {
    module: string;
    target: string;
    objective?: string;
  };
  
  // Module selector
  onModuleSelect?: (moduleName: string) => void;
  
  // Documentation viewer
  documentIndex?: number;
}

interface UseModalManagerResult {
  // Current active modal
  activeModal: ModalType;
  
  // Modal context data
  modalContext: ModalContext;
  
  // Static key for forcing re-renders
  staticKey: number;
  
  // Modal control functions
  openModal: (type: ModalType, context?: Partial<ModalContext>) => void;
  closeModal: () => void;
  refreshStatic: () => void;
  refreshStaticOnly: () => void;
  
  // Specific modal helpers
  openConfig: (error?: string) => void;
  openMemorySearch: () => void;
  openModuleSelector: (onSelect: (name: string) => void) => void;
  openSafetyWarning: (execution: ModalContext['pendingExecution']) => void;
  openDocumentation: (docIndex?: number) => void;
  
  // Check if specific modal is open
  isModalOpen: (type: ModalType) => boolean;
}

export const useModalManager = (): UseModalManagerResult => {
  const [activeModal, setActiveModal] = useState<ModalType>(ModalType.NONE);
  const [modalContext, setModalContext] = useState<ModalContext>({});
  const [staticKey, setStaticKey] = useState(0);
  const { stdout } = useStdout();
  
  
  // Screen refresh function - only clear terminal when truly needed  
  const refreshStatic = useCallback(() => {
    // Only clear terminal if we're not in a modal that should preserve content
    const shouldClearTerminal = activeModal === ModalType.NONE || 
                               activeModal === ModalType.INITIALIZATION || 
                               activeModal === ModalType.DOCUMENTATION;
    
    if (shouldClearTerminal) {
      stdout.write(ansiEscapes.clearTerminal);
    }
    setStaticKey(prev => prev + 1);
  }, [stdout, activeModal]);
  
  // Static key refresh only
  const refreshStaticOnly = useCallback(() => {
    setStaticKey(prev => prev + 1);
  }, []);
  
  // Simplified modal control
  const openModal = useCallback((type: ModalType, context?: Partial<ModalContext>) => {
    // Update modal state
    setActiveModal(type);
    if (context) {
      setModalContext(prev => ({ ...prev, ...context }));
    }
    
    // Only clear terminal for modals that need a fresh screen
    // Config editor can overlay without clearing to prevent flicker
    const needsFullClear = type === ModalType.INITIALIZATION || type === ModalType.DOCUMENTATION;
    if (needsFullClear) {
      stdout.write(ansiEscapes.clearTerminal);
    }
    
    // Always increment static key to trigger re-render
    setStaticKey(prev => prev + 1);
  }, [stdout]);
  
  const closeModal = useCallback(() => {
    const previousModal = activeModal;
    
    // Clear modal state
    setActiveModal(ModalType.NONE);
    setModalContext({});
    
    // Always clear terminal when closing modals to prevent overlay remnants
    // The flicker issue should be resolved by reducing unnecessary opens/closes
    stdout.write(ansiEscapes.clearTerminal);
    
    // Always increment static key to trigger re-render
    setStaticKey(prev => prev + 1);
  }, [stdout, activeModal]);
  
  // Specific modal helpers for type safety and convenience
  const openConfig = useCallback((error?: string) => {
    openModal(ModalType.CONFIG, { configError: error });
  }, [openModal]);
  
  const openMemorySearch = useCallback(() => {
    openModal(ModalType.MEMORY_SEARCH);
  }, [openModal]);
  
  const openModuleSelector = useCallback((onSelect: (name: string) => void) => {
    openModal(ModalType.MODULE_SELECTOR, { onModuleSelect: onSelect });
  }, [openModal]);
  
  const openSafetyWarning = useCallback((execution: ModalContext['pendingExecution']) => {
    openModal(ModalType.SAFETY_WARNING, { pendingExecution: execution });
  }, [openModal]);
  
  const openDocumentation = useCallback((docIndex?: number) => {
    openModal(ModalType.DOCUMENTATION, { documentIndex: docIndex });
  }, [openModal]);
  
  const isModalOpen = useCallback((type: ModalType) => {
    return activeModal === type;
  }, [activeModal]);
  
  return {
    activeModal,
    modalContext,
    staticKey,
    openModal,
    closeModal,
    refreshStatic,
    refreshStaticOnly,
    openConfig,
    openMemorySearch,
    openModuleSelector,
    openSafetyWarning,
    openDocumentation,
    isModalOpen
  };
};