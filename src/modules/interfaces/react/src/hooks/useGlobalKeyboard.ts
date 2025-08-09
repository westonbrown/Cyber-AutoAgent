/**
 * Global Keyboard Handler Hook
 * 
 * Handles only global shortcuts (ESC, Ctrl+C, Ctrl+L) without interfering
 * with normal text input operations.
 */

import { useInput } from 'ink';
import { useEffect } from 'react';

export interface GlobalKeyboardOptions {
  onEscape?: () => void;
  onCtrlC?: () => void;
  onCtrlL?: () => void;
  isActive?: boolean;
}

/**
 * Hook for handling global keyboard shortcuts
 * Uses React Ink's useInput to avoid conflicts with text inputs
 */
export function useGlobalKeyboard({
  onEscape,
  onCtrlC,
  onCtrlL,
  isActive = true
}: GlobalKeyboardOptions) {
  
  // Only use keyboard input if we're in a TTY environment
  const isTTY = process.stdin.isTTY;
  
  // Use conditional hook pattern - always call useInput but make it inactive in non-TTY
  useInput((input, key) => {
    if (!isActive || !isTTY) return;
    
    // Handle Escape key
    if (key.escape && onEscape) {
      onEscape();
      return;
    }
    
    // Handle Ctrl+C
    if (key.ctrl && input === 'c' && onCtrlC) {
      onCtrlC();
      return;
    }
    
    // Handle Ctrl+L
    if (key.ctrl && input === 'l' && onCtrlL) {
      onCtrlL();
      return;
    }
    
    // All other input is ignored - let text inputs handle it
  }, { isActive: isActive && isTTY });
}