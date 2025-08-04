/**
 * Modal Registry Component
 * 
 * Centralized component for rendering all modals based on the active modal type.
 * This ensures consistent modal behavior and simplifies the main App component.
 */

import React from 'react';
import { Box } from 'ink';
import { ConfigEditorV2 } from './ConfigEditorV2.js';
import { MemorySearch } from './MemorySearch.js';
import { ModuleSelector } from './ModuleSelector.js';
import { SafetyWarning } from './SafetyWarning.js';
import { InitializationFlow } from './InitializationFlow.js';
import { ModalType } from '../hooks/useModalManager.js';
import { AssessmentFlow } from '../services/AssessmentFlow.js';

interface ModalRegistryProps {
  activeModal: ModalType;
  modalContext: any;
  onClose: () => void;
  terminalWidth: number;
  
  // Additional props for specific modals
  assessmentFlowManager?: AssessmentFlow;
  addOperationHistoryEntry?: (type: any, content: string, operation?: any) => void;
  onSafetyConfirm?: () => void;
  isFirstRunExperience?: boolean;
  setIsFirstRunExperience?: (value: boolean) => void;
  setIsConfigurationModalOpen?: (value: boolean) => void;
}

export const ModalRegistry: React.FC<ModalRegistryProps> = ({
  activeModal,
  modalContext,
  onClose,
  terminalWidth,
  assessmentFlowManager,
  addOperationHistoryEntry,
  onSafetyConfirm,
  isFirstRunExperience,
  setIsFirstRunExperience,
  setIsConfigurationModalOpen
}) => {
  // Don't render anything if no modal is active
  if (activeModal === ModalType.NONE) {
    return null;
  }
  
  // Common modal wrapper for consistent styling
  const ModalWrapper: React.FC<{ children: React.ReactNode }> = ({ children }) => (
    <Box flexDirection="column" width="90%">
      {children}
    </Box>
  );
  
  switch (activeModal) {
    case ModalType.CONFIG:
      return (
        <ModalWrapper>
          <ConfigEditorV2 
            onClose={() => {
              onClose();
              // Show welcome message after config if first run
              if (isFirstRunExperience) {
                addOperationHistoryEntry?.('info', 'Configuration complete! Type /help for commands or try: scan example.com');
                setIsFirstRunExperience?.(false);
              }
            }}
          />
        </ModalWrapper>
      );
      
    case ModalType.MEMORY_SEARCH:
      return (
        <ModalWrapper>
          <MemorySearch onClose={onClose} />
        </ModalWrapper>
      );
      
    case ModalType.MODULE_SELECTOR:
      return (
        <ModalWrapper>
          <ModuleSelector 
            onClose={onClose}
            onSelect={(moduleName) => {
              onClose();
              if (modalContext.onModuleSelect) {
                modalContext.onModuleSelect(moduleName);
              }
            }}
          />
        </ModalWrapper>
      );
      
    case ModalType.SAFETY_WARNING:
      return (
        <ModalWrapper>
          {modalContext.pendingExecution && (
            <SafetyWarning 
              target={modalContext.pendingExecution.target}
              module={modalContext.pendingExecution.module}
              onConfirm={() => {
                onClose();
                onSafetyConfirm?.();
              }}
              onCancel={onClose}
            />
          )}
        </ModalWrapper>
      );
      
    case ModalType.INITIALIZATION:
      return (
        <ModalWrapper>
          <InitializationFlow 
            onComplete={() => {
              onClose();
              // Show config editor after initialization
              setIsConfigurationModalOpen?.(true);
            }}
          />
        </ModalWrapper>
      );
      
    default:
      return null;
  }
};