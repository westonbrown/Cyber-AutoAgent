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
  onAssessmentCancel: () => void; // Kill switch handler with notification
  onScreenClear: () => void;
  onEscapeExit?: () => void; // Optional ESC handler
  allowGlobalEscape?: boolean; // Allow ESC even when terminal is not interactive
}

export function useKeyboardHandlers({
  activeOperation,
  isTerminalInteractive,
  onAssessmentPause,
  onAssessmentCancel,
  onScreenClear,
  onEscapeExit,
  allowGlobalEscape = false
}: KeyboardHandlersProps) {
  const { exit } = useApp();

  const handleTerminalInput = useCallback((input: string, key: any) => {
    if (!isTerminalInteractive) return;
    
    // ESC: Kill switch for running operations, exit otherwise
    if (key.escape) {
      if (activeOperation?.status === 'running') {
        onAssessmentCancel(); // Use kill switch with notification
      } else {
        // Always call onEscapeExit if provided, otherwise default exit
        if (onEscapeExit) {
          onEscapeExit();
        } else {
          // Fallback behavior
          console.log('\n🔴 Exiting Cyber-AutoAgent... Goodbye!');
          exit();
        }
      }
      return;
    }
    
    // Ctrl+C: Clear input or pause assessment (documented behavior)
    if (key.ctrl && input === 'c') {
      if (activeOperation?.status === 'running') {
        onAssessmentPause();
      } else {
        // If no operation running, exit gracefully
        console.log('\n🔴 Exiting Cyber-AutoAgent... Goodbye!');
        exit();
      }
      return;
    }
    
    // Ctrl+L: Clear screen (documented behavior)
    if (key.ctrl && input === 'l') {
      onScreenClear();
      return;
    }
  }, [isTerminalInteractive, activeOperation, onAssessmentPause, onAssessmentCancel, onScreenClear, onEscapeExit, exit]);

  // Use keyboard handler with higher priority for global shortcuts
  useInput(handleTerminalInput, { isActive: isTerminalInteractive });
  
  // Global ESC handler that works even when terminal is not interactive
  const handleGlobalEscape = useCallback((input: string, key: any) => {
    if (!allowGlobalEscape) return;
    
    // Only handle ESC key for global exit
    if (key.escape) {
      if (activeOperation?.status === 'running') {
        onAssessmentCancel(); // Use kill switch with notification
      } else {
        if (onEscapeExit) {
          onEscapeExit();
        } else {
          console.log('\n🔴 Exiting Cyber-AutoAgent... Goodbye!');
          exit();
        }
      }
      return;
    }
  }, [allowGlobalEscape, activeOperation, onAssessmentCancel, onEscapeExit, exit]);
  
  // Global escape handler - always active when allowGlobalEscape is true
  useInput(handleGlobalEscape, { isActive: allowGlobalEscape && !isTerminalInteractive });
}