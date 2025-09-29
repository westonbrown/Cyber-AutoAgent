/**
 * Optimized Event Store for High-Performance Event Streaming
 * 
 * Uses chunked arrays to avoid O(n) spreading operations.
 * Provides O(1) append and efficient iteration.
 */

import React from 'react';
import { DisplayStreamEvent } from '../components/StreamDisplay.js';

// Chunk size for internal storage - balance between memory and performance
const CHUNK_SIZE = 100;
const MAX_EVENTS = 10000; // Maximum events to keep in memory

/**
 * EventStore - Efficient append-only event storage
 * 
 * Instead of [...prev, newEvent] which is O(n), this uses chunked arrays
 * for O(1) append operations and efficient memory usage.
 */
export class EventStore {
  private chunks: DisplayStreamEvent[][] = [];
  private currentChunk: DisplayStreamEvent[] = [];
  private totalCount = 0;
  private maxEvents: number;

  constructor(maxEvents = MAX_EVENTS) {
    this.maxEvents = maxEvents;
  }

  /**
   * Append a single event - O(1) operation
   */
  append(event: DisplayStreamEvent): void {
    // Add to current chunk
    this.currentChunk.push(event);
    this.totalCount++;

    // Start new chunk if current is full
    if (this.currentChunk.length >= CHUNK_SIZE) {
      this.chunks.push(this.currentChunk);
      this.currentChunk = [];
      
      // Trim old chunks if over limit
      this.trimToMaxSize();
    }
  }

  /**
   * Append multiple events efficiently
   */
  appendBatch(events: DisplayStreamEvent[]): void {
    for (const event of events) {
      this.append(event);
    }
  }

  /**
   * Get all events as array - only when needed for rendering
   */
  toArray(): DisplayStreamEvent[] {
    // Only flatten when necessary
    const result: DisplayStreamEvent[] = [];
    
    // Add completed chunks
    for (const chunk of this.chunks) {
      result.push(...chunk);
    }
    
    // Add current chunk
    result.push(...this.currentChunk);
    
    return result;
  }

  /**
   * Get recent events without copying all data
   */
  getRecent(count: number): DisplayStreamEvent[] {
    const total = this.totalCount;
    if (count >= total) {
      return this.toArray();
    }

    const result: DisplayStreamEvent[] = [];
    const needed = Math.min(count, total);
    
    // Start from current chunk and work backwards
    let remaining = needed;
    
    // Take from current chunk first
    if (this.currentChunk.length > 0) {
      const fromCurrent = Math.min(remaining, this.currentChunk.length);
      const startIdx = Math.max(0, this.currentChunk.length - fromCurrent);
      result.unshift(...this.currentChunk.slice(startIdx));
      remaining -= fromCurrent;
    }
    
    // Take from previous chunks if needed
    for (let i = this.chunks.length - 1; i >= 0 && remaining > 0; i--) {
      const chunk = this.chunks[i];
      const fromChunk = Math.min(remaining, chunk.length);
      const startIdx = Math.max(0, chunk.length - fromChunk);
      result.unshift(...chunk.slice(startIdx));
      remaining -= fromChunk;
    }
    
    return result;
  }

  /**
   * Get events for a specific range (for virtualization)
   */
  getRange(start: number, end: number): DisplayStreamEvent[] {
    const result: DisplayStreamEvent[] = [];
    let currentIndex = 0;

    // Iterate through chunks efficiently
    for (const chunk of this.chunks) {
      const chunkEnd = currentIndex + chunk.length;
      
      if (chunkEnd > start && currentIndex < end) {
        const startInChunk = Math.max(0, start - currentIndex);
        const endInChunk = Math.min(chunk.length, end - currentIndex);
        result.push(...chunk.slice(startInChunk, endInChunk));
      }
      
      currentIndex = chunkEnd;
      if (currentIndex >= end) break;
    }

    // Check current chunk if needed
    if (currentIndex < end) {
      const startInChunk = Math.max(0, start - currentIndex);
      const endInChunk = Math.min(this.currentChunk.length, end - currentIndex);
      if (startInChunk < endInChunk) {
        result.push(...this.currentChunk.slice(startInChunk, endInChunk));
      }
    }

    return result;
  }

  /**
   * Clear all events
   */
  clear(): void {
    this.chunks = [];
    this.currentChunk = [];
    this.totalCount = 0;
  }

  /**
   * Get total event count
   */
  get count(): number {
    return this.totalCount;
  }

  /**
   * Trim old events to stay under max size
   */
  private trimToMaxSize(): void {
    if (this.totalCount <= this.maxEvents) return;

    const toRemove = this.totalCount - this.maxEvents;
    let removed = 0;

    // Remove complete chunks from the beginning
    while (removed < toRemove && this.chunks.length > 0) {
      const firstChunk = this.chunks[0];
      if (removed + firstChunk.length <= toRemove) {
        // Remove entire chunk
        removed += firstChunk.length;
        this.chunks.shift();
      } else {
        // Partially trim first chunk
        const trimCount = toRemove - removed;
        this.chunks[0] = firstChunk.slice(trimCount);
        removed += trimCount;
      }
    }

    this.totalCount -= removed;
  }

  /**
   * Create a snapshot for immutable rendering
   */
  snapshot(): ReadonlyArray<DisplayStreamEvent> {
    return Object.freeze(this.toArray());
  }

  /**
   * Split into completed and active events
   */
  split(activeCount: number): {
    completed: DisplayStreamEvent[];
    active: DisplayStreamEvent[];
  } {
    const total = this.totalCount;
    
    if (activeCount >= total) {
      return {
        completed: [],
        active: this.toArray()
      };
    }

    const completedCount = total - activeCount;
    
    return {
      completed: this.getRange(0, completedCount),
      active: this.getRange(completedCount, total)
    };
  }
}

/**
 * React Hook for using EventStore
 */
export function useEventStore(maxEvents = MAX_EVENTS) {
  const storeRef = React.useRef(new EventStore(maxEvents));
  const [version, setVersion] = React.useState(0);

  const append = React.useCallback((event: DisplayStreamEvent) => {
    storeRef.current.append(event);
    setVersion(v => v + 1);
  }, []);

  const appendBatch = React.useCallback((events: DisplayStreamEvent[]) => {
    storeRef.current.appendBatch(events);
    setVersion(v => v + 1);
  }, []);

  const clear = React.useCallback(() => {
    storeRef.current.clear();
    setVersion(v => v + 1);
  }, []);

  const getEvents = React.useCallback(() => {
    return storeRef.current.toArray();
  }, [version]); // Depend on version to re-compute when changed

  const getRecent = React.useCallback((count: number) => {
    return storeRef.current.getRecent(count);
  }, [version]);

  const split = React.useCallback((activeCount: number) => {
    return storeRef.current.split(activeCount);
  }, [version]);

  return {
    append,
    appendBatch,
    clear,
    getEvents,
    getRecent,
    split,
    count: storeRef.current.count
  };
}