/**
 * Keyboard Handlers Hook
 * 
 * Extracts keyboard handling logic from App.tsx to reduce complexity.
 * Implements documented keyboard shortcuts: Ctrl+C for pause/clear, Ctrl+L for screen clear.
 */

import { useCallback } from 'react';
import { useInput, useApp } from 'ink';
import { Operation } from '../services/OperationManager.js';

interface KeyboardHandlersProps {
  activeOperation: Operation | null;
  isTerminalInteractive: boolean;
  onAssessmentPause: () => void;
  onScreenClear: () => void;
}

export function useKeyboardHandlers({
  activeOperation,
  isTerminalInteractive,
  onAssessmentPause,
  onScreenClear
}: KeyboardHandlersProps) {
  const { exit } = useApp();

  const handleTerminalInput = useCallback((input: string, key: any) => {
    if (!isTerminalInteractive) return;
    
    // Ctrl+C: Clear input or pause assessment (documented behavior)
    if (key.ctrl && input === 'c') {
      if (activeOperation?.status === 'running') {
        onAssessmentPause();
      } else {
        // If no operation running, exit gracefully
        exit();
      }
      return;
    }
    
    // Ctrl+L: Clear screen (documented behavior)
    if (key.ctrl && input === 'l') {
      onScreenClear();
      return;
    }
  }, [isTerminalInteractive, activeOperation, onAssessmentPause, onScreenClear, exit]);

  // Use keyboard handler
  useInput(handleTerminalInput, { isActive: isTerminalInteractive });
}