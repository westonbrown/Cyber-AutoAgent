/**
 * Terminal Size Hook - Robust terminal dimension management
 *
 * Provides automatic terminal resize handling with built-in padding and fallback defaults.
 * Ensures consistent layout across different terminal sizes and resize events.
 *
 * @example
 * const { availableWidth, availableHeight } = useTerminalSize();
 * const divider = '─'.repeat(availableWidth);
 */

import { useEffect, useState } from 'react';

/**
 * Horizontal padding to prevent text from hitting terminal edges.
 * Provides comfortable reading margins.
 */
const TERMINAL_PADDING_X = 8;

/**
 * Vertical padding to reserve space for UI chrome (header, footer).
 * Ensures content doesn't overlap with fixed UI elements.
 */
const TERMINAL_PADDING_Y = 4;

/**
 * Minimum guaranteed width to prevent layout collapse in small terminals.
 */
const MIN_WIDTH = 60;

/**
 * Minimum guaranteed height to prevent content clipping.
 */
const MIN_HEIGHT = 20;

/**
 * Default terminal dimensions when stdout properties are unavailable.
 * Standard 80x24 terminal with padding applied.
 */
const DEFAULT_COLUMNS = 80;
const DEFAULT_ROWS = 24;

export interface TerminalSize {
  /** Raw terminal column count */
  columns: number;
  /** Raw terminal row count */
  rows: number;
  /** Available width after padding (use for content layout) */
  availableWidth: number;
  /** Available height after padding (use for content layout) */
  availableHeight: number;
}

/**
 * Hook for managing terminal dimensions with automatic resize handling.
 *
 * Subscribes to terminal resize events and provides both raw and padded dimensions.
 * Handles edge cases like missing stdout properties or extremely small terminals.
 *
 * @returns TerminalSize object with current dimensions
 */
export function useTerminalSize(): TerminalSize {
  const [size, setSize] = useState<TerminalSize>(() => {
    const cols = process.stdout.columns || DEFAULT_COLUMNS;
    const rows = process.stdout.rows || DEFAULT_ROWS;
    return {
      columns: cols,
      rows: rows,
      availableWidth: Math.max(cols - TERMINAL_PADDING_X, MIN_WIDTH),
      availableHeight: Math.max(rows - TERMINAL_PADDING_Y, MIN_HEIGHT),
    };
  });

  useEffect(() => {
    function updateSize() {
      const cols = process.stdout.columns || DEFAULT_COLUMNS;
      const rows = process.stdout.rows || DEFAULT_ROWS;
      setSize({
        columns: cols,
        rows: rows,
        availableWidth: Math.max(cols - TERMINAL_PADDING_X, MIN_WIDTH),
        availableHeight: Math.max(rows - TERMINAL_PADDING_Y, MIN_HEIGHT),
      });
    }

    // Subscribe to terminal resize events
    process.stdout.on('resize', updateSize);

    // Cleanup listener on unmount
    return () => {
      process.stdout.off('resize', updateSize);
    };
  }, []);

  return size;
}
