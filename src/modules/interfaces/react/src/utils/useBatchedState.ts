/**
 * Batched State Updates Hook
 * 
 * Optimizes React performance by batching multiple state updates
 * within a time window to reduce re-renders.
 */

import React, { useRef, useCallback, useState, useEffect } from 'react';

interface BatchedUpdate<T> {
  updater: (prev: T) => T;
  timestamp: number;
}

/**
 * useBatchedState - Batches state updates within a time window
 * 
 * Benefits:
 * - Reduces re-renders from 100+ per second to ~20 per second
 * - Maintains UI responsiveness
 * - Prevents React reconciliation overhead
 * 
 * @param initialState - Initial state value
 * @param batchWindowMs - Time window for batching (default 50ms)
 * @param maxBatchSize - Maximum updates to batch before forcing flush
 */
export function useBatchedState<T>(
  initialState: T,
  batchWindowMs: number = 50,
  maxBatchSize: number = 100
): [T, (updater: React.SetStateAction<T>) => void, () => void] {
  const [state, setStateInternal] = useState<T>(initialState);
  const pendingUpdates = useRef<BatchedUpdate<T>[]>([]);
  const flushTimer = useRef<NodeJS.Timeout | null>(null);
  const isFlushingRef = useRef(false);

  // Flush all pending updates
  const flush = useCallback(() => {
    if (isFlushingRef.current || pendingUpdates.current.length === 0) {
      return;
    }

    isFlushingRef.current = true;
    const updates = pendingUpdates.current;
    pendingUpdates.current = [];

    // Clear any pending timer
    if (flushTimer.current) {
      clearTimeout(flushTimer.current);
      flushTimer.current = null;
    }

    // Apply all updates in a single state update
    setStateInternal(prevState => {
      let newState = prevState;
      for (const update of updates) {
        newState = update.updater(newState);
      }
      return newState;
    });

    isFlushingRef.current = false;
  }, []);

  // Batched setState function
  const setState = useCallback((updater: React.SetStateAction<T>) => {
    const updateFn: (prev: T) => T = 
      typeof updater === 'function' 
        ? updater as (prev: T) => T
        : () => updater;

    pendingUpdates.current.push({
      updater: updateFn,
      timestamp: Date.now()
    });

    // Force flush if batch is too large
    if (pendingUpdates.current.length >= maxBatchSize) {
      flush();
      return;
    }

    // Schedule flush if not already scheduled
    if (!flushTimer.current) {
      flushTimer.current = setTimeout(flush, batchWindowMs);
    }
  }, [flush, batchWindowMs, maxBatchSize]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (flushTimer.current) {
        clearTimeout(flushTimer.current);
        flush(); // Flush any pending updates
      }
    };
  }, [flush]);

  return [state, setState, flush];
}

/**
 * useBatchedReducer - Batched version of useReducer
 * 
 * Similar to useBatchedState but for reducer pattern
 */
export function useBatchedReducer<S, A>(
  reducer: (state: S, action: A) => S,
  initialState: S,
  batchWindowMs: number = 50,
  maxBatchSize: number = 100
): [S, (action: A) => void, () => void] {
  const [state, setState, flush] = useBatchedState(initialState, batchWindowMs, maxBatchSize);

  const dispatch = useCallback((action: A) => {
    setState(prev => reducer(prev, action));
  }, [setState, reducer]);

  return [state, dispatch, flush];
}

/**
 * useEventBatcher - Specialized batcher for event streams
 * 
 * Optimized for handling high-frequency event streams like:
 * - Real-time logs
 * - WebSocket messages
 * - Server-sent events
 */
export function useEventBatcher<T>(
  onBatch: (events: T[]) => void,
  batchWindowMs: number = 50,
  maxBatchSize: number = 50
) {
  const batchRef = useRef<T[]>([]);
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  const flush = useCallback(() => {
    if (batchRef.current.length === 0) return;

    const batch = batchRef.current;
    batchRef.current = [];
    
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }

    onBatch(batch);
  }, [onBatch]);

  const addEvent = useCallback((event: T) => {
    batchRef.current.push(event);

    // Force flush if batch is full
    if (batchRef.current.length >= maxBatchSize) {
      flush();
      return;
    }

    // Schedule flush
    if (!timerRef.current) {
      timerRef.current = setTimeout(flush, batchWindowMs);
    }
  }, [flush, batchWindowMs, maxBatchSize]);

  // Cleanup
  useEffect(() => {
    return () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current);
        flush();
      }
    };
  }, [flush]);

  return { addEvent, flush };
}

/**
 * useAnimationFrameBatcher - Uses requestAnimationFrame for smooth updates
 * 
 * Best for:
 * - Animations
 * - Smooth scrolling
 * - Visual transitions
 */
export function useAnimationFrameBatcher<T>(
  onBatch: (items: T[]) => void,
  maxBatchSize: number = 100
) {
  const batchRef = useRef<T[]>([]);
  const rafRef = useRef<number | null>(null);

  const flush = useCallback(() => {
    if (batchRef.current.length === 0) return;

    const batch = batchRef.current;
    batchRef.current = [];
    
    if (rafRef.current) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }

    onBatch(batch);
  }, [onBatch]);

  const addItem = useCallback((item: T) => {
    batchRef.current.push(item);

    // Force flush if batch is full
    if (batchRef.current.length >= maxBatchSize) {
      flush();
      return;
    }

    // Schedule flush on next animation frame
    if (!rafRef.current) {
      rafRef.current = requestAnimationFrame(flush);
    }
  }, [flush, maxBatchSize]);

  // Cleanup
  useEffect(() => {
    return () => {
      if (rafRef.current) {
        cancelAnimationFrame(rafRef.current);
        flush();
      }
    };
  }, [flush]);

  return { addItem, flush };
}