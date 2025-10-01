/**
 * MaxSizedBox - Content-aware truncation component
 *
 * Intelligently constrains content to fit within specified dimensions with clear
 * overflow indicators. Handles large tool outputs, scan results, and log data
 * without causing performance issues or layout collapse.
 *
 * @example
 * <MaxSizedBox maxWidth={80} maxHeight={20} overflowDirection="top">
 *   <Box><Text>Line 1...</Text></Box>
 *   <Box><Text>Line 2...</Text></Box>
 * </MaxSizedBox>
 */

import React from 'react';
import { Box, Text } from 'ink';

/**
 * Minimum height to ensure truncation message can be displayed.
 */
const MINIMUM_MAX_HEIGHT = 2;

export interface MaxSizedBoxProps {
  /** React children to be constrained */
  children?: React.ReactNode;
  /** Maximum width in characters */
  maxWidth: number;
  /** Maximum height in lines */
  maxHeight: number | undefined;
  /** Direction to hide overflow content */
  overflowDirection?: 'top' | 'bottom';
  /** Additional hidden lines count (for external tracking) */
  additionalHiddenLinesCount?: number;
}

/**
 * Constrains children to specified dimensions with intelligent truncation.
 *
 * Requirements:
 * - Direct children must be Box components (each representing a line)
 * - Box children must contain only Text components
 * - Preserves text styling (colors, bold, etc.) during truncation
 *
 * @param props MaxSizedBoxProps configuration
 */
export const MaxSizedBox: React.FC<MaxSizedBoxProps> = ({
  children,
  maxWidth,
  maxHeight,
  overflowDirection = 'top',
  additionalHiddenLinesCount = 0,
}) => {
  // Convert children to array of lines for processing
  const lines: React.ReactNode[] = [];

  React.Children.forEach(children, (child) => {
    if (React.isValidElement(child) && child.type === Box) {
      lines.push(child);
    }
  });

  // Calculate effective max height with minimum guarantee
  const targetMaxHeight = maxHeight
    ? Math.max(Math.round(maxHeight), MINIMUM_MAX_HEIGHT)
    : Number.MAX_SAFE_INTEGER;

  // Determine if content will overflow
  const contentWillOverflow =
    lines.length > targetMaxHeight || additionalHiddenLinesCount > 0;

  // Reserve one line for truncation indicator if needed
  const visibleContentHeight = contentWillOverflow
    ? targetMaxHeight - 1
    : targetMaxHeight;

  // Calculate hidden lines
  const hiddenLinesCount = Math.max(0, lines.length - visibleContentHeight);
  const totalHiddenLines = hiddenLinesCount + additionalHiddenLinesCount;

  // Select visible portion based on overflow direction
  const visibleLines =
    hiddenLinesCount > 0
      ? overflowDirection === 'top'
        ? lines.slice(hiddenLinesCount)
        : lines.slice(0, visibleContentHeight)
      : lines;

  return (
    <Box flexDirection="column" width={maxWidth} flexShrink={0}>
      {totalHiddenLines > 0 && overflowDirection === 'top' && (
        <Box>
          <Text dimColor>
            ... first {totalHiddenLines} line{totalHiddenLines === 1 ? '' : 's'}{' '}
            hidden ...
          </Text>
        </Box>
      )}

      {visibleLines.map((line, index) => (
        <Box key={index}>{line}</Box>
      ))}

      {totalHiddenLines > 0 && overflowDirection === 'bottom' && (
        <Box>
          <Text dimColor>
            ... last {totalHiddenLines} line{totalHiddenLines === 1 ? '' : 's'}{' '}
            hidden ...
          </Text>
        </Box>
      )}
    </Box>
  );
};
