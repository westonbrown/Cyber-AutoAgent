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
  isTerminalVisible: boolean;
  onAssessmentPause: () => void;
  onAssessmentCancel: () => void;
  onScreenClear: () => void;
}

export function useKeyboardHandlers({
  activeOperation,
  isTerminalInteractive,
  isTerminalVisible,
  onAssessmentPause,
  onAssessmentCancel,
  onScreenClear
}: KeyboardHandlersProps) {
  const { exit } = useApp();

  const handleTerminalInput = useCallback((input: string, key: any) => {
    // ESC: Kill switch - Match original working behavior exactly
    if (key.escape) {
      if (isTerminalVisible && activeOperation?.status === 'running') {
        // Immediately cancel current operation and kill container
        onAssessmentCancel();
      } else {
        // Exit application when not in modal or running operation
        exit();
      }
      return;
    }
    
    // For other shortcuts, respect isTerminalInteractive
    if (!isTerminalInteractive) return;
    
    // Ctrl+C: Clear input or stop assessment (documented behavior)
    if (key.ctrl && input === 'c') {
      if (activeOperation?.status === 'running') {
        onAssessmentPause(); // This now properly stops the execution service
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
  }, [isTerminalInteractive, isTerminalVisible, activeOperation, onAssessmentPause, onAssessmentCancel, onScreenClear, exit]);

  // Keep keyboard handler active based on TTY availability (matching working version)
  const isKeyboardActive = process.stdin.isTTY;
  useInput(handleTerminalInput, { isActive: isKeyboardActive });
}