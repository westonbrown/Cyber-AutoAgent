/**
 * Custom Keypress Hook for Cyber-AutoAgent
 * 
 * Provides robust keyboard handling that works across all execution modes:
 * - Python CLI mode
 * - Docker single-container mode  
 * - Docker full-stack mode
 * 
 * Based on production patterns from gemini-cli, this hook:
 * - Uses readline interface directly (bypassing React Ink limitations)
 * - Handles raw stdin data properly
 * - Works with both TTY and non-TTY modes
 * - Provides proper cleanup on unmount
 */

import { useEffect, useRef } from 'react';
import { useStdin } from 'ink';
import readline from 'readline';

export interface Key {
  name: string;
  ctrl: boolean;
  meta: boolean;
  shift: boolean;
  sequence: string;
}

/**
 * Custom keypress hook that bypasses React Ink's useInput limitations
 * 
 * @param onKeypress - Callback function executed on each keypress
 * @param options - Control options for the hook
 * @param options.isActive - Whether the hook should actively listen for input
 */
export function useKeypress(
  onKeypress: (key: Key) => void,
  { isActive }: { isActive: boolean }
) {
  const { stdin, setRawMode } = useStdin();
  const onKeypressRef = useRef(onKeypress);
  const rlRef = useRef<readline.Interface | null>(null);

  // Keep callback reference updated
  useEffect(() => {
    onKeypressRef.current = onKeypress;
  }, [onKeypress]);

  useEffect(() => {
    if (!isActive) {
      return;
    }

    // DO NOT enable raw mode - let React Ink handle stdin mode
    // Raw mode would conflict with text input components
    
    // Handle keypress events
    const handleKeypress = (_: unknown, key: Key) => {
      // ONLY handle specific keys we care about
      
      // Special handling for escape key
      if (key.name === 'escape' || key.sequence === '\x1B' || key.sequence === '\u001B') {
        onKeypressRef.current({
          name: 'escape',
          ctrl: false,
          meta: false,
          shift: false,
          sequence: '\x1B'
        });
        return;
      }

      // Special handling for Ctrl+C
      if (key.ctrl && key.name === 'c') {
        onKeypressRef.current({
          name: 'c',
          ctrl: true,
          meta: false,
          shift: false,
          sequence: '\x03'
        });
        return;
      }

      // Special handling for Ctrl+L (clear screen)
      if (key.ctrl && key.name === 'l') {
        onKeypressRef.current({
          name: 'l',
          ctrl: true,
          meta: false,
          shift: false,
          sequence: '\x0C'
        });
        return;
      }

      // DO NOT pass through other keys - they should be handled by text inputs
      // This prevents our global handler from interfering with normal typing
    };

    // Fallback handler for raw data (handles non-TTY and edge cases)
    const handleRawData = (data: Buffer) => {
      const input = data.toString();
      
      // ONLY handle special keys we care about
      // Don't intercept normal typing
      
      // Check for escape sequence
      if (input === '\x1B' || input === '\u001B' || input.charCodeAt(0) === 27) {
        handleKeypress(undefined, {
          name: 'escape',
          ctrl: false,
          meta: false,
          shift: false,
          sequence: '\x1B'
        });
        return;
      }

      // Check for Ctrl+C
      if (input === '\x03' || input.charCodeAt(0) === 3) {
        handleKeypress(undefined, {
          name: 'c',
          ctrl: true,
          meta: false,
          shift: false,
          sequence: '\x03'
        });
        return;
      }

      // Check for Ctrl+L (clear screen)
      if (input === '\x0C' || input.charCodeAt(0) === 12) {
        handleKeypress(undefined, {
          name: 'l',
          ctrl: true,
          meta: false,
          shift: false,
          sequence: '\x0C'
        });
        return;
      }

      // DO NOT process other input - let it pass through to text inputs
      // This prevents interference with normal typing
    };

    // Create readline interface
    const rl = readline.createInterface({
      input: stdin,
      escapeCodeTimeout: 50 // Quick escape detection
    });
    rlRef.current = rl;

    // Enable keypress events
    readline.emitKeypressEvents(stdin, rl);

    // Listen for keypress events (works in TTY mode)
    stdin.on('keypress', handleKeypress);

    // Only listen for raw data in non-TTY mode (Docker/headless)
    // In TTY mode, keypress events are sufficient
    if (!stdin.isTTY) {
      stdin.on('data', handleRawData);
    }

    // Cleanup function
    return () => {
      stdin.removeListener('keypress', handleKeypress);
      
      if (!stdin.isTTY) {
        stdin.removeListener('data', handleRawData);
      }
      
      if (rlRef.current) {
        rlRef.current.close();
        rlRef.current = null;
      }
    };
  }, [isActive, stdin, setRawMode]);

  // Return a method to manually trigger escape if needed
  return {
    triggerEscape: () => {
      onKeypressRef.current({
        name: 'escape',
        ctrl: false,
        meta: false,
        shift: false,
        sequence: '\x1B'
      });
    }
  };
}