/**
 * useDebouncedState Hook
 * 
 * Prevents rapid state updates that cause UI flicker and duplicate rendering.
 * Essential for fixing the test capture issues identified.
 */

import { useState, useCallback, useRef, useEffect } from 'react';

export function useDebouncedState<T>(
  initialValue: T,
  delay: number = 100
): [T, (value: T) => void, () => void] {
  const [state, setState] = useState<T>(initialValue);
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);
  const pendingValueRef = useRef<T | null>(null);

  const setDebouncedState = useCallback((value: T) => {
    // Clear any existing timeout
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }

    // Store pending value
    pendingValueRef.current = value;

    // Set new timeout
    timeoutRef.current = setTimeout(() => {
      setState(value);
      pendingValueRef.current = null;
      timeoutRef.current = null;
    }, delay);
  }, [delay]);

  const flush = useCallback(() => {
    if (timeoutRef.current && pendingValueRef.current !== null) {
      clearTimeout(timeoutRef.current);
      setState(pendingValueRef.current);
      pendingValueRef.current = null;
      timeoutRef.current = null;
    }
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, []);

  return [state, setDebouncedState, flush];
}

export default useDebouncedState;