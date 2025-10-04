/**
 * Layout Constants - Standardized spacing and sizing
 *
 * Centralized layout configuration for consistent UI rendering across components.
 * Replaces magic numbers with semantic constants for maintainability.
 */

/**
 * Reserved space for fixed UI elements (header, footer, status bar).
 * Prevents content from overlapping with non-scrollable chrome.
 */
export const RESERVED_VERTICAL_SPACE = {
  /** Header height (operation info, model, target) */
  HEADER: 3,
  /** Footer height (metrics, tokens, cost, duration) */
  FOOTER: 3,
  /** Status bar and padding */
  STATUS_BAR: 2,
  /** Additional padding for breathing room */
  PADDING: 2,
  /** Total reserved space */
  get TOTAL() {
    return this.HEADER + this.FOOTER + this.STATUS_BAR + this.PADDING;
  },
};

/**
 * Tool display spacing requirements.
 * Ensures tool output has proper layout without overlap.
 */
export const TOOL_LAYOUT = {
  /** Lines for tool name, status, description */
  HEADER: 2,
  /** Padding around tool content */
  PADDING: 1,
  /** Minimum visible lines for tool output */
  MIN_OUTPUT_LINES: 3,
  /** Total reserved space per tool */
  get RESERVED() {
    return this.HEADER + this.PADDING * 2;
  },
};

/**
 * Content area sizing.
 * Determines maximum space available for scrollable content.
 */
export const CONTENT_AREA = {
  /** Fraction of terminal width to use (0.89 = 89% for margins) */
  WIDTH_FRACTION: 0.89,
  /** Minimum content width to prevent collapse */
  MIN_WIDTH: 60,
  /** Minimum content height to prevent clipping */
  MIN_HEIGHT: 10,
};

/**
 * Calculate available height for active content (tools, reasoning, output).
 *
 * @param terminalHeight Total terminal height in lines
 * @returns Available height for active content area
 */
export function calculateAvailableHeight(terminalHeight: number): number {
  return Math.max(
    terminalHeight - RESERVED_VERTICAL_SPACE.TOTAL,
    CONTENT_AREA.MIN_HEIGHT
  );
}

/**
 * Calculate available height for a single tool display.
 *
 * @param terminalHeight Total terminal height in lines
 * @returns Available height for tool output content
 */
export function calculateToolContentHeight(terminalHeight: number): number {
  const totalAvailable = calculateAvailableHeight(terminalHeight);
  return Math.max(
    totalAvailable - TOOL_LAYOUT.RESERVED,
    TOOL_LAYOUT.MIN_OUTPUT_LINES
  );
}

/**
 * Calculate available width for content.
 *
 * @param terminalWidth Total terminal width in columns
 * @returns Available width for content area
 */
export function calculateAvailableWidth(terminalWidth: number): number {
  return Math.max(
    Math.floor(terminalWidth * CONTENT_AREA.WIDTH_FRACTION),
    CONTENT_AREA.MIN_WIDTH
  );
}
