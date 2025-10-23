/**
 * useCommandHistory - Hook for managing command input history
 *
 * Provides Up/Down arrow navigation through command history with
 * configurable limits and persistence support.
 */

import { useState, useCallback, useRef, useEffect } from 'react';

export interface CommandHistoryOptions {
  /** Maximum number of history items to keep */
  maxItems?: number;
  /** Enable history (can be toggled at runtime) */
  enabled?: boolean;
  /** Initial history items */
  initialHistory?: string[];
}

export interface CommandHistoryResult {
  /** Add a command to history */
  addCommand: (command: string) => void;
  /** Navigate to previous command */
  navigatePrevious: () => string | null;
  /** Navigate to next command */
  navigateNext: () => string | null;
  /** Get current history item */
  getCurrentItem: () => string | null;
  /** Clear all history */
  clearHistory: () => void;
  /** Get all history items */
  getHistory: () => string[];
  /** Current position in history */
  historyPosition: number;
  /** Whether history is enabled */
  enabled: boolean;
}

/**
 * Command history hook
 */
export function useCommandHistory(
  options: CommandHistoryOptions = {}
): CommandHistoryResult {
  const { maxItems = 50, enabled = true, initialHistory = [] } = options;

  const [history, setHistory] = useState<string[]>(initialHistory);
  const [position, setPosition] = useState<number>(-1);
  const currentInputRef = useRef<string>('');

  /**
   * Add command to history
   */
  const addCommand = useCallback(
    (command: string) => {
      if (!enabled || !command.trim()) return;

      setHistory(prev => {
        // Don't add if it's the same as the last command
        if (prev.length > 0 && prev[prev.length - 1] === command) {
          return prev;
        }

        // Add to history and trim if needed
        const newHistory = [...prev, command];
        if (newHistory.length > maxItems) {
          return newHistory.slice(-maxItems);
        }
        return newHistory;
      });

      // Reset position after adding
      setPosition(-1);
      currentInputRef.current = '';
    },
    [enabled, maxItems]
  );

  /**
   * Navigate to previous command (Up arrow)
   */
  const navigatePrevious = useCallback((): string | null => {
    if (!enabled || history.length === 0) return null;

    setPosition(prev => {
      const newPosition = prev === -1 ? history.length - 1 : Math.max(0, prev - 1);
      return newPosition;
    });

    const newPosition = position === -1 ? history.length - 1 : Math.max(0, position - 1);
    return history[newPosition] || null;
  }, [enabled, history, position]);

  /**
   * Navigate to next command (Down arrow)
   */
  const navigateNext = useCallback((): string | null => {
    if (!enabled || history.length === 0) return null;

    setPosition(prev => {
      if (prev === -1) return -1;
      const newPosition = prev + 1;
      return newPosition >= history.length ? -1 : newPosition;
    });

    const newPosition = position + 1;
    if (newPosition >= history.length) {
      return currentInputRef.current || null;
    }
    return history[newPosition] || null;
  }, [enabled, history, position]);

  /**
   * Get current history item
   */
  const getCurrentItem = useCallback((): string | null => {
    if (!enabled || position === -1) return null;
    return history[position] || null;
  }, [enabled, history, position]);

  /**
   * Clear all history
   */
  const clearHistory = useCallback(() => {
    setHistory([]);
    setPosition(-1);
    currentInputRef.current = '';
  }, []);

  /**
   * Get all history items
   */
  const getHistory = useCallback(() => {
    return [...history];
  }, [history]);

  // Reset position when history changes
  useEffect(() => {
    if (!enabled) {
      setPosition(-1);
    }
  }, [enabled]);

  return {
    addCommand,
    navigatePrevious,
    navigateNext,
    getCurrentItem,
    clearHistory,
    getHistory,
    historyPosition: position,
    enabled
  };
}

/**
 * Persist history to localStorage
 */
export function usePersistentCommandHistory(
  storageKey: string,
  options: CommandHistoryOptions = {}
): CommandHistoryResult {
  // Load initial history from localStorage
  const loadHistory = (): string[] => {
    try {
      const stored = localStorage.getItem(storageKey);
      return stored ? JSON.parse(stored) : [];
    } catch {
      return [];
    }
  };

  const initialHistory = loadHistory();
  const history = useCommandHistory({ ...options, initialHistory });

  // Save history to localStorage whenever it changes
  useEffect(() => {
    try {
      localStorage.setItem(storageKey, JSON.stringify(history.getHistory()));
    } catch {
      // Silently fail if localStorage is not available
    }
  }, [history, storageKey]);

  return history;
}
